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
import { checkClaim, snapshot } from "../edge/asof.js";

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
    name: "get_country",
    description:
      "One country's dated record, century by century, harvested from the per-country year " +
      "articles English Wikipedia writes separately ('1969 in Japan') and never indexes " +
      "together. Use this when the question is about a nation rather than a year or a subject.",
    inputSchema: {
      type: "object",
      properties: {
        country: { type: "string", description: "country name or slug, e.g. 'Japan', 'south-africa'" },
        from_year: { type: "integer", description: "earliest year; astronomical numbering" },
        to_year: { type: "integer", description: "latest year" },
        limit: { type: "integer", description: "default 200, max 2000" },
      },
      required: ["country"],
    },
  },
  {
    name: "get_year_facts",
    description:
      "What a year (1800-2025) looked like in numbers, from outside sources rather than " +
      "encyclopedia prose: world population, U.S. CPI and what a dollar then is worth now, " +
      "average U.S. prices (gas, eggs, bread, milk, houses, income, minimum wage), who led the " +
      "major powers, and the Billboard Hot 100 No. 1 songs. Every figure carries its source. " +
      "For any other country's leaders use get_leaders.",
    inputSchema: {
      type: "object",
      properties: { year: { type: "integer", description: "1800 to 2025" } },
      required: ["year"],
    },
  },
  {
    name: "get_leaders",
    description:
      "Who led a country (or every country) in a year, 1800-2025: heads of state, heads of " +
      "government and ruling-party leaders, in the order they held the post. Each name is quoted " +
      "from Wikipedia's list of state leaders (revision id given) and kept only where the " +
      "person's Wikidata record holds the same post over the same years, so a missing name " +
      "means the sources disagree, not that the post was empty.",
    inputSchema: {
      type: "object",
      properties: {
        year: { type: "integer", description: "1800 to 2025" },
        country: { type: "string", description: "optional: country or state name, e.g. 'Brazil', 'Ottoman Empire', 'Soviet Union'. Omit for every state" },
      },
      required: ["year"],
    },
  },
  {
    name: "get_number_one_song",
    description:
      "The Billboard Hot 100 No. 1 single on a given date (1958-08-04 onward): the first chart " +
      "issue dated on or after that day, quoted from a cited Wikipedia revision.",
    inputSchema: {
      type: "object",
      properties: { date: { type: "string", description: "YYYY-MM-DD" } },
      required: ["date"],
    },
  },
  {
    name: "convert_dollars",
    description:
      "Inflation-adjust U.S. dollars between years with the BLS CPI-U (1913 onward). Omit " +
      "to_year for the latest published month.",
    inputSchema: {
      type: "object",
      properties: {
        amount: { type: "number" },
        from_year: { type: "integer" },
        to_year: { type: "integer", description: "optional; default is the latest CPI month" },
      },
      required: ["amount", "from_year"],
    },
  },
  {
    name: "get_world_on_date",
    description:
      "The world on one date in a single answer: the dated entries for that exact day, births " +
      "and deaths that day, every state's office holders that year, the Billboard Hot 100 No. 1 " +
      "in force, U.S. prices and CPI, world population, official series (unemployment, rates, " +
      "GDP, debt, CO2, temperature), Federal Reserve exchange rates for that day, and that " +
      "year's Nobel Prizes. Each part carries its source; parts no source covers are absent.",
    inputSchema: {
      type: "object",
      properties: { date: { type: "string", description: "YYYY-MM-DD, e.g. 1969-07-20" } },
      required: ["date"],
    },
  },
  {
    name: "check_claim",
    description:
      "Check one dated sentence against the record before stating it. Leaders, Billboard No. 1 " +
      "singles and Nobel Prizes get a structured check that can return 'supported' or " +
      "'contradicted' with the source. Other claims are matched against the dated entries and " +
      "the answer says where the record dates sentences holding the claim's key words " +
      "(matched_same_year, matched_other_years, ...), with the entries as evidence.",
    inputSchema: {
      type: "object",
      properties: { claim: { type: "string", description: "e.g. 'Richard Nixon was president of the United States in 1975'" } },
      required: ["claim"],
    },
  },
  {
    name: "get_nobel_prizes",
    description:
      "Nobel laureates for a year (1901 on) or for a category across years, from the Nobel " +
      "Prize API and kept only where Wikidata records the same prize in the same year.",
    inputSchema: {
      type: "object",
      properties: {
        year: { type: "integer" },
        category: { type: "string", description: "Physics, Chemistry, Physiology or Medicine, Literature, Peace, Economic Sciences" },
        name: { type: "string", description: "optional: laureate name to find" },
      },
    },
  },
  {
    name: "get_official_series",
    description:
      "Official data series by year from the agencies that publish them, each cross-checked " +
      "against a second copy: U.S. unemployment, federal funds rate, GDP, population, federal " +
      "debt, Mauna Loa CO2, global temperature anomaly, Fed exchange rates. Omit series to list them.",
    inputSchema: {
      type: "object",
      properties: {
        series: { type: "string", description: "series id from the list, e.g. 'unemployment_rate'" },
        from_year: { type: "integer" },
        to_year: { type: "integer" },
      },
    },
  },
  {
    name: "get_disagreements",
    description:
      "Where two sources slashyear checks against each other disagree: leaders' terms " +
      "(Wikipedia lists vs Wikidata), birth and death dates (Wikipedia year articles vs " +
      "Wikidata), Nobel Prizes (Nobel API vs Wikidata). Useful before trusting either source.",
    inputSchema: {
      type: "object",
      properties: {
        person: { type: "string", description: "optional: name to look for" },
        section: { type: "string", description: "optional: leaders, life_years, life_days or nobel" },
        limit: { type: "integer", description: "default 50, max 500" },
      },
    },
  },
  {
    name: "list_countries",
    description: "Browse the countries that have a record of their own, largest first.",
    inputSchema: {
      type: "object",
      properties: { limit: { type: "integer", description: "default 100, max 500" } },
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

  if (name === "get_country" || name === "list_countries") {
    const cross = await asset(env, request, "/api/cross.json");
    const places = cross?.places || [];
    if (name === "list_countries") {
      return text({
        countries_total: places.length,
        countries: places.slice(0, cap(args?.limit, 100, 500)).map((p) => ({
          country: p.label, slug: p.slug, entries: p.total, span: p.span,
          page: `${origin}/in/${p.slug}`,
        })),
      });
    }
    const want = norm(String(args?.country || ""));
    const hit = places.find((p) => p.slug === want.replace(/ /g, "-"))
      || places.find((p) => norm(p.label) === want)
      || places.find((p) => norm(p.label).includes(want) && want.length > 2);
    if (!hit) return text({ error: `no record for "${args?.country}"`, hint: "try list_countries" });
    const page = await asset(env, request, `/api/place/${hit.slug}.json`);
    if (!page) return text({ error: `no record for "${args?.country}"` });
    const limit = cap(args?.limit, 200, 2000);
    const items = [];
    for (const c of page.centuries) {
      for (const it of c.items) if (inRange(it.year, from, to)) items.push(it);
    }
    return text({
      country: page.label, slug: page.slug, span: page.span,
      entries_total: page.total,
      entries_shown: Math.min(items.length, limit),
      note: "each century shows a sample spread across it; open the year page for everything held for that year",
      entries: items.slice(0, limit).map((it) => ({
        year: it.year, year_label: it.year_label, date: it.date, section: it.section, text: it.text,
        source: { wikipedia_article: it.cite.title, revision_id: it.cite.revid, url: it.cite.url },
        page: `${origin}/${it.year === 404 ? "404/" : it.year}`,
      })),
      page: `${origin}/in/${page.slug}`,
      license: "CC BY-SA 4.0. Attribute the Wikipedia article and revision id on each entry.",
    });
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

  const brief = (s) => ({
    state: s.state,
    holders: s.holders.map((h) => ({ name: h.name, post: h.title || h.office, wikidata: h.qid })),
  });

  if (name === "get_year_facts") {
    const y = parseInt(args?.year, 10);
    if (!Number.isFinite(y)) return text({ error: "year must be an integer" });
    const f = await asset(env, request, `/api/facts/${y}.json`);
    if (!f) return text({ error: `no facts published for ${y}`, covered: "1800 to 2025" });
    const { leaders, ...rest } = f;
    return text({
      ...rest,
      leaders: leaders && {
        major_powers: leaders.states.filter((s) => s.key).map(brief),
        other_states: leaders.states.length - leaders.states.filter((s) => s.key).length,
        more: "get_leaders with this year (and optionally a country) for the rest",
        source: leaders.source,
      },
      pages: { year: `${origin}/${y}`, leaders: leaders ? `${origin}/leaders/${y}` : undefined, born: f.prices ? `${origin}/born/${y}` : undefined },
    });
  }

  if (name === "get_leaders") {
    const y = parseInt(args?.year, 10);
    if (!Number.isFinite(y)) return text({ error: "year must be an integer" });
    const f = await asset(env, request, `/api/facts/${y}.json`);
    if (!f?.leaders) return text({ error: `no leaders published for ${y}`, covered: "1800 to 2025" });
    const q = String(args?.country || "").trim().toLowerCase();
    let states = f.leaders.states;
    if (q) {
      states = states.filter((s) =>
        [s.state, s.country, s.key, s.wikipedia].some((v) => v && v.toLowerCase().includes(q)));
      if (!states.length)
        return text({ year: y, country: args.country, states: [], note: "no state by that name has a checked leader this year", page: `${origin}/leaders/${y}` });
    }
    return text({
      year: y,
      states: q ? states : states.map(brief),
      source: f.leaders.source,
      checked: f.leaders.checked,
      page: `${origin}/leaders/${y}`,
      license: "CC BY-SA 4.0. Attribute the Wikipedia article and revision id.",
    });
  }

  if (name === "get_number_one_song") {
    const d = String(args?.date || "");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return text({ error: "date must be YYYY-MM-DD" });
    if (d < "1958-08-04") return text({ error: "the Hot 100 starts with the issue of 1958-08-04", covered: "1958-08-04 onward" });
    const y = parseInt(d.slice(0, 4), 10);
    let wk = null;
    let src = null;
    for (const yy of [y, y + 1]) {
      const f = await asset(env, request, `/api/facts/${yy}.json`);
      const hit = f?.hot100?.weeks.find((w) => w.date >= d);
      if (hit) { wk = hit; src = f.hot100.source; break; }
    }
    if (!wk) return text({ error: `no Hot 100 issue on or after ${d}`, covered: "1958-08-04 onward" });
    return text({
      date: d, chart_issue_date: wk.date, title: wk.title, artist: wk.artist,
      source: src, page: `${origin}/born/${y}`,
      license: "CC BY-SA 4.0. Attribute the Wikipedia article and revision id.",
    });
  }

  if (name === "convert_dollars") {
    const prices = await asset(env, request, "/api/prices.json");
    const amount = Number(args?.amount);
    const fy = String(parseInt(args?.from_year, 10));
    const a = prices?.cpi?.years?.[fy];
    if (!Number.isFinite(amount) || !a) return text({ error: "need an amount and a from_year of 1913 or later" });
    let b = prices.cpi.latest.value;
    let label = prices.cpi.latest.date.slice(0, 7);
    if (args?.to_year != null) {
      const ty = String(parseInt(args.to_year, 10));
      b = prices.cpi.years[ty];
      label = ty;
      if (!b) return text({ error: `no annual CPI for ${args.to_year}` });
    }
    return text({
      amount, from_year: +fy, to: label,
      result: Math.round(amount * (b / a) * 100) / 100,
      cpi_from: a, cpi_to: b,
      source: prices.cpi.source,
    });
  }

  if (name === "get_world_on_date") return text(await snapshot(env, request, args?.date, origin));

  if (name === "check_claim") return text(await checkClaim(env, request, args?.claim, origin));

  if (name === "get_nobel_prizes") {
    const doc = await asset(env, request, "/api/nobel.json");
    if (!doc) return text({ error: "Nobel data not available" });
    const y = args?.year != null ? String(parseInt(args.year, 10)) : null;
    const cat = norm(args?.category || "");
    const who = norm(args?.name || "");
    const rows = [];
    for (const [yy, ps] of Object.entries(doc.years)) {
      if (y && yy !== y) continue;
      for (const p of ps) {
        if (cat && !norm(p.category).includes(cat)) continue;
        if (who && !norm(p.name).includes(who)) continue;
        rows.push({ year: +yy, ...p });
      }
    }
    if (!y && !cat && !who) return text({ error: "pass a year, a category or a name" });
    return text({
      prizes: rows.slice(0, 300), total: rows.length,
      not_awarded: y ? doc.not_awarded[y] : undefined,
      source: doc.source, checked_against: doc.checked_against, page: `${origin}/nobel`,
    });
  }

  if (name === "get_official_series") {
    const idx = await asset(env, request, "/api/official/index.json");
    if (!idx) return text({ error: "official series not available" });
    if (!args?.series) return text({ series: idx.series.map(({ id, name: n, unit, publisher, span }) => ({ id, name: n, unit, publisher, span })) });
    const hit = idx.series.find((x) => x.id === args.series || norm(x.name).includes(norm(args.series)));
    if (!hit) return text({ error: `no series "${args.series}"`, ids: idx.series.map((x) => x.id) });
    const s = await asset(env, request, `/api/official/${hit.id}.json`);
    const annual = Object.fromEntries(Object.entries(s.annual).filter(([k]) => inRange(+k, from, to)));
    return text({
      id: hit.id, name: s.name, unit: s.unit, annual_method: s.annual_method, annual,
      source: { publisher: s.publisher, url: s.url, license: s.license }, cross_check: s.cross_check,
      more: `${origin}/api/official/${hit.id}.json has the native ${s.frequency} values`,
    });
  }

  if (name === "get_disagreements") {
    const doc = await asset(env, request, "/api/disagreements.json");
    if (!doc) return text({ error: "ledger not available" });
    const who = norm(args?.person || "");
    const limit = cap(args?.limit, 50, 500);
    const out = {};
    for (const [k, sec] of Object.entries(doc.sections)) {
      if (args?.section && k !== args.section) continue;
      const rows = who ? sec.rows.filter((r) => norm(r.person || r.name || "").includes(who)) : sec.rows;
      out[k] = { title: sec.title, rule: sec.rule, total: rows.length, rows: rows.slice(0, limit) };
    }
    return text({ what: doc.what, sections: out, page: `${origin}/disagreements` });
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
          serverInfo: { name: "slashyear", version: "1.3.0" },
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
