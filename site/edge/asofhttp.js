import { CORS } from "./search.js";
import { snapshot } from "./asof.js";

const H = { ...CORS, "cache-control": "public, max-age=86400" };

export async function answer(request, env, date) {
  if (request.method === "OPTIONS") return new Response(null, { headers: H });
  const origin = new URL(request.url).origin;
  if (!date)
    return new Response(JSON.stringify({
      error: "pass a date",
      usage: [`${origin}/api/asof/1969-07-20`, `${origin}/api/asof?date=1969-07-20`],
      what: "the world on one date: that day's dated entries, leaders in office that year, the Billboard No. 1, U.S. prices, world population, official series and exchange rates, each with its source",
    }, null, 1), { status: 400, headers: H });
  const out = await snapshot(env, request, date, origin);
  return new Response(JSON.stringify(out, null, 1), { status: out.error ? 400 : 200, headers: H });
}
