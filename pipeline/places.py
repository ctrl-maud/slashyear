#!/usr/bin/env python3
"""places.py — the country-year articles the world-year articles never had room for.

Measured in COVERAGE-AUDIT.md, the corpus inherits English Wikipedia's own geography:
across 49,685 event rows, Britain and England are named 6,444 times, Italy and Rome
4,814, the United States 4,189 -- against 2,267 for the whole of Africa, 1,455 for Latin
America and 570 for Korea. That is not a ranking bug we can tune away. The world-year
article "1969" is one article, written mostly by editors working in English, and it has
room for a few dozen lines a year for the entire planet.

Wikipedia also publishes a separate article per country per year -- "1969 in Japan",
"2001 in India", "1969 in Brazil" -- in exactly the shape the year articles use:
Incumbents, Events (usually broken out by month), Births, Deaths. They are dense, dated,
individually cited, and largely disjoint from what the world-year article carries.
14,294 of them exist for 186 places between AD 1000 and 2025 (probed, not guessed;
see data/places-manifest.json).

Harvesting them does two things. It adds rows weighted exactly where the record is thin,
and it gives every one of those rows a **country**, which is a column the dataset did not
have and the first thing anyone filtering history reaches for.

Provenance is unchanged: every claim carries the source article and revision id it came
from, so verify.py re-downloads that revision and proves the sentence appears in it, and
the page footer names every article a page quotes.

This runs AFTER extract.py (which rewrites data/claims from scratch) and BEFORE
classify.py, in the same slot deaths.py occupies. It never rewrites a claim it did not
create: a merge drops the previous from_place rows and re-adds them, and leaves
everything else alone.

Usage:
  places.py harvest [--workers 6] [--limit N] [--refresh]
  places.py merge   [--min-year -3000]
  places.py sample "1969 in Japan"      # parse one article, print what would publish
  places.py report                      # country mix of the merged corpus
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract as EX  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
API = "https://en.wikipedia.org/w/api.php"
UA = "slashyear-places/1.0 (https://www.slashyear.com; ahmadopsr@gmail.com)"
MANIFEST = os.path.join(ROOT, "data", "places-manifest.json")
RAW = os.path.join(ROOT, "data", "raw", "places")
CLAIMS = os.path.join(ROOT, "data", "claims")


def slug(place: str) -> str:
    s = place.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def display(place: str) -> str:
    """'the United States' is how the article title reads; 'United States' is the column
    value. The article title keeps its article, the country does not."""
    return re.sub(r"^the\s+", "", place).strip()


# --------------------------------------------------------------------------- fetch ---

def fetch(session, title: str) -> dict | None:
    for attempt in range(5):
        try:
            r = session.get(API, params={
                "action": "query", "prop": "revisions", "rvprop": "content|ids",
                "rvslots": "main", "titles": title, "redirects": 1,
                "format": "json", "formatversion": 2}, timeout=60)
            if r.status_code in (429, 503):
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            page = r.json()["query"]["pages"][0]
            if page.get("missing"):
                return None
            # A redirect that lands somewhere else entirely ("1802 in Wales" ->
            # "Timeline of Welsh history") is a different article about a different
            # scope, and its claims are not this year's. Only accept the article we
            # asked for, or a redirect that kept the "<year> in <place>" shape.
            got = page["title"]
            if got != title and not re.match(r"^\d{3,4} in ", got):
                return None
            rev = page["revisions"][0]
            return {
                "title": got,
                "source": {
                    "site": "en.wikipedia.org",
                    "title": got,
                    "pageid": page["pageid"],
                    "revid": rev["revid"],
                    "url": "https://en.wikipedia.org/wiki/" + got.replace(" ", "_"),
                    "permalink": f"https://en.wikipedia.org/w/index.php?oldid={rev['revid']}",
                    "license": "CC BY-SA 4.0",
                    "retrieved": dt.date.today().isoformat(),
                },
                "wikitext": rev["slots"]["main"]["content"],
            }
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def raw_path(entry: dict) -> str:
    return os.path.join(RAW, slug(entry["place"]), f"{entry['year']}.json")


def harvest_one(entry: dict, refresh: bool) -> str:
    path = raw_path(entry)
    if os.path.exists(path) and not refresh:
        return "cached"
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = UA
    got = fetch(s, entry["title"])
    if not got or len(got["wikitext"]) < 400:
        return "miss"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {"year": entry["year"], "place": display(entry["place"]),
           "source": got["source"], "wikitext": got["wikitext"]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    return "ok"


def cmd_harvest(a) -> int:
    man = json.load(open(MANIFEST, encoding="utf-8"))
    if a.limit:
        man = man[:a.limit]
    os.makedirs(RAW, exist_ok=True)
    counts = {"ok": 0, "cached": 0, "miss": 0}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(harvest_one, e, a.refresh): e for e in man}
        for i, fut in enumerate(as_completed(futs), 1):
            counts[fut.result()] += 1
            if i % 250 == 0:
                rate = i / max(time.time() - t0, 1)
                print(f"  {i:,}/{len(man):,} ok={counts['ok']:,} cached={counts['cached']:,} "
                      f"miss={counts['miss']:,} {rate:.1f}/s "
                      f"eta={(len(man) - i) / max(rate, .01) / 60:.1f}m", flush=True)
    print(f"harvest done in {(time.time() - t0) / 60:.1f}m: {counts}")
    return 0


# --------------------------------------------------------------------------- parse ---

DAYS_IN = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
BARE_DAY = re.compile(r"^(\d{1,2})(?=\s*[\u2013\u2014-]\s)")
HEADINGS = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.M)


def claims_for(rec: dict) -> list[dict]:
    """Parse one country-year article into claims, tagged with their country.

    The article is about exactly one year, so it is year-scoped the way the year's own
    article is -- extract()'s scoping rule exists to stop a century article dumping a
    hundred years onto one page, and it does not apply here.

    Two things are true of these articles and not of the world-year articles, and both
    are handled here rather than in extract.py so the existing corpus parses unchanged:

    1. The month is often a definition-list term (";February") instead of a heading, and
       the lines under it are bare days -- "28 - At midnight Walvis Bay ... is handed over
       to Namibia". Published as-is that is a sentence starting with a number that belongs
       to no month and reaches no calendar page. The month is put back in front of the day,
       and `month_prefix` records that we did it so verify.py can re-derive the published
       text from the stored wikitext exactly.
    2. Because that term is not a real heading, it has no anchor on the source page, so
       the citation must point at the article rather than at a fragment that does not
       exist. `soft_month` says so.
    """
    place = rec["place"]
    sl = slug(place)
    real_heads = {m.group(2).strip().lower() for m in HEADINGS.finditer(rec["wikitext"])}
    out = []
    for c in EX.extract({"year": rec["year"], "label": "", "source": rec["source"],
                         "wikitext": rec["wikitext"]}, scoped=True, month_markers=True):
        trail = c["section_trail"]
        month = trail[-1] if trail and trail[-1] in EX.MONTHS else None
        if month and month.lower() not in real_heads:
            c["soft_month"] = True
        if month and not c.get("date_prefix"):
            m = BARE_DAY.match(c["text"])
            if m and 1 <= int(m.group(1)) <= DAYS_IN[EX.MONTHS.index(month)]:
                c["month_prefix"] = month
                c["text"] = f"{month} {c['text']}"
                c["date"], c["month"], c["day"] = EX.parse_date(c["text"], trail)
                c["body"] = EX.strip_date_lead(c["text"])
        # Whatever is still opening on a bare day number has no month anywhere to give it
        # and would publish as "7 - President Lucas Mangope declares ...". Drop it: the
        # sentence is true but the date on the front of it is unreadable.
        if BARE_DAY.match(c["text"]):
            continue
        c["id"] = f"{rec['year']}:p{sl[:6]}{hashlib.sha1(c['text'].encode()).hexdigest()[:10]}"
        c["country"] = place
        c["from_place"] = True
        # The bullet has to cite the revision it really came from -- "1018 in Scotland",
        # not "1018". Without this the row is published under the year article's source,
        # which is the wrong article, and verify.py reports it as not present in the
        # revision it names, because it is not: 34,560 rows on the first run.
        c["source"] = rec["source"]
        out.append(c)
    return out


def cmd_sample(a) -> int:
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = UA
    got = fetch(s, a.title)
    if not got:
        print("no such article")
        return 1
    m = re.match(r"^(\d{3,4}) in (.+)$", got["title"])
    rec = {"year": int(m.group(1)), "place": display(m.group(2)),
           "source": got["source"], "wikitext": got["wikitext"]}
    cs = claims_for(rec)
    kinds = {}
    for c in cs:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print(f"{got['title']}: {len(rec['wikitext']):,} bytes -> {len(cs)} claims {kinds}")
    for c in cs[:a.show]:
        d = c["date"] or "(no date)"
        print(f"  [{c['kind']:5}] [{d:14}] {c['text'][:150]}")
    return 0


# --------------------------------------------------------------------------- merge ---

def cmd_merge(a) -> int:
    if not os.path.isdir(RAW):
        print("nothing harvested")
        return 1
    by_year: dict[int, list[str]] = {}
    for sl in sorted(os.listdir(RAW)):
        d = os.path.join(RAW, sl)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.endswith(".json"):
                by_year.setdefault(int(fn[:-5]), []).append(os.path.join(d, fn))

    added_total = skipped_dupe = 0
    years_touched = no_year_page = 0
    per_country: dict[str, int] = {}
    for year in sorted(by_year):
        claimp = os.path.join(CLAIMS, f"{year}.json")
        if not os.path.exists(claimp):
            # No world-year page for this year, so there is nothing to merge into. The
            # site publishes a year page only where the year has a source article of its
            # own; inventing one from a single country would put a page on the site whose
            # whole record is one nation.
            no_year_page += 1
            continue
        doc = json.load(open(claimp, encoding="utf-8"))
        kept = [c for c in doc["claims"] if not c.get("from_place")]
        seen = {c["text"].lower()[:120] for c in kept}
        added = []
        for path in sorted(by_year[year]):
            rec = json.load(open(path, encoding="utf-8"))
            for c in claims_for(rec):
                k = c["text"].lower()[:120]
                if k in seen:
                    skipped_dupe += 1
                    continue
                seen.add(k)
                added.append(c)
                per_country[c["country"]] = per_country.get(c["country"], 0) + 1
        doc["claims"] = kept + added
        json.dump(doc, open(claimp, "w", encoding="utf-8"), ensure_ascii=False)
        added_total += len(added)
        years_touched += 1

    print(f"merged {added_total:,} country claims into {years_touched:,} years "
          f"({skipped_dupe:,} dropped as duplicates of rows already held; "
          f"{no_year_page:,} country-years had no world-year page to join)")
    top = sorted(per_country.items(), key=lambda kv: -kv[1])[:20]
    print("  top countries:", ", ".join(f"{c} {n:,}" for c, n in top))
    json.dump(per_country, open(os.path.join(ROOT, "data", "places-counts.json"), "w"),
              ensure_ascii=False, indent=1)
    return 0


def cmd_report(a) -> int:
    tot = held = 0
    per: dict[str, int] = {}
    for fn in sorted(os.listdir(CLAIMS)):
        if not fn.endswith(".json"):
            continue
        doc = json.load(open(os.path.join(CLAIMS, fn), encoding="utf-8"))
        for c in doc["claims"]:
            tot += 1
            if c.get("country"):
                held += 1
                per[c["country"]] = per.get(c["country"], 0) + 1
    print(f"claims held: {tot:,}; carrying a country: {held:,} ({held / max(tot,1):.0%}) "
          f"across {len(per)} countries")
    for c, n in sorted(per.items(), key=lambda kv: -kv[1])[:30]:
        print(f"  {c:28} {n:7,}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest"); h.add_argument("--workers", type=int, default=6)
    h.add_argument("--limit", type=int); h.add_argument("--refresh", action="store_true")
    h.set_defaults(fn=cmd_harvest)
    m = sub.add_parser("merge"); m.set_defaults(fn=cmd_merge)
    s = sub.add_parser("sample"); s.add_argument("title"); s.add_argument("--show", type=int, default=25)
    s.set_defaults(fn=cmd_sample)
    r = sub.add_parser("report"); r.set_defaults(fn=cmd_report)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
