#!/usr/bin/env python3
"""entities.py — the fourth cross-cut: one page per thing, not per year.

`dates.py` re-files the corpus by calendar day and `cross.py` by decade, century and
subject. This one re-files it by the *entity a sentence is about*: every dated line in
which Wikipedia's own editors linked to "Constantinople", in order, from the 4th century
to the 20th, each with the revision it was quoted from.

Why this is not another copy of Wikipedia. Wikipedia has an article ON Constantinople --
prose about the city. It does not publish "every dated event in every year article that
links to Constantinople", because that aggregate does not live in any one article; it is
scattered across two thousand of them. A handful of subjects have a hand-written
"Timeline of ..." article; the other four thousand here do not, and none of them carry a
per-line citation to a fixed revision.

The links come from the wikitext itself -- `[[Constantinople]]` in the source line -- so
the association is Wikipedia's editorial judgement, not ours and not a language model's.
Only sentences already PUBLISHED on a year page are used, so every line on an entity page
has been through verify.py and exists on a page of ours we can link back to.

A link target is a STRING, and one subject is written many ways: editors link Persia and
Iran, Macedon and Macedonia (ancient kingdom), Sassanid Empire and Sasanian Empire, USSR
and Soviet Union. Grouping on the string split 136 subjects across 284 pages -- the
Byzantine Empire's timeline was missing the rows filed under "Byzantine" and "Eastern
Roman Empire" -- and left 383 pages without the Wikidata id that is the whole point of
the format, because a redirect title has no item of its own. So every title is resolved
through Wikipedia's own redirect graph first and the rows are merged under the canonical
one. The aliases are recorded on the page and redirected to it, never dropped.

Each entity is resolved against Wikidata to a QID where one exists. That is what turns
the JSON from text into data: a QID is the join key every other database on earth uses,
so somebody merging our timeline with theirs does not have to match on a string.

Usage:
  entities.py [--min-years 8] [--max 4000] [--no-wikidata]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "data", "site")
CLAIMS = os.path.join(ROOT, "data", "claims")
OUT = os.path.join(SITE, "entities")
WD_CACHE = os.path.join(ROOT, "data", "wikidata.json")
REDIR_CACHE = os.path.join(ROOT, "data", "redirects.json")

UA = {"User-Agent": "slashyear.com/1.0 (https://slashyear.com; machine-readable history)"}

# Links we never make a page for. Years, dates and bare numbers already have better pages
# of ours; common nouns linked in passing ("regent", "abbot") describe a role, not a
# subject anyone searches a timeline for.
DATE_RE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}$")
# "AD 4", "AD 757" and "69 AD" are year articles, not subjects: the era can be written on
# either side of the number, and only one side was covered, so 13 year articles had a
# /timeline page of their own.
YEARISH_RE = re.compile(r"^\d{1,4}(\s*(BC|BCE|AD|CE))?$|^(AD|CE|BC|BCE)\s*\d{1,4}$|"
                        r"^\d{1,2}(st|nd|rd|th)\s+century|^\d+s$")
STOP = {
    "Nobility", "Roman Catholic", "Catholic Church",  # kept out: label is a category, not an event subject
}


MONTHS = ("January February March April May June July August September October "
          "November December").split()


def date_key(date: str | None) -> tuple[int, int]:
    """(month, day) for sorting. An entry with no day sorts to the head of its month, an
    entry with no date at all to the head of its year."""
    if not date:
        return (0, 0)
    m = re.match(r"^(?:c\.\s*)?([A-Z][a-z]+)(?:\s+(\d{1,2}))?", date)
    if not m or m.group(1) not in MONTHS:
        return (0, 0)
    return (MONTHS.index(m.group(1)) + 1, int(m.group(2) or 0))


def slugify(title: str) -> str:
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80]


def wanted(name: str) -> bool:
    if not name or len(name) < 3 or len(name) > 70:
        return False
    if name in STOP:
        return False
    if not name[0].isupper():          # [[regent]], [[abbot]] -- a role, not a subject
        return False
    if DATE_RE.match(name) or YEARISH_RE.match(name):
        return False
    if name.startswith(("List of", "Category:", "File:", "Image:", "Template:")):
        return False
    return True


def canonical_titles(names: list[str]) -> dict[str, str]:
    """Every link title -> the article Wikipedia actually serves for it.

    `action=query&redirects=1` follows the redirect graph 50 titles at a time and is the
    only authority for this: the alternative is guessing that "Sassanid Empire" and
    "Sasanian Empire" are the same subject, which is exactly the judgement this project
    does not make for itself. Titles that do not resolve (red links, deleted pages) keep
    the name they had. Cached on disk, so a rebuild resolves only new links."""
    import requests
    cache: dict[str, str] = {}
    if os.path.exists(REDIR_CACHE):
        cache = json.load(open(REDIR_CACHE, encoding="utf-8"))
    todo = sorted({n for n in names if n not in cache})
    print(f"  redirects: {len(names) - len(todo):,} cached, {len(todo):,} to resolve")
    if todo:
        from concurrent.futures import ThreadPoolExecutor
        session = requests.Session()
        session.headers.update(UA)

        def one(batch: list[str]) -> dict[str, str]:
            for attempt in range(4):
                try:
                    r = session.get("https://en.wikipedia.org/w/api.php",
                                    params={"action": "query", "titles": "|".join(batch),
                                            "redirects": 1, "format": "json",
                                            "formatversion": 2}, timeout=60)
                    q = r.json()["query"]
                    norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
                    red = {n["from"]: n["to"] for n in q.get("redirects", [])}
                    out = {}
                    for t in batch:
                        step = norm.get(t, t)
                        out[t] = red.get(step, step)
                    return out
                except Exception:
                    time.sleep(2 * (attempt + 1))
            return {t: t for t in batch}

        batches = [todo[i:i + 50] for i in range(0, len(todo), 50)]
        done = 0
        with ThreadPoolExecutor(max_workers=4) as ex:
            for got in ex.map(one, batches):
                cache.update(got)
                done += 1
                if done % 100 == 0:
                    # written as we go: 83,000 titles take minutes and a run that dies
                    # at the end with nothing on disk pays the whole cost again.
                    json.dump(cache, open(REDIR_CACHE, "w", encoding="utf-8"),
                              ensure_ascii=False)
                    print(f"   ...{done}/{len(batches)} batches", flush=True)
        json.dump(cache, open(REDIR_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return cache


def load_links() -> dict[tuple[int, str], list[str]]:
    """(year, sentence) -> the entities Wikipedia linked in that sentence."""
    out: dict[tuple[int, str], list[str]] = {}
    for fn in os.listdir(CLAIMS):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(CLAIMS, fn)))
        y = d["year"]
        for c in d["claims"]:
            ls = [l for l in (c.get("links") or []) if wanted(l)]
            if ls:
                out[(y, c["text"])] = ls
    return out


def load_published():
    """Every entry actually on a year page, in year order."""
    years = []
    for fn in os.listdir(SITE):
        if not fn.endswith(".json") or fn == "index.json":
            continue
        try:
            y = int(fn[:-5])
        except ValueError:
            continue
        years.append((y, os.path.join(SITE, fn)))
    years.sort()
    for y, path in years:
        yield y, json.load(open(path))


def fetch_wikidata(titles: list[str]) -> dict[str, dict]:
    """enwiki article title -> {qid, description, instance_of}. Batched 50 per request.

    Mapping back is done through each entity's own enwiki sitelink rather than by
    position: wbgetentities keys its answer by QID and drops titles it cannot resolve,
    so a positional zip mislabels entities as soon as one title in the batch is missing.
    `normalize=1` is rejected outright for a multi-title request ("only allowed if
    exactly one site and one page have been given") and takes the whole batch down with
    it -- the first run of this returned 0 ids for 2,941 entities because of it. Results are cached on disk, so a rebuild costs
    nothing for entities already seen."""
    cache: dict[str, dict] = {}
    if os.path.exists(WD_CACHE):
        cache = json.load(open(WD_CACHE))
    todo = [t for t in titles if t not in cache]
    print(f"  wikidata: {len(titles) - len(todo):,} cached, {len(todo):,} to fetch")
    for i in range(0, len(todo), 50):
        batch = todo[i : i + 50]
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "sites": "enwiki",
                "titles": "|".join(batch),
                "props": "sitelinks|descriptions|claims",
                "sitefilter": "enwiki",
                "languages": "en",
                "format": "json",
            }
        )
        j: dict = {}
        for attempt in range(4):
            try:
                raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
                j = json.loads(raw)
                break
            except Exception as e:
                if attempt == 3:
                    print("   wikidata batch failed:", e)
                time.sleep(2 * (attempt + 1))

        found: dict[str, dict] = {}
        for qid, ent in (j.get("entities") or {}).items():
            if not qid.startswith("Q"):
                continue
            title = ((ent.get("sitelinks") or {}).get("enwiki") or {}).get("title")
            if not title:
                continue
            inst = []
            for c in (ent.get("claims") or {}).get("P31", [])[:3]:
                try:
                    inst.append(c["mainsnak"]["datavalue"]["value"]["id"])
                except Exception:
                    pass
            rec = {
                "qid": qid,
                "description": ((ent.get("descriptions") or {}).get("en") or {}).get("value"),
                "instance_of": inst,
            }
            found[title] = rec

        for t in batch:
            cache[t] = found.get(t) or {"qid": None, "description": None, "instance_of": []}
        if (i // 50) % 10 == 0:
            json.dump(cache, open(WD_CACHE, "w"))
            print(f"   ...{i + len(batch):,}/{len(todo):,}", flush=True)
        time.sleep(0.12)
    json.dump(cache, open(WD_CACHE, "w"))
    return cache


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-years", type=int, default=6, help="an entity needs this many distinct years to earn a page")
    # The cap is a file budget, not a taste judgement: Cloudflare Pages refuses a
    # deployment over 20,000 files and each entity costs two of them (the page and its
    # /api/entity JSON). Measured 2026-09-08: 14,819 files at 3,114 entities.
    ap.add_argument("--max", type=int, default=4900, help="cap on published entity pages (Cloudflare Pages allows 20,000 files total)")
    ap.add_argument("--no-wikidata", action="store_true")
    ap.add_argument("--protect", default="https://slashyear.com/api/entities.json",
                    help="index of the entity pages that are LIVE right now; those slugs "
                         "keep their page whatever the ranking says. Pass '' to disable.")
    args = ap.parse_args()

    print("reading wikitext links...")
    links = load_links()
    print(f"  {len(links):,} sentences carry at least one usable link")

    # One subject, many spellings: resolve every link through Wikipedia's redirect graph
    # before grouping, or the same entity gets two half-timelines and neither gets a QID.
    all_names = sorted({n for ls in links.values() for n in ls})
    canon = canonical_titles(all_names)

    # Some redirects land where this file will not publish: "Byzantine emperor" and
    # "Ottoman Sultan" resolve to "List of ..." articles, "Catholicism" to the excluded
    # "Catholic Church". Throwing those rows away would delete live pages, and keeping
    # each spelling separate re-creates the split the merge exists to remove -- Catholic
    # Church came back as three pages. So the group still merges; it is just titled with
    # the spelling Wikipedia's editors used most, and the canonical name stays out.
    by_target: dict[str, Counter] = defaultdict(Counter)
    for ls in links.values():
        for n in ls:
            c = canon.get(n, n)
            if c != n and not wanted(c):
                by_target[c][n] += 1
    stand_in = {}
    for target, names in by_target.items():
        rep = sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        for n in names:
            stand_in[n] = rep

    # How many distinct years each spelling covered BEFORE the merge. An alias that
    # cleared the floor on its own was a live URL in the last deploy, so its redirect is
    # the one that must survive the _redirects rule limit; this is the ranking key.
    pre_years: dict[str, set[int]] = defaultdict(set)
    for (y, _t), ls in links.items():
        for n in ls:
            pre_years[n].add(y)

    aliases: dict[str, set[str]] = defaultdict(set)
    moved = 0
    for key, ls in links.items():
        out: list[str] = []
        for n in ls:
            c = canon.get(n, n)
            if c != n:
                if not wanted(c):
                    c = stand_in.get(n, n)
                if c == n:
                    pass
                else:
                    moved += 1
                    aliases[c].add(n)
            if c not in out:             # a sentence linking both Persia and Iran counts once
                out.append(c)
        links[key] = out
    print(f"  {moved:,} links follow a redirect to their canonical title; "
          f"{len(aliases):,} titles absorbed at least one alias")

    print("walking published year pages...")
    hits: dict[str, list[dict]] = defaultdict(list)
    label_of: dict[str, str] = {}
    npub = 0
    for y, page in load_published():
        for sec in page["sections"]:
            for it in sec["items"]:
                npub += 1
                for name in links.get((y, it["text"]), []):
                    slug = slugify(name)
                    if not slug:
                        continue
                    label_of.setdefault(slug, name)
                    hits[slug].append(
                        {
                            "year": y,
                            "year_label": page["label"],
                            "section": sec["title"],
                            "date": it.get("date"),
                            "text": it["text"],
                            "cite": it["cite"],
                        }
                    )
    print(f"  {npub:,} published entries, {len(hits):,} distinct entities linked")

    ranked = []
    for slug, items in hits.items():
        yrs = {i["year"] for i in items}
        if len(yrs) < args.min_years:
            continue
        ranked.append((len(yrs), len(items), slug))
    ranked.sort(reverse=True)

    # A page that is live and indexed does not get to disappear because a new source added
    # competitors for the file budget. The country-year harvest put 1,180 fresh entities
    # over the floor and the cap silently dropped the Berlin Wall, Anne Frank and Johannes
    # Gutenberg -- all three had pages yesterday. The ranking decides who fills what is
    # LEFT of the cap; it does not get to retire a URL.
    protected: set[str] = set()
    if args.protect:
        try:
            if args.protect.startswith("http"):
                import urllib.request
                # Cloudflare answers a bare urllib request with 403; it wants a UA.
                req = urllib.request.Request(
                    args.protect, headers={"User-Agent": "slashyear-build/1.0 "
                                           "(https://www.slashyear.com)"})
                with urllib.request.urlopen(req, timeout=30) as fh:
                    live = json.load(fh)
                # Keep a copy so a rebuild without network still protects the same URLs.
                json.dump(live, open(os.path.join(ROOT, "data", "live-entities.json"),
                                     "w", encoding="utf-8"))
            else:
                live = json.load(open(args.protect, encoding="utf-8"))
            protected = {e["slug"] for e in live.get("entities", [])} & set(hits)
            print(f"  {len(protected):,} entity pages are live now and are kept whatever "
                  f"the ranking says")
        except Exception as e:
            print(f"  WARNING: could not read {args.protect} ({e.__class__.__name__}); "
                  f"publishing on rank alone, which may retire live URLs")
    keep = [s for _, _, s in ranked if s in protected]
    room = max(0, args.max - len(keep))
    keep += [s for _, _, s in ranked if s not in protected][:room]
    print(f"  {len(ranked):,} clear the {args.min_years}-year floor; publishing {len(keep):,} "
          f"({len(protected):,} of them protected as live)")

    wd = {}
    if not args.no_wikidata:
        print("resolving Wikidata ids...")
        wd = fetch_wikidata([label_of[s] for s in keep])

    # co-occurrence, for the "related" rail: entities that appear in the same sentences
    keepset = set(keep)
    co: dict[str, Counter] = defaultdict(Counter)
    sent_ents: dict[tuple[int, str], list[str]] = defaultdict(list)
    for slug in keep:
        for it in hits[slug]:
            sent_ents[(it["year"], it["text"])].append(slug)
    for ents in sent_ents.values():
        if len(ents) < 2:
            continue
        for a in ents:
            for b in ents:
                if a != b:
                    co[a][b] += 1

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    index = []
    for slug in keep:
        # Chronological, not alphabetical. Sorting on the date STRING put December before
        # January inside a year, so 1,005 timelines listed their rows out of order --
        # Michael Jackson's 2009 read "June 25, June 25, March 5".
        items = sorted(hits[slug], key=lambda i: (i["year"], date_key(i.get("date"))))
        # de-duplicate: the same sentence can be published under two sections in rare cases
        seen, uniq = set(), []
        for i in items:
            k = (i["year"], i["text"])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(i)
        items = uniq
        yrs = sorted({i["year"] for i in items})
        topics = Counter(i["section"] for i in items)
        info = wd.get(label_of[slug]) or {}
        page = {
            "slug": slug,
            "label": label_of[slug],
            "wikipedia": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(label_of[slug].replace(" ", "_")),
            "wikidata": ("https://www.wikidata.org/wiki/" + info["qid"]) if info.get("qid") else None,
            "qid": info.get("qid"),
            "description": info.get("description"),
            "entries": len(items),
            "years": len(yrs),
            "span": [yrs[0], yrs[-1]],
            "span_label": [items[0]["year_label"], items[-1]["year_label"]],
            "topics": [{"title": t, "count": c} for t, c in topics.most_common()],
            # The spellings Wikipedia's editors used that redirect here. Shown on the
            # page, and 301'd to it, so a merge never costs a URL.
            "also_known_as": sorted(aliases.get(label_of[slug], [])),
            "related": [
                {"slug": s, "label": label_of[s], "shared": c}
                for s, c in co[slug].most_common(12)
                if s in keepset
            ],
            "items": items,
        }
        json.dump(page, open(os.path.join(OUT, f"{slug}.json"), "w"), ensure_ascii=False)
        index.append(
            {
                "slug": slug,
                "label": page["label"],
                "qid": page["qid"],
                "description": page["description"],
                "entries": page["entries"],
                "years": page["years"],
                "span_label": page["span_label"],
            }
        )

    index.sort(key=lambda e: (-e["entries"], e["slug"]))
    json.dump({"count": len(index), "entities": index}, open(os.path.join(OUT, "index.json"), "w"), ensure_ascii=False)

    # Every alias slug that used to be (or could have been) a page of its own now points
    # at the canonical one. postbuild.py turns these into 301s so the merge costs no URL.
    kept_slugs = set(keep)
    pairs = []
    for canon_title, names in aliases.items():
        target = slugify(canon_title)
        if target not in kept_slugs:
            continue
        for n in names:
            alias = slugify(n)
            if alias and alias != target and alias not in kept_slugs:
                pairs.append((len(pre_years.get(n, ())), alias, target))
    # Most-covered first: Cloudflare Pages caps _redirects, so the aliases that were
    # pages of their own have to be at the head of the file.
    pairs.sort(key=lambda t: (-t[0], t[1]))
    merged = {alias: target for _n, alias, target in pairs}
    # NOT inside data/site: verify.py, surface.py, dates.py and postbuild.py all read
    # that directory as "one JSON per year" and int() the filename.
    json.dump(merged, open(os.path.join(ROOT, "data", "entities-merged.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=0)
    withq = sum(1 for e in index if e["qid"])
    print(f"wrote {len(index):,} entity pages to {OUT} ({withq:,} carry a Wikidata id, "
          f"{len(merged):,} alias slugs redirect in)")


if __name__ == "__main__":
    main()
