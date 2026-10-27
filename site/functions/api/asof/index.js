/* GET /api/asof?date=YYYY-MM-DD — same answer as /api/asof/YYYY-MM-DD. */
import { answer } from "../../../edge/asofhttp.js";

export async function onRequest({ request, env }) {
  return answer(request, env, new URL(request.url).searchParams.get("date"));
}
