/* POST /mcp — a Model Context Protocol server over streamable HTTP, no auth.
 *
 * The reason this exists: a model that wants a dated historical fact currently has two
 * options, both bad. It can recall the fact from training, which cannot be checked, or it
 * can fetch an encyclopedia article and read prose around the answer. This gives it a
 * third: ask for the year, the day or the subject and get rows back, each carrying the
 * revision id the sentence was quoted from, so the answer it writes can cite something
 * that will still say the same thing next year.
 *
 * Deliberately stateless. No sessions, no SSE, no storage: every request is a complete
 * JSON-RPC exchange answered from static files, which is why it cannot fall behind the
 * site or go down separately from it.
 */

import { CORS as BASE_CORS, asset, norm, rankSubjects, searchText, subjects }
  from "../edge/search.js";

const PROTOCOL = "2025-06-18";

const CORS = { ...BASE_CORS };
delete CORS["content-type"];

const JSONH = { ...CORS, "content-type": "application/json; charset=utf-8" };

const MONTHS = ["january", "february", "march", "april", "may", "june", "july",
  "august", "september", "october", "november", "december"];

function daySlug(input) {
  const s = String(input || "").trim().toLowerCase();
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return `${MONTHS[parseInt(m[2], 10) - 1]}-${parseInt(m[3], 10)}`;
  m = s.match(/^(\d{1,2})-(\d{1,2})$/);
  if (m) return `${MONTHS[parseInt(m[1], 10) - 1]}-${parseInt(m[2], 10)}`;
  m = s.match(/^([a-z]+)[ -](\d{1,2})$/);
  if (m && MONTHS.includes(m[1])) return `${m[1]}-${parseInt(m[2], 10)}`;
  m = s.match(/^(\d{1,2})[ -]([a-z]+)$/);
  if (m && MONTHS.includes(m[2])) return `${m[2]}-${parseInt(m[1], 10)}`;
  return null;
}

const TOOLS = [
  {
    name: "search_history",
    description:
      "Full-text search across every dated entry in the historical record, plus the subjects " +
      "that match. Each entry is a sentence quoted verbatim from a numbered English Wikipedia " +
      "revision and carries that revision id, so an answer built on it can cite a source that " +
      "will still say the same thing next year. Use this whenever you need a dated fact.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "words to find, e.g. 'volcanic eruption' or 'Constantinople'" },
        from_year: { type: "integer", description: "earliest year; astronomical numbering, so -43 means 44 BCE" },
        to_year: { type: "integer", description: "latest year" },
        limit: { type: "integer", description: "maximum entries to return (default 25, max 200)" },
      },
      required: ["query"],
    },
  },
  {
    name: "get_year",
    description:
      "Everything the record holds for one year: the headline summary and every dated entry, " +
      "grouped by subject, each with its source revision.",
    inputSchema: {
      type: "object",
      properties: { year: { type: "integer", description: "astronomical numbering: 1969, or -43 for 44 BCE" } },
      required: ["year"],
    },
  },
  {
    name: "get_day",
    description:
      "One calendar day across every recorded year — what happened on 4 July in all of them. " +
      "This aggregate exists in no single encyclopedia article.",
    inputSchema: {
      type: "object",
      properties: { date: { type: "string", description: "'july-4', 'July 4', '07-04' or any 'YYYY-MM-DD'" } },
      required: ["date"],
    },
  },
  {
    name: "get_timeline",
    description:
      "One subject's whole record in date order: every dated entry across all years in which " +
      "Wikipedia's editors linked to it, with its Wikidata id for joining to other datasets.",
    inputSchema: {
      type: "object",
      properties: {
        subject: { type: "string", description: "subject name or slug, e.g. 'Byzantine Empire' or 'byzantine-empire'" },
        from_year: { type: "integer" },
        to_year: { type: "integer" },
        limit: { type: "integer", description: "default 100, max 1000" },
      },
      required: ["subject"],
    },
  },
  {
    name: "list_subjects",
    description: "Browse the subjects that have a timeline, largest record first.",
    inputSchema: {
      type: "object",
      properties: {
        starts_with: { type: "string" },
        limit: { type: "integer", description: "default 50, max 500" },
      },
    },
  },
];

function text(obj) {
  return { content: [{ type: "text", text: JSON.stringify(obj, null, 1) }] };
}

