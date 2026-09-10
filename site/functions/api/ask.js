/* Ask History — /api/ask
 *
 * POST {question, token, from?, to?} -> a chronological answer where every sentence is
 * pinned to sentences we already publish, each carrying the Wikipedia revision id it was
 * frozen from. The model is never asked what it knows; it is handed passages and told to
 * arrange and connect them. That is the whole design: the site's claim is that every line
 * is sourced, and an unsourced sentence from a language model would end that claim.
 *
 * Retrieval is the same static inverted index the site already ships (`/api/text`, 121k
 * sentences), read through edge/search.js. No vector database, no embedding call, nothing
 * running between deploys — so the only thing this route can spend money on is the one
 * completion at the end, which is exactly the thing the budget guard below counts.
 *
 * Four separate brakes, because one is never enough on a public endpoint:
 *   1. Turnstile   — every request carries a solved challenge, verified server-side.
 *   2. Per-IP rate — a burst limit per minute and a hard ceiling per day.
 *   3. Global rate — a site-wide daily ceiling, in case an attacker has many IPs.
 *   4. Budget      — running spend for the calendar month; over the cap the route stops
 *                    answering entirely rather than degrading quietly.
 *
 * KV counters are read-modify-write and KV is eventually consistent, so a determined
 * attacker racing many requests through different colos can overshoot a counter slightly.
 * That is deliberate: the budget guard is the backstop that actually bounds the money, and
 * it is checked before every completion. Exactness would cost a Durable Object and buy
 * nothing, because the limits are already set well under the cap.
 */
import { asset, rankSubjects, searchText, subjects } from "../../edge/search.js";

const num = (v, d) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
};

/* Defaults are deliberately conservative; every one is overridable as a Pages variable
 * without a redeploy. */
const cfg = (env) => ({
  budgetUsd: num(env.ASK_BUDGET_USD, 150),
  usdInPerM: num(env.ASK_USD_PER_MTOK_IN, 0.19),
  usdOutPerM: num(env.ASK_USD_PER_MTOK_OUT, 0.51),
  perIpDay: num(env.ASK_PER_IP_DAY, 15),
  perIpMin: num(env.ASK_PER_IP_MIN, 4),
  globalDay: num(env.ASK_GLOBAL_DAY, 1500),
  maxQuestion: num(env.ASK_MAX_QUESTION, 300),
  maxOutTokens: num(env.ASK_MAX_OUT_TOKENS, 700),
  passages: num(env.ASK_PASSAGES, 40),
  perTimeline: num(env.ASK_PER_TIMELINE, 18),
  maxPassages: num(env.ASK_MAX_PASSAGES, 90),
});

const json = (body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body, null, 1), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra },
  });

const monthKey = (d = new Date()) => `spend:${d.toISOString().slice(0, 7)}`;
const dayKey = (d = new Date()) => d.toISOString().slice(0, 10);
const minKey = (d = new Date()) => d.toISOString().slice(0, 16);

/** Spend is stored in micro-dollars as an integer string: KV values are text, and
 *  floating point accumulated a cent of drift a week when this was stored as a float. */
async function spentUsd(kv) {
  const raw = await kv.get(monthKey());
  return (parseInt(raw || "0", 10) || 0) / 1e6;
}

async function addSpendUsd(kv, usd) {
  const k = monthKey();
  const cur = parseInt((await kv.get(k)) || "0", 10) || 0;
  // 70 days of TTL: the key only has to outlive its own month.
  await kv.put(k, String(cur + Math.round(usd * 1e6)), { expirationTtl: 70 * 86400 });
}

async function bump(kv, key, ttl) {
  const cur = parseInt((await kv.get(key)) || "0", 10) || 0;
  await kv.put(key, String(cur + 1), { expirationTtl: ttl });
  return cur + 1;
}

async function verifyTurnstile(secret, token, ip) {
  if (!secret) return { ok: false, why: "captcha not configured" };
  if (!token) return { ok: false, why: "captcha missing" };
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token);
  if (ip) form.append("remoteip", ip);
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    body: form,
  });
  const d = await r.json().catch(() => ({}));
  return d.success ? { ok: true } : { ok: false, why: (d["error-codes"] || []).join(",") || "captcha failed" };
}

/** A stable key for the question, so the same question asked twice costs once. */
async function qhash(s) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].slice(0, 12).map((x) => x.toString(16).padStart(2, "0")).join("");
}

