/* GET /api/search?q=&from=&to=&limit=
 *
 * The one route on the site that computes. It answers two different questions at once
 * because a caller usually has both: which subjects match this query (navigation, and a
 * whole timeline behind each), and which individual dated sentences match it (the fact
 * they actually came for). Krakatoa has no subject page — it is in three years — and
 * still comes back with its eruptions, which is the case that made the full-text index
 * worth building.
 */
import { CORS, rankSubjects, searchText, subjects } from "../../edge/search.js";

const H = { ...CORS, "cache-control": "public, max-age=600" };

export async function onRequest({ request, env }) {
  if (request.method === "OPTIONS") return new Response(null, { headers: H });
  if (request.method !== "GET")
    return new Response(JSON.stringify({ error: "GET only" }), { status: 405, headers: H });

  const url = new URL(request.url);
  const q = (url.searchParams.get("q") || "").slice(0, 200);
  const from = parseInt(url.searchParams.get("from") ?? "", 10);
  const to = parseInt(url.searchParams.get("to") ?? "", 10);
  const limit = Math.min(Math.max(parseInt(url.searchParams.get("limit") ?? "25", 10) || 25, 1), 200);

  if (!q.trim())
    return new Response(
      JSON.stringify({
        error: "pass ?q=",
        usage: `${url.origin}/api/search?q=eruption&from=1800&to=1900&limit=20`,
        note: "years use astronomical numbering, so -43 is 44 BCE",
        docs: `${url.origin}/api`,
      }, null, 1),
      { status: 400, headers: H },
    );

  const rows = await subjects(env, request);
  const hits = rankSubjects(rows, q);
  const text = await searchText(env, request, q, { from, to, limit });

  return new Response(
    JSON.stringify({
      query: q,
      filters: { from: Number.isFinite(from) ? from : null, to: Number.isFinite(to) ? to : null, limit },
      subjects: hits.map(({ r }) => ({
        label: r.label,
        slug: r.slug,
        description: r.description || null,
        wikidata: r.qid || null,
        entries: r.entries,
        span: [r.from, r.to],
        page: `${url.origin}/timeline/${r.slug}`,
        json: `${url.origin}/api/entity/${r.slug}.json`,
      })),
      entries_total: text.total,
      entries_truncated: text.truncated,
      entries: text.entries.map((e) => ({
        ...e,
        page: `${url.origin}/${e.year === 404 ? "404/" : e.year}`,
      })),
      license: "CC BY-SA 4.0 — attribute the article and revision id on each entry",
      bulk: `${url.origin}/dump/datapackage.json`,
      docs: `${url.origin}/api`,
    }, null, 1),
    { headers: H },
  );
}
