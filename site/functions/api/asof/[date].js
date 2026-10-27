/* GET /api/asof/1969-07-20 — the world on one date, assembled from the published record. */
import { answer } from "../../../edge/asofhttp.js";

export async function onRequest({ request, env, params }) {
  return answer(request, env, params.date);
}
