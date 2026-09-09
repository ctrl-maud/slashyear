/* Shared by /api/search and /mcp. Lives outside functions/ so it is bundled as a module
 * and never routed as an endpoint of its own.
 *
 * Search over 86,902 sentences with nothing running: postings bucketed by first letter,
 * sentences in 256-row shards, both plain static files. A query fetches the two or three
 * posting files its words start with, intersects, and hydrates only the shards its
 * results actually land in. Everything it reads is edge-cached and held in module scope,
 * so a warm isolate answers without touching the origin at all.
 */

export const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "content-type, mcp-protocol-version, mcp-session-id, accept",
  "content-type": "application/json; charset=utf-8",
};

const cache = { subjects: null, meta: null, posts: new Map(), docs: new Map() };

export async function asset(env, request, path) {
  const url = new URL(request.url);
  url.pathname = path;
  url.search = "";
  const res = await env.ASSETS.fetch(
    new Request(url.toString(), { headers: { accept: "application/json" } }),
  );
  if (!res.ok) return null;
  return res.json();
}

export const norm = (s) =>
  (s || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

/* Mirrors TEXT_STOP in pipeline/postbuild.py. "king", "war" and "city" are absent on
 * purpose: in a historical corpus those are the query, not noise. */
const STOP = new Set(
  `a an the and or of in on at to for from by with as is are was were be been being it its
   this that these those his her their he she they them we you i not no but if then than so
   such into over under after before during between within about also more most other some
   any all each both few many one two three which who whom whose what when where why how
   there here have has had do does did will would can could may might must shall should new
   first second`.split(/\s+/),
);

function queryTokens(q) {
  const out = [];
  for (const w of (q || "").toLowerCase().match(/[a-z0-9]+/g) || []) {
    // Mirrors _tokens() in postbuild.py: a token carrying a digit counts from two
    // characters, so "Apollo 11" is two tokens and intersects, instead of degrading
    // to "Apollo" and answering with the earliest rocket in the corpus.
    const min = /\d/.test(w) ? 2 : 3;
    if (w.length < min || STOP.has(w)) continue;
    const forms = [w];
    if (w.length > 4 && w.endsWith("s") && !w.endsWith("ss")) forms.push(w.slice(0, -1));
    out.push(forms);
  }
  return out;
}

async function postings(env, request, letter) {
  if (cache.posts.has(letter)) return cache.posts.get(letter);
  const table = (await asset(env, request, `/api/text/t-${letter}.json`)) || {};
  cache.posts.set(letter, table);
  return table;
}

async function docShard(env, request, n) {
  if (cache.docs.has(n)) return cache.docs.get(n);
  const rows = (await asset(env, request, `/api/text/d-${n}.json`)) || [];
  cache.docs.set(n, rows);
  return rows;
}

export async function meta(env, request) {
  if (!cache.meta) cache.meta = await asset(env, request, "/api/text/index.json");
  return cache.meta;
}

const FIELDS = ["year", "year_label", "date", "section", "text",
  "source_url", "source_title", "source_revid", "source_section"];

/** Free-text search over every published sentence. */
export async function searchText(env, request, query, { from, to, limit = 25, maxShards = 40 } = {}) {
  const m = await meta(env, request);
  if (!m) return { total: 0, entries: [], truncated: false };
  const groups = queryTokens(query);
  if (!groups.length) return { total: 0, entries: [], truncated: false };

  const N = m.documents;
  const lists = [];
  for (const forms of groups) {
    const seen = new Set();
    for (const f of forms) {
      const table = await postings(env, request, f[0]);
      for (const d of table[f] || []) seen.add(d);
    }
    if (seen.size) lists.push({ set: seen, idf: Math.log(N / seen.size) });
  }
  if (!lists.length) return { total: 0, entries: [], truncated: false };

  lists.sort((a, b) => a.set.size - b.set.size);
  const score = new Map();
  const hitCount = new Map();
  for (const { set, idf } of lists)
    for (const d of set) {
      score.set(d, (score.get(d) || 0) + idf);
      hitCount.set(d, (hitCount.get(d) || 0) + 1);
    }

  // Every word beats some of the words; within each of those, the rarer the better.
  let ids = [...score.keys()];
  const all = ids.filter((d) => hitCount.get(d) === lists.length);
  if (all.length) ids = all;

  // Year filter, applied to whole shards first: docids are in year order.
  const per = m.docs_per_shard;
  const spans = m.spans || [];
  const inYears = (d) => {
    const sp = spans[Math.floor(d / per)];
    if (!sp) return true;
    if (Number.isFinite(to) && sp[0] > to) return false;
    if (Number.isFinite(from) && sp[1] < from) return false;
    return true;
  };
  if (Number.isFinite(from) || Number.isFinite(to)) ids = ids.filter(inYears);

  ids.sort((a, b) => score.get(b) - score.get(a) || a - b);

  const entries = [];
  const wanted = ids.slice(0, Math.max(limit * 6, 60));
  const byShard = new Map();
  for (const d of wanted) {
    const sh = Math.floor(d / per);
    if (!byShard.has(sh)) byShard.set(sh, []);
    byShard.get(sh).push(d);
  }
  /* Shard order decides what the phrase check ever gets to see, and docids are handed
   * out in year order, so hydrating them in their natural order means the ranking is
   * settled by the earliest matches and the sentence that actually says "Apollo 11"
   * is never read. Densest shards first: where a query's matches cluster is where its
   * answer is. */
  const shards = [...byShard.entries()].sort(
    (a, b) => b[1].length - a[1].length || a[0] - b[0]);
  let fetched = 0;
  for (const [sh, docids] of shards) {
    if (fetched >= maxShards) break;
    fetched++;
    const rows = await docShard(env, request, sh);
    for (const d of docids) {
      const row = rows[d % per];
      if (!row) continue;
      const rec = Object.fromEntries(FIELDS.map((k, i) => [k, row[i]]));
      if (Number.isFinite(from) && rec.year < from) continue;
      if (Number.isFinite(to) && rec.year > to) continue;
      entries.push({ ...rec, _s: score.get(d) });
    }
  }
  /* A bag of words puts "Clearchus, tyrant of Heraclea on the Black Sea, is murdered"
   * above the actual Black Death, because it holds both words and they are rarer there.
   * Nothing in the postings can say the words were adjacent, so the phrase check happens
   * here, on the sentences already fetched. */
  /* Where the phrase SITS is evidence of whether the sentence is about it. Four rows
   * carry the words "Apollo 11": the 1969 launch opens with them, Buzz Aldrin's birth
   * has them in a parenthesis, and a 1920 item about the New York Times ridiculing
   * Goddard has them in its last clause. All three matched the phrase and the tie broke
   * on year, so the answer to "Apollo 11" was a 1920 newspaper story. A sentence that
   * opens on the phrase is about it; one that ends on it is mentioning it. */
  const phrase = norm(query);
  if (phrase)
    for (const e of entries) {
      const t = norm(e.text);
      const at = t.indexOf(phrase);
      if (at >= 0) e._s += 1000 + 300 * (1 - at / Math.max(t.length, 1));
    }
  /* A bare year IS a query on a site of year pages. Without this, "1969" answers with a
   * 1622 shipwreck, because every "(d. 1969)" birth row matches the token just as well
   * and there are more of them. */
  const asYear = /^-?\d{1,4}$/.test(query.trim()) ? parseInt(query.trim(), 10) : null;
  if (asYear !== null) for (const e of entries) if (e.year === asYear) e._s += 2000;
  entries.sort((a, b) => b._s - a._s || a.year - b.year);
  return {
    total: ids.length,
    truncated: shards.length > fetched,
    entries: entries.slice(0, limit).map((e) => {
      const { _s, source_url, source_title, source_revid, source_section, ...rest } = e;
      return {
        ...rest,
        source: {
          wikipedia_article: source_title,
          revision_id: source_revid,
          section: source_section,
          url: source_url,
        },
      };
    }),
  };
}

/* Subject matching, for the navigation half of a result. Substring matching on a short
 * or numeric token is worse than useless here: half the labels carry a disambiguating
 * date range, so "Apollo 11" hit "Jin dynasty (1115-1234)", and "printing press" hit
 * four empresses. A token only counts at a word boundary, and a number only as a whole
 * word. */
const loose = (t) => t.length >= 4 && !/^\d+$/.test(t);

export async function subjects(env, request) {
  if (cache.subjects) return cache.subjects;
  const idx = await asset(env, request, "/api/search-index.json");
  if (!idx) return [];
  const f = idx.fields;
  cache.subjects = idx.rows.map((r) => Object.fromEntries(f.map((k, i) => [k, r[i]])));
  return cache.subjects;
}

export function rankSubjects(rows, query, keep = 6) {
  const q = norm(query);
  if (!q) return [];
  const tokens = q.split(" ").filter((t) => t.length > 1);
  const hits = rows
    .map((r) => {
      const label = norm(r.label);
      const words = label.split(" ");
      const desc = norm(r.description);
      let s = 0;
      if (label === q) s += 1000;
      else if (label.startsWith(q)) s += 500;
      else if (label.includes(q)) s += 250;
      for (const t of tokens) {
        if (words.includes(t)) s += 60;
        else if (loose(t) && words.some((w) => w.startsWith(t))) s += 25;
        if (loose(t) && desc.split(" ").some((w) => w.startsWith(t))) s += 8;
      }
      return { r, s: s === 0 ? 0 : s + Math.min(r.entries, 400) / 100 };
    })
    .filter((h) => h.s > 0)
    .sort((a, b) => b.s - a.s);
  if (!hits.length) return hits;
  const floor = Math.max(hits[0].s * 0.45, 20);
  return hits.filter((h) => h.s >= floor).slice(0, keep);
}
