/* GET /api/check?claim=  (or POST {"claim": "..."})
 *
 * Checks one sentence against the record and returns the entries that bear on it. Leaders,
 * No. 1 singles and Nobel prizes get a structured check, because for those the record is
 * complete enough to say "contradicted". Anything else is matched against the dated
 * sentences, and the answer is where the record dates what matches, never a judgement
 * written by a model.
 */
import { CORS } from "../../edge/search.js";
import { checkClaim } from "../../edge/asof.js";

const H = { ...CORS, "cache-control": "public, max-age=3600" };

export async function onRequest({ request, env }) {
  if (request.method === "OPTIONS") return new Response(null, { headers: H });
  const url = new URL(request.url);
  let claim = url.searchParams.get("claim");
  if (request.method === "POST") {
    try { claim = (await request.json())?.claim ?? claim; } catch { /* fall through */ }
  } else if (request.method !== "GET")
    return new Response(JSON.stringify({ error: "GET or POST" }), { status: 405, headers: H });
  if (!claim)
    return new Response(JSON.stringify({
      error: "pass ?claim=",
      usage: `${url.origin}/api/check?claim=${encodeURIComponent("Richard Nixon was president in 1975")}`,
      verdicts: {
        supported: "the record has the fact for that year (and day, if one is given)",
        contradicted: "structured checks only: the record is complete for the question and says otherwise",
        conflicting_dates: "entries matching the claim are dated differently",
        evidence_only: "the claim names no year; matching entries are returned",
        no_evidence: "nothing in the record bears on it; this is not a judgement that it is false",
      },
    }, null, 1), { status: 400, headers: H });
  const out = await checkClaim(env, request, claim, url.origin);
  return new Response(JSON.stringify(out, null, 1), { status: out.error ? 400 : 200, headers: H });
}