async function call(name, args, env, request) {
  const origin = new URL(request.url).origin;
  const cap = (n, d, max) => Math.min(Math.max(parseInt(n ?? d, 10) || d, 1), max);
  const inRange = (y, a, b) =>
    (!Number.isFinite(a) || y >= a) && (!Number.isFinite(b) || y <= b);
  const from = Number.isFinite(args?.from_year) ? args.from_year : NaN;
  const to = Number.isFinite(args?.to_year) ? args.to_year : NaN;

  if (name === "search_history") {
    const limit = cap(args?.limit, 25, 200);
    const rows = await subjects(env, request);
    const hits = rankSubjects(rows, args?.query || "");
    const found = await searchText(env, request, args?.query || "", { from, to, limit });
    return text({
      query: args?.query,
      subjects: hits.map(({ r }) => ({
        label: r.label, slug: r.slug, description: r.description || null, wikidata: r.qid || null,
        entries: r.entries, span: [r.from, r.to], page: `${origin}/timeline/${r.slug}`,
      })),
      entries_total: found.total,
      entries_truncated: found.truncated,
      entries: found.entries.map((e) => ({
        ...e, page: `${origin}/${e.year === 404 ? "404/" : e.year}`,
      })),
      license: "CC BY-SA 4.0. Attribute the Wikipedia article and revision id on each entry.",
    });
  }

  if (name === "get_year") {
    const y = parseInt(args?.year, 10);
    if (!Number.isFinite(y)) return text({ error: "year must be an integer" });
    const page = await asset(env, request, `/api/year/${y}.json`);
    if (!page)
      return text({
        error: `no records published for year ${y}`,
        reason: "a year with nothing sourced to it gets no page rather than an empty one",
        directory: `${origin}/`,
      });
    return text({ ...page, page: `${origin}/${y === 404 ? "404/" : y}` });
  }

  if (name === "get_day") {
    const slug = daySlug(args?.date);
    if (!slug) return text({ error: "could not read that date", examples: ["july-4", "July 4", "1969-07-20"] });
    const page = await asset(env, request, `/api/date/${slug}.json`);
    if (!page) return text({ error: `nothing published for ${slug}` });
    return text({ ...page, page: `${origin}/on/${slug}` });
  }

  if (name === "get_timeline") {
    const rows = await subjects(env, request);
    const want = String(args?.subject || "");
    let slug = rows.find((r) => r.slug === norm(want).replace(/ /g, "-"))?.slug;
    if (!slug) slug = rankSubjects(rows, want, 1)[0]?.r?.slug;
    if (!slug) return text({ error: `no timeline for "${want}"`, hint: "try list_subjects" });
    const page = await asset(env, request, `/api/entity/${slug}.json`);
    if (!page) return text({ error: `no timeline for "${want}"` });
    const limit = cap(args?.limit, 100, 1000);
    const items = page.items.filter((it) => inRange(it.year, from, to));
    return text({
      subject: page.label, slug: page.slug, description: page.description,
      wikidata: page.qid, wikipedia: page.wikipedia,
      entries_total: items.length, span: page.span_label,
      related: page.related.map((r) => r.label),
      entries: items.slice(0, limit).map((it) => ({
        year: it.year, year_label: it.year_label, date: it.date, section: it.section, text: it.text,
        source: { wikipedia_article: it.cite.title, revision_id: it.cite.revid, url: it.cite.url },
      })),
      page: `${origin}/timeline/${page.slug}`,
      license: "CC BY-SA 4.0. Attribute the Wikipedia article and revision id on each entry.",
    });
  }

  if (name === "list_subjects") {
    const rows = await subjects(env, request);
    const p = norm(args?.starts_with || "");
    const limit = cap(args?.limit, 50, 500);
    const out = rows.filter((r) => !p || norm(r.label).startsWith(p));
    return text({
      total: out.length,
      subjects: out.slice(0, limit).map((r) => ({
        label: r.label, slug: r.slug, description: r.description || null,
        wikidata: r.qid || null, entries: r.entries, span: [r.from, r.to],
      })),
    });
  }

  return text({ error: `unknown tool ${name}` });
}

export async function onRequest({ request, env }) {
  if (request.method === "OPTIONS") return new Response(null, { headers: CORS });

  if (request.method === "GET") {
    // Not an SSE stream — but a human or a directory that opens the URL should be told
    // exactly what this is and how to connect, rather than getting a bare 405.
    return new Response(
      JSON.stringify(
        {
          name: "slashyear",
          description:
            "Model Context Protocol server for the year-by-year historical record: every entry " +
            "quoted verbatim from a numbered English Wikipedia revision, with that revision id.",
          protocol: "mcp",
          protocolVersion: PROTOCOL,
          transport: "streamable-http (POST JSON-RPC to this URL)",
          auth: null,
          tools: TOOLS.map((t) => t.name),
          docs: new URL(request.url).origin + "/api",
        },
        null,
        1,
      ),
      { headers: JSONH },
    );
  }

  if (request.method !== "POST")
    return new Response(JSON.stringify({ error: "POST JSON-RPC" }), { status: 405, headers: JSONH });

  let msg;
  try {
    msg = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } }),
      { status: 400, headers: JSONH },
    );
  }

  const one = async (m) => {
    const id = m?.id ?? null;
    const ok = (result) => ({ jsonrpc: "2.0", id, result });
    const err = (code, message) => ({ jsonrpc: "2.0", id, error: { code, message } });
    switch (m?.method) {
      case "initialize":
        return ok({
          protocolVersion: PROTOCOL,
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: "slashyear", version: "1.0.0" },
          instructions:
            "Sourced history. Every entry is a sentence quoted verbatim from a specific English " +
            "Wikipedia revision and carries that revision id, so a claim built on it stays " +
            "checkable. Years use astronomical numbering: -43 is 44 BCE. Reuse is free under " +
            "CC BY-SA 4.0; cite the article and revision id.",
        });
      case "ping":
        return ok({});
      case "tools/list":
        return ok({ tools: TOOLS });
      case "tools/call": {
        const t = TOOLS.find((x) => x.name === m?.params?.name);
        if (!t) return err(-32602, `unknown tool: ${m?.params?.name}`);
        try {
          return ok(await call(t.name, m?.params?.arguments || {}, env, request));
        } catch (e) {
          return ok({ content: [{ type: "text", text: `error: ${e?.message || e}` }], isError: true });
        }
      }
      case "resources/list":
        return ok({ resources: [] });
      case "prompts/list":
        return ok({ prompts: [] });
      default:
        return err(-32601, `method not found: ${m?.method}`);
    }
  };

  // Notifications carry no id and get no body back, per JSON-RPC.
  const batch = Array.isArray(msg) ? msg : [msg];
  const answers = [];
  for (const m of batch) {
    if (m?.id === undefined || m?.id === null) {
      if (typeof m?.method === "string" && m.method.startsWith("notifications/")) continue;
    }
    answers.push(await one(m));
  }
  if (!answers.length) return new Response(null, { status: 202, headers: CORS });
  return new Response(JSON.stringify(Array.isArray(msg) ? answers : answers[0]), {
    headers: { ...JSONH, "mcp-protocol-version": PROTOCOL },
  });
}