const SYSTEM = `You are the research writer for slashyear, a reference site whose entire promise is that every line is sourced.

You will be given a question and a numbered list of dated passages. The passages are the ONLY facts you may use. You have no other knowledge and must not supply any.

Rules, in order of importance:
1. Every factual sentence you write ends with one or more citation markers like [3] or [3][7], naming the passages it came from. A sentence with no marker is a mistake.
2. Never state a fact that is not in a passage. Do not fill gaps, infer dates, name people, or round numbers that the passages do not give.
3. Answer chronologically. Lead with the earliest relevant event and move forward, so the answer reads as a sequence rather than a list.
4. You may connect events into a narrative — "which left", "after this", "by then" — but the causal claim must be visible in the passages themselves. If you are joining two events whose connection is not stated, say plainly that the passages record both but do not state a link.
5. If the passages do not answer the question, say exactly what they do and do not cover, and stop. A short honest answer is correct; a padded one is a failure.
6. Plain English. No headings, no bullet lists, no preamble, no closing summary. Three to six short paragraphs at most.`;

const PLANNER = `You turn a history question into a retrieval plan for a corpus of dated events. Reply with JSON only, no prose, no code fence.

{"queries": ["..."], "subjects": ["..."], "from": <year|null>, "to": <year|null>}

queries: 2 to 4 short keyword searches, each 1-4 words, using words that would literally appear in a one-line record of the event. Never include words like decline, impact, cause, effect, modern, history — those are your words, not the record's.
subjects: the people, places, empires, organisations or things the question is about, by their common name.
from/to: the years the question is about, as plain integers, or null if it names no period. Use astronomical numbering, so 44 BC is -43. If the question refers to a period by name rather than by date ("while Rome was falling", "the Industrial Revolution"), convert it to the years yourself.

Example question: What was happening in Japan while the Roman Empire was falling?
{"queries":["Japan emperor","Yamato court","Western Roman Empire"],"subjects":["Japan","Roman Empire"],"from":350,"to":550}`;

/** A first, tiny call that turns the question into search terms and a date range.
 *
 *  Without it the index is searched with the question's own vocabulary, and a question
 *  is written in words the record never uses: "decline", "shape", "modern" appear in no
 *  one-line entry, while "while the Roman Empire was falling" carries a date range that
 *  nothing in a bag of words can see. This costs one short completion — a fraction of
 *  the answer's own cost — and is the difference between answering the question asked
 *  and answering the words it was asked in. */
async function plan(env, question, c) {
  const fallback = { queries: [question], subjects: [], from: undefined, to: undefined };
  try {
    const r = await fetch(env.AZURE_DS_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json", "api-key": env.AZURE_DS_KEY },
      body: JSON.stringify({
        model: env.AZURE_DS_MODEL || "DeepSeek-V4-Flash",
        messages: [{ role: "system", content: PLANNER }, { role: "user", content: question }],
        temperature: 0,
        max_tokens: 200,
        response_format: { type: "json_object" },
      }),
    });
    if (!r.ok) return { ...fallback, usage: null };
    const d = await r.json();
    const raw = d?.choices?.[0]?.message?.content || "";
    const p = JSON.parse(raw.replace(/^```(?:json)?|```$/g, "").trim());
    const clean = (a) => (Array.isArray(a) ? a.filter((x) => typeof x === "string" && x.trim()).slice(0, 5) : []);
    const yr = (v) => (Number.isFinite(Number(v)) && v !== null && v !== "" ? Number(v) : undefined);
    const queries = clean(p.queries);
    return {
      queries: queries.length ? queries : [question],
      subjects: clean(p.subjects),
      from: yr(p.from),
      to: yr(p.to),
      usage: d?.usage || null,
    };
  } catch {
    return { ...fallback, usage: null };
  }
}

/* Word-matching alone answers "how did the decline of the Ottoman Empire shape modern
 * Syria" with the three sentences that happen to carry both names, because the question's
 * own words — decline, shape, modern — are not in the record and the record does not
 * narrate. The subjects the question names each have a whole published timeline behind
 * them, so those are pulled in as well and the model is handed the run of events rather
 * than the intersection of two words. This is the difference between a search result and
 * an answer, and it costs nothing: the timelines are static files we already serve. */
async function timelines(env, request, names, c, { from, to }) {
  let rows;
  try {
    rows = await subjects(env, request);
  } catch {
    return [];
  }
  const slugs = new Set();
  for (const name of names.slice(0, 4)) for (const { r } of rankSubjects(rows, name, 1)) slugs.add(r.slug);

  const out = [];
  for (const slug of slugs) {
    const doc = await asset(env, request, `/api/entity/${slug}.json`);
    for (const it of sample(doc?.items || [], c.perTimeline, { from, to })) out.push(it);
  }
  return out;
}

/** Spread a long timeline evenly rather than taking its first N: an entity with 600
 *  entries would otherwise contribute only its earliest century. Births and deaths go
 *  last — a founder's birth year is rarely what a question about consequences wants. */
