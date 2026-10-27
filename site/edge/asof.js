/* The world on one date, and a claim checked against the record. Shared by /api/asof,
 * /api/check and /mcp.
 *
 * Nothing here is new data. A snapshot is the published record cut on one axis: the dated
 * sentences filed under that day, the office holders the checked lists give for that
 * year, the Hot 100 issue in force, the outside series for that year and the exchange
 * rates the Fed published that day. Each part keeps the source it came from, and a part
 * the sources do not cover is left out rather than filled.
 */

import { asset, docShard, FIELDS, meta, norm, searchText } from "./search.js";

export const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/** "1969-07-20" -> {y, m, d}; a real calendar date or null. */
export function parseISO(s) {
  const m = String(s || "").trim().match(/^(-?\d{1,4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const y = parseInt(m[1], 10), mo = parseInt(m[2], 10), d = parseInt(m[3], 10);
  if (mo < 1 || mo > 12 || d < 1) return null;
  const t = new Date(Date.UTC(2000, mo - 1, d));
  t.setUTCFullYear(y);
  if (t.getUTCMonth() !== mo - 1 || t.getUTCDate() !== d) return null;
  return { y, m: mo, d, weekday: WEEKDAYS[t.getUTCDay()] };
}

const pad = (n) => String(n).padStart(2, "0");
const isoOf = ({ y, m, d }) => `${y}-${pad(m)}-${pad(d)}`;

/** Every published sentence for one year, straight from the search shards. */
export async function yearRows(env, request, y) {
  const mt = await meta(env, request);
  if (!mt) return [];
  const out = [];
  for (let i = 0; i < mt.spans.length; i++) {
    const [a, b] = mt.spans[i];
    if (y < a || y > b) continue;
    for (const row of await docShard(env, request, i)) {
      if (row[0] !== y) continue;
      out.push(Object.fromEntries(FIELDS.map((k, j) => [k, row[j]])));
    }
  }
  return out;
}

/** A line that opens on a day range ("April 14–15 –", "14–15 April –") covers every day in it. */
function spans(text, m, d) {
  const mon = MONTHS[m - 1];
  const t = String(text);
  let x = t.match(new RegExp(`^${mon}\\s+(\\d{1,2})\\s*[–-]\\s*(\\d{1,2})\\b`));
  if (!x) x = t.match(new RegExp(`^(\\d{1,2})\\s*[–-]\\s*(\\d{1,2})\\s+${mon}\\b`));
  return !!x && +x[1] <= d && d <= +x[2] && +x[1] !== d;
}

const cited = (r) => ({
  date: r.date, section: r.section, text: r.text,
  source: { wikipedia_article: r.source_title, revision_id: r.source_revid, section: r.source_section, url: r.source_url },
});

/** The Hot 100 issue in force: the first chart issue dated on or after the day, which is
 * how Billboard dates an issue (the week it covers ends on its date). */
async function hot100On(env, request, iso) {
  if (iso < "1958-08-04") return null;
  const y = parseInt(iso.slice(0, 4), 10);
  for (const yy of [y, y + 1]) {
    const f = await asset(env, request, `/api/facts/${yy}.json`);
    const wk = f?.hot100?.weeks.find((w) => w.date >= iso);
    if (wk) return { chart_issue_date: wk.date, title: wk.title, artist: wk.artist, source: f.hot100.source };
  }
  return null;
}

async function fxOn(env, request, iso) {
  const idx = await asset(env, request, "/api/official/index.json");
  if (!idx?.fx?.length) return null;
  const day = (await asset(env, request, `/api/official/fx/${iso.slice(0, 4)}.json`))?.[iso];
  if (!day) return null;
  const rates = idx.fx.filter((id) => day[id] != null).map((id) => {
    const m = idx.fx_meta[id];
    return { id, name: m.name, unit: m.unit, value: day[id], source: { publisher: m.publisher, url: m.url, license: m.license } };
  });
  return rates.length ? { note: "Federal Reserve H.10 noon buying rates in New York for this exact day; none are published on weekends and holidays", rates } : null;
}

export async function snapshot(env, request, input, origin) {
  const p = parseISO(input);
  if (!p) return { error: "date must be a real calendar date as YYYY-MM-DD", example: "1969-07-20" };
  const iso = isoOf(p);
  const day = `${MONTHS[p.m - 1]} ${p.d}`;
  const rows = await yearRows(env, request, p.y);
  const same = rows.filter((r) => r.date === day || spans(r.text, p.m, p.d));
  const facts = p.y >= 1800 ? await asset(env, request, `/api/facts/${p.y}.json`) : null;

  const out = {
    date: iso,
    weekday: p.y >= 1583 ? p.weekday : undefined,
    weekday_note: p.y >= 1583 ? "Gregorian calendar; some countries still used the Julian calendar after 1582" : undefined,
    events: same.filter((r) => r.section !== "Births" && r.section !== "Deaths").map(cited),
    births: same.filter((r) => r.section === "Births").map(cited),
    deaths: same.filter((r) => r.section === "Deaths").map(cited),
    events_same_year: rows.filter((r) => r.date !== day && r.section !== "Births" && r.section !== "Deaths").length,
  };

  if (facts?.leaders) {
    out.leaders = {
      basis: `in office during ${p.y}: the sources give years, not days, so a holder who left before ${day} is still listed`,
      states: facts.leaders.states.map((s) => ({
        state: s.state, country: s.country,
        holders: s.holders.map((h) => ({ name: h.name, post: h.title || h.office, wikidata: h.qid })),
      })),
      source: facts.leaders.source,
      checked: facts.leaders.checked,
    };
  }
  const song = await hot100On(env, request, iso);
  if (song) out.number_one_song = song;
  if (facts?.prices) {
    const pr = facts.prices;
    out.us_prices = {
      cpi_annual_average: pr.cpi, one_dollar_then_in_today_dollars: pr.dollar_today, today_as_of: pr.cpi_now_date,
      items: pr.items.map((i) => ({ label: i.label, per: i.unit, then: i.then, then_in_today_dollars: i.then_in_today_dollars, source: i.source })),
      cpi_source: pr.cpi_source,
    };
  }
  if (facts?.population) out.world_population = facts.population;
  if (facts?.official) out.official_series = facts.official;
  if (facts?.nobel) out.nobel_prizes = facts.nobel;
  const fx = await fxOn(env, request, iso);
  if (fx) out.exchange_rates = fx;

  out.pages = {
    year: `${origin}/${p.y === 404 ? "404/" : p.y}`,
    day: `${origin}/on/${MONTHS[p.m - 1].toLowerCase()}-${p.d}`,
    leaders: facts?.leaders ? `${origin}/leaders/${p.y}` : undefined,
    snapshot: `${origin}/asof?date=${iso}`,
  };
  out.license = "Wikipedia-derived text CC BY-SA 4.0 (cite article and revision id); U.S. government series public domain; other series as labelled.";
  return out;
}

/* ---------- claim checking ---------- */

const MONTH_RE = MONTHS.map((m) => m.toLowerCase()).join("|");
const STOPC = new Set(`a an the and or of in on at to for from by with as is are was were be been being it its
  this that these those his her their he she they them not no but if then than so into over under after before
  during between within about also which who whom whose what when where how there have has had do does did
  will would can could may might happened happen took place year date became become`.split(/\s+/));

function claimDate(claim) {
  const c = claim.toLowerCase();
  let m = c.match(/\b(\d{4})-(\d{2})-(\d{2})\b/);
  if (m) return { y: +m[1], m: +m[2], d: +m[3] };
  m = c.match(new RegExp(`\\b(${MONTH_RE})\\s+(\\d{1,2})(?:st|nd|rd|th)?,?\\s+(\\d{3,4})\\b`));
  if (m) return { y: +m[3], m: MONTHS.findIndex((x) => x.toLowerCase() === m[1]) + 1, d: +m[2] };
  m = c.match(new RegExp(`\\b(\\d{1,2})(?:st|nd|rd|th)?\\s+(${MONTH_RE}),?\\s+(\\d{3,4})\\b`));
  if (m) return { y: +m[3], m: MONTHS.findIndex((x) => x.toLowerCase() === m[2]) + 1, d: +m[1] };
  m = c.match(/\b(\d{1,4})\s*(bc|bce)\b/);
  if (m) return { y: 1 - parseInt(m[1], 10) };
  m = c.match(/\b(1\d{3}|20\d{2})\b/);
  if (m) return { y: +m[1] };
  m = c.match(/\b(?:in|ad|year)\s+([1-9]\d{1,2})\b/);
  if (m) return { y: +m[1] };
  return null;
}

const IRREGULAR = { fell: "fall", sank: "sink", won: "win", began: "begin", became: "become", took: "take",
  died: "die", born: "bear", wrote: "write", led: "lead", fought: "fight", built: "build", made: "make",
  struck: "strike", rose: "rise", froze: "freeze", flew: "fly", ran: "run", sold: "sell", bought: "buy",
  shot: "shoot", killed: "kill", gave: "give", held: "hold", met: "meet", left: "leave", lost: "lose" };

/** Crude stem so "landed" meets "lands" and "sank" meets "sinks". */
export function stem(w) {
  if (IRREGULAR[w]) return IRREGULAR[w];
  for (const suf of ["ings", "ing", "ied", "ies", "ed", "es", "s"]) {
    if (w.endsWith(suf) && w.length - suf.length >= 3) {
      const b = w.slice(0, -suf.length);
      return suf === "ied" || suf === "ies" ? `${b}y` : b;
    }
  }
  return w;
}

/** The words of a claim worth matching: no stop words, no month names, no year. Small
 * numbers and Roman numerals stay, because "Apollo 11" is not "Apollo 17" and "World War I"
 * is not "World War II". */
const ROMAN = new Set(["ii", "iii", "iv", "vi", "vii", "viii", "ix", "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii"]);
function contentTokens(s, when) {
  const skip = new Set([when?.y, when ? 1 - when.y : null, when?.d].filter((x) => x != null).map(String));
  const ws = norm(s).split(" ");
  return [...new Set(ws.filter((w, i) => {
    if (/^\d+$/.test(w)) return w.length <= 3 && +w > 0 && !skip.has(w);
    if (ROMAN.has(w) || (w === "i" && ["war", "world"].includes(ws[i - 1]))) return true;
    return w.length > 2 && !STOPC.has(w) && !MONTHS.some((m) => m.toLowerCase() === w)
      && !["bce", "ad", "bc"].includes(w);
  }))];
}

const isNum = (t) => /^\d+$/.test(t) || t === "i" || ROMAN.has(t);

/** An entry's words, without the "July 20 –" it opens with, which would otherwise count as
 * the "20" in "Apollo 20". */
function entryWords(text) {
  const head = new RegExp(`^\\s*(?:(?:${MONTH_RE})(?:\\s+\\d{1,2})?|\\d{1,2}\\s+(?:${MONTH_RE}))[^–—]{0,40}[–—]\\s*`, "i");
  return norm(String(text).replace(head, "")).split(" ");
}

const POSTS = "president|prime minister|premier|chancellor|king|queen|emperor|empress|monarch|sultan|shah|tsar|czar|pope|leader|head of state|head of government|general secretary|first secretary|chairman|governor-general|governor general|president of the government|taoiseach|dictator|regent|ruler";

async function leaderCheck(env, request, claim, when, origin) {
  const m = claim.match(new RegExp(`^(.+?)\\s+(?:was|became|served as|is|remained)\\s+(?:the\\s+)?(?:\\w+\\s+)?(${POSTS})\\b(?:\\s+of\\s+(?:the\\s+)?(.+?))?(?:\\s+(?:in|during|on)\\b.*)?\\.?$`, "i"));
  if (!m || !when || when.y < 1800 || when.y > 2025) return null;
  const who = contentTokens(m[1], null);
  const where = m[3] ? norm(m[3].replace(/\bin\b.*$/i, "")) : "";
  if (!who.length) return null;
  const shard = await asset(env, request, `/api/leaders-index/${who[who.length - 1][0]}.json`);
  if (!shard) return null;
  const rows = shard.rows.map((r) => Object.fromEntries(shard.fields.map((k, i) => [k, r[i]])));
  const isHim = (h) => who.every((t) => norm(`${h.name} ${h.person}`).split(" ").includes(t));
  const inState = (h) => !where || [h.state, h.country].some((v) => v && norm(v).includes(where));
  const mine = rows.filter((h) => isHim(h) && inState(h));
  if (!mine.length) return null;
  const has = (h, y) => h.years.some(([a, b]) => a <= y && y <= b);
  const f = await asset(env, request, `/api/facts/${when.y}.json`);
  const ev = (h) => ({ name: h.name, state: h.state, post: h.post, quote: h.quote, wikidata: h.qid, years_published: h.years.map(([a, b]) => (a === b ? `${a}` : `${a}-${b}`)).join(", ") });
  const now = mine.filter((h) => has(h, when.y));
  if (now.length)
    return { verdict: "supported", basis: "structured: world leaders record", evidence: now.map(ev), source: f?.leaders?.source, page: `${origin}/leaders/${when.y}` };
  const near = mine.filter((h) => h.years.some(([a, b]) => b >= when.y - 15 && a <= when.y + 15));
  const stateKnown = (f?.leaders?.states || []).some((s) =>
    where ? [s.state, s.country].some((v) => v && norm(v).includes(where)) : near.some((h) => h.state === s.state));
  if (near.length && stateKnown)
    return {
      verdict: "contradicted", basis: "structured: world leaders record",
      explanation: `the record publishes this person in that post for ${near.map((h) => ev(h).years_published).join("; ")}, not ${when.y}`,
      evidence: near.map(ev), source: f?.leaders?.source, page: `${origin}/leaders/${when.y}`,
    };
  return null;
}

const bare = (t) => norm(String(t).replace(/\(.*?\)/g, ""));

async function songCheck(env, request, claim, when, origin) {
  if (!/(number one|number 1\b|no\.? ?1\b|#1\b|hot 100|topped)/i.test(claim) || !when) return null;
  const all = await asset(env, request, "/api/hot100.json");
  if (!all?.weeks?.length) return null;
  const qt = ` ${norm(claim)} `;
  const titles = [...new Set(all.weeks.map((w) => bare(w.title)))].filter((t) => t.length >= 4 && qt.includes(` ${t} `));
  if (!titles.length) return null;
  const title = titles.sort((a, b) => b.length - a.length)[0];
  const runs = all.weeks.filter((w) => bare(w.title) === title);
  const srcFor = (y) => all.sources.find((x) => x.year === y);
  const first = all.weeks[0].date, last = all.weeks[all.weeks.length - 1].date;
  const ev = runs.slice(0, 12).map((w) => ({ chart_issue_date: w.date, title: w.title, artist: w.artist, source: srcFor(+w.date.slice(0, 4)) }));
  const base = { basis: "structured: Billboard Hot 100 number ones, every issue from 1958-08-04", page: `${origin}/born/${when.y}` };
  if (when.m && when.d) {
    const iso = isoOf(when);
    if (iso < first || iso > last) return null;
    const inForce = all.weeks.find((w) => w.date >= iso);
    const ok = inForce && bare(inForce.title) === title;
    return { ...base, verdict: ok ? "supported" : "contradicted",
      explanation: ok ? `"${inForce.title}" was No. 1 on the issue dated ${inForce.date}` : `the issue in force on ${iso} (dated ${inForce?.date}) had "${inForce?.title}" by ${inForce?.artist} at No. 1`,
      evidence: ok ? [{ chart_issue_date: inForce.date, title: inForce.title, artist: inForce.artist, source: srcFor(+inForce.date.slice(0, 4)) }] : ev };
  }
  if (when.y < 1958 || when.y > +last.slice(0, 4)) return null;
  const that = runs.filter((w) => +w.date.slice(0, 4) === when.y);
  if (that.length) return { ...base, verdict: "supported", explanation: `No. 1 on ${that.length} issue(s) dated ${when.y}`, evidence: that.map((w) => ({ chart_issue_date: w.date, title: w.title, artist: w.artist, source: srcFor(when.y) })) };
  const yrs = [...new Set(runs.map((w) => w.date.slice(0, 4)))];
  return { ...base, verdict: "contradicted", explanation: `"${runs[0].title}" was No. 1 only on issues dated ${yrs.join(", ")}, not ${when.y}`, evidence: ev };
}

async function nobelCheck(env, request, claim, when, origin) {
  const m = claim.match(/nobel (?:peace )?prize(?: in| for)? ?(physics|chemistry|medicine|physiology or medicine|literature|peace|economic sciences|economics)?/i);
  if (!m || !when || when.y < 1901) return null;
  const f = await asset(env, request, `/api/facts/${when.y}.json`);
  if (!f?.nobel) return null;
  let cat = (m[1] || (/peace/i.test(m[0]) ? "peace" : "")).toLowerCase();
  if (cat === "medicine") cat = "physiology or medicine";
  if (cat === "economics") cat = "economic sciences";
  const who = contentTokens(claim.slice(0, m.index), when);
  if (!who.length) return null;
  const pool = f.nobel.prizes.filter((p) => !cat || norm(p.category) === norm(cat));
  const hit = pool.filter((p) => who.every((t) => norm(p.name).split(" ").includes(t)));
  if (hit.length) return { verdict: "supported", basis: "structured: Nobel Prize record", evidence: hit, source: f.nobel.source };
  if (cat && pool.length) {
    const all = await asset(env, request, "/api/nobel.json");
    const theirs = [];
    for (const [yy, ps] of Object.entries(all?.years || {}))
      for (const p of ps) if (who.every((t) => norm(p.name).split(" ").includes(t))) theirs.push(`the ${yy} ${p.category} prize`);
    return {
      verdict: "contradicted", basis: "structured: Nobel Prize record",
      explanation: `the ${when.y} ${pool[0].category} prize went to ${pool.map((p) => p.name).join(", ")}` +
        (theirs.length ? `; the record has ${theirs.join(" and ")} for this laureate (prizes are dated by prize year, which can differ from the year it was presented)` : ""),
      evidence: pool, source: f.nobel.source,
    };
  }
  return null;
}

/** Check one sentence against the record. A verdict of "contradicted" is only given where
 * the record is complete for the question (the year's office holders for a state the
 * record covers, the full run of Hot 100 issues, the year's Nobel prizes). For a free-text
 * event the most the record can say is where it dates the matching sentences. */
export async function checkClaim(env, request, claimIn, origin) {
  const claim = String(claimIn || "").trim().slice(0, 400);
  if (claim.length < 8) return { error: "pass a claim of at least a few words", example: "Apollo 11 landed on the Moon on July 20, 1969" };
  const when = claimDate(claim);
  const base = { claim, year: when?.y ?? null, date: when?.m ? isoOf(when) : null };

  for (const f of [leaderCheck, songCheck, nobelCheck]) {
    const r = await f(env, request, claim, when, origin);
    if (r) return { ...base, ...r };
  }

  const toks = contentTokens(claim, when);
  if (!toks.length) return { ...base, verdict: "no_evidence", explanation: "nothing searchable in the claim" };
  const stems = toks.map(stem);
  const q = toks.map((t) => IRREGULAR[t] || t).join(" ");
  const found = await searchText(env, request, q, { limit: 60, maxShards: 60 });
  const pool = [...found.entries];
  if (when) {
    const near = await searchText(env, request, q, { from: when.y, to: when.y, limit: 40, maxShards: 8 });
    const seen = new Set(pool.map((e) => e.text));
    for (const e of near.entries) if (!seen.has(e.text)) pool.push(e);
  }
  const scored = pool.map((e, rank) => {
    const words = entryWords(e.text);
    const ws = new Set(words);
    const ss = new Set(words.map(stem));
    const hit = toks.filter((t, i) => ws.has(t) || (!isNum(t) && ss.has(stems[i])));
    const numsOk = toks.filter(isNum).every((t) => ws.has(t));
    return { e, rank, all: hit.length === toks.length, cover: hit.length / toks.length, numsOk };
  }).filter((x) => x.numsOk && x.cover >= 0.5).sort((a, b) => b.cover - a.cover || a.rank - b.rank);
  if (!scored.length)
    return { ...base, verdict: "no_evidence", explanation: "no entry in the record holds most of the claim's key words. This is not a judgement that the claim is false", searched: toks };

  const day = when?.m ? `${MONTHS[when.m - 1]} ${when.d}` : null;
  const first = (xs) => [...xs.filter((x) => when && x.e.year === when.y), ...xs.filter((x) => !when || x.e.year !== when.y)];
  const ev = first(scored).slice(0, 8).map(({ e, all, cover }) => ({ ...e, matches_all_key_words: all, word_coverage: Math.round(cover * 100) / 100, page: `${origin}/${e.year === 404 ? "404/" : e.year}` }));
  const full = scored.filter((x) => x.all);
  const g = { ...base, basis: "text match against dated entries: shows where the record dates sentences holding the claim's key words; it does not read meaning", key_words: toks };
  if (!when) return { ...g, verdict: "evidence_only", explanation: "the claim names no year", evidence: ev };
  if (toks.length < 2 || !full.length) return { ...g, verdict: "partial_matches", explanation: "no entry holds every key word of the claim", evidence: ev };
  const same = full.filter((x) => x.e.year === when.y);
  if (same.length) {
    if (day && !same.some((x) => x.e.date === day) && same.every((x) => x.e.date))
      return { ...g, verdict: "matched_other_dates", explanation: `entries holding every key word are dated ${when.y}, on ${[...new Set(same.map((x) => x.e.date))].join(", ")}, not ${day}`, evidence: ev };
    return { ...g, verdict: "matched_same_year", explanation: `an entry dated ${when.y}${day && same.some((x) => x.e.date === day) ? `, ${day},` : ""} holds every key word of the claim`, evidence: ev };
  }
  const yrs = [...new Set(full.map((x) => x.e.year))].slice(0, 8);
  return { ...g, verdict: "matched_other_years", explanation: `entries holding every key word are dated ${yrs.join(", ")}, not ${when.y}`, evidence: ev };
}