function sample(items, n, { from, to }) {
  const inRange = items.filter(
    (it) => (!Number.isFinite(from) || it.year >= from) && (!Number.isFinite(to) || it.year <= to));
  const events = inRange.filter((it) => it.section !== "Births" && it.section !== "Deaths");
  const pool = events.length >= Math.min(n, 4) ? events : inRange;
  if (pool.length <= n) return pool;
  const step = pool.length / n;
  return Array.from({ length: n }, (_, i) => pool[Math.floor(i * step)]);
}

/** One list, chronological, no sentence twice. Chronological because the answer has to
 *  be: a model handed passages in relevance order writes them back in relevance order. */
function merge(a, b) {
  const seen = new Set();
  const out = [];
  for (const e of [...a, ...b]) {
    const k = `${e.year}|${e.text}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(e);
  }
  return out.sort((x, y) => x.year - y.year);
}

function buildPassages(entries) {
  return entries
    .map((e, i) => {
      const when = e.date ? `${e.date}, ${e.year_label}` : e.year_label;
      return `[${i + 1}] ${when} — ${e.text}`;
    })
    .join("\n");
}

/* GET /api/ask — public callers learn only whether the route is up. The spend/limits
 * view is operational detail: it needs the status key (ASK_STATUS_KEY, sent as ?key= or
 * an x-status-key header), because budget and traffic numbers are nobody's business. */
export async function onRequestGet({ request, env }) {
  const c = cfg(env);
  if (!env.ASK_KV) return json({ enabled: false }, 200);
  const spent = await spentUsd(env.ASK_KV);
  const enabled = Boolean(env.AZURE_DS_KEY) && spent < c.budgetUsd;

  const url = new URL(request.url);
  const given = url.searchParams.get("key") || request.headers.get("x-status-key");
  const authed = Boolean(env.ASK_STATUS_KEY) && given === env.ASK_STATUS_KEY;
  if (!authed) {
    return json({
      enabled,
      note: "Answers are composed only from sentences published on this site; each carries the Wikipedia revision id it was frozen from.",
    });
  }

  const used = await env.ASK_KV.get(`g:${dayKey()}`);
  return json({
    enabled,
    month: monthKey().slice(6),
    budget_usd: c.budgetUsd,
    spent_usd: Math.round(spent * 10000) / 10000,
    remaining_usd: Math.round((c.budgetUsd - spent) * 10000) / 10000,
    answers_today: parseInt(used || "0", 10) || 0,
    limits: {
      per_ip_per_day: c.perIpDay,
      per_ip_per_minute: c.perIpMin,
      site_per_day: c.globalDay,
      max_question_chars: c.maxQuestion,
    },
    model: env.AZURE_DS_MODEL || "DeepSeek-V4-Flash",
  });
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
}

export async function onRequestPost({ request, env }) {
  const c = cfg(env);
  const kv = env.ASK_KV;
  if (!kv) return json({ error: "Ask History is not configured." }, 503);

  // Same-origin only. Turnstile already binds a token to our domains, but refusing
  // cross-origin callers means a scraper cannot even burn the rate limit from a page.
  const origin = request.headers.get("origin");
  const here = new URL(request.url).origin;
  if (origin && origin !== here) return json({ error: "Cross-origin requests are not accepted." }, 403);

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Send JSON." }, 400);
  }

  const question = String(body.question || "").trim().slice(0, c.maxQuestion);
  if (question.length < 8) return json({ error: "Ask a fuller question." }, 400);

  const from = Number.isFinite(Number(body.from)) && body.from !== null && body.from !== "" ? Number(body.from) : undefined;
  const to = Number.isFinite(Number(body.to)) && body.to !== null && body.to !== "" ? Number(body.to) : undefined;

  // 4 — budget first: it is the only check that bounds money, so nothing runs before it.
  const spent = await spentUsd(kv);
  if (spent >= c.budgetUsd)
    return json({
      error: "Ask History has reached its budget for this month and will come back at the start of the next one.",
      alternative: `${here}/api/search?q=${encodeURIComponent(question)}`,
    }, 503);

  const ip = request.headers.get("cf-connecting-ip") || "0.0.0.0";
  const day = dayKey();

  // A cached answer is served before the rate limiters, not after: re-reading an answer
  // the site has already paid for is not abuse, and shared links would otherwise burn a
  // visitor's daily quota on someone else's question.
  const key = `ans:${await qhash(`${question}|${from ?? ""}|${to ?? ""}`)}`;
  const cached = await kv.get(key);
  if (cached) return json({ ...JSON.parse(cached), cached: true });

  // 1 — captcha.
  const t = await verifyTurnstile(env.TURNSTILE_SECRET, body.token, ip);
  if (!t.ok) return json({ error: "Captcha check failed — reload the page and try again.", detail: t.why }, 403);

  // 2 and 3 — rate limits.
  const perMin = await bump(kv, `ipm:${ip}:${minKey()}`, 180);
  if (perMin > c.perIpMin) return json({ error: "Too fast. Wait a minute and ask again." }, 429);

  const perDay = await bump(kv, `ip:${ip}:${day}`, 2 * 86400);
  if (perDay > c.perIpDay)
    return json({ error: `That is ${c.perIpDay} questions today, which is the daily limit. The full index stays open at /api/search.` }, 429);

  const globalToday = await bump(kv, `g:${day}`, 2 * 86400);
  if (globalToday > c.globalDay)
    return json({ error: "Ask History has hit its limit for today across the whole site. It resets at midnight UTC." }, 429);

  // Plan, then retrieve. Only the plan and the answer touch the model.
  const p = await plan(env, question, c);
  const span = { from: from ?? p.from, to: to ?? p.to };
  const per = Math.max(8, Math.round(c.passages / Math.max(p.queries.length, 1)));

  let hits = [];
  let matched = 0;
  for (const q of p.queries) {
    const r = await searchText(env, request, q, { ...span, limit: per });
    matched += r.total || 0;
    hits = hits.concat(r.entries || []);
  }
  // A named period can be wrong or too tight; if it emptied the result, drop it and retry
  // unfiltered rather than telling the reader the record is silent when it is not.
  if (!hits.length && (Number.isFinite(span.from) || Number.isFinite(span.to)))
    for (const q of p.queries) {
      const r = await searchText(env, request, q, { limit: per });
      matched += r.total || 0;
      hits = hits.concat(r.entries || []);
    }

  const names = p.subjects.length ? p.subjects : p.queries;
  const entries = merge(hits, await timelines(env, request, names, c, span)).slice(0, c.maxPassages);
  if (!entries.length)
    return json({
      question,
      answer: "Nothing in the index matches that question closely enough to answer it from sources. Try naming a person, place or event directly.",
      sources: [],
      matched: 0,
    });

  const messages = [
    { role: "system", content: SYSTEM },
    { role: "user", content: `Question: ${question}\n\nPassages:\n${buildPassages(entries)}` },
  ];

  let data;
  try {
    const r = await fetch(env.AZURE_DS_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json", "api-key": env.AZURE_DS_KEY },
      body: JSON.stringify({
        model: env.AZURE_DS_MODEL || "DeepSeek-V4-Flash",
        messages,
        temperature: 0.2,
        max_tokens: c.maxOutTokens,
      }),
    });
    if (!r.ok) {
      const text = await r.text();
      return json({ error: "The answering model did not respond. Try again shortly.", status: r.status, detail: text.slice(0, 300) }, 502);
    }
    data = await r.json();
  } catch (e) {
    return json({ error: "The answering model did not respond. Try again shortly.", detail: String(e).slice(0, 200) }, 502);
  }

  const answer = data?.choices?.[0]?.message?.content?.trim() || "";
  const usage = data?.usage || {};
  const billed = (u) =>
    (num(u?.prompt_tokens, 0) / 1e6) * c.usdInPerM + (num(u?.completion_tokens, 0) / 1e6) * c.usdOutPerM;
  // Both calls are counted, or the budget guard would quietly under-report by the planner.
  const cost = billed(usage) + billed(p.usage);
  await addSpendUsd(kv, cost);

  // Only the passages the answer actually cited are returned as sources — a citation list
  // that includes everything retrieved is not a citation list.
  const cited = new Set([...answer.matchAll(/\[(\d{1,2})\]/g)].map((m) => parseInt(m[1], 10)));
  const sources = entries
    .map((e, i) => ({ n: i + 1, ...e }))
    .filter((e) => cited.has(e.n))
    .map((e) => ({
      n: e.n,
      year: e.year,
      year_label: e.year_label,
      date: e.date || null,
      text: e.text,
      page: `${here}/${e.year === 404 ? "404/" : e.year}`,
      // searchText returns the citation nested; the entity timelines return it as `cite`.
      wikipedia: e.source?.url || e.cite?.url || null,
      revision: e.source?.revision_id ?? e.cite?.revid ?? null,
    }));

  const payload = {
    question,
    answer,
    sources,
    matched: matched || entries.length,
    model: env.AZURE_DS_MODEL || "DeepSeek-V4-Flash",
    license: "CC BY-SA 4.0 — attribute the article and revision id on each source",
  };

  // 30 days: the corpus only changes on a rebuild, and a rebuild is rarer than that.
  await kv.put(key, JSON.stringify(payload), { expirationTtl: 30 * 86400 });
  return json(payload);
}
