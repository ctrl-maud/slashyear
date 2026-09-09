#!/usr/bin/env python3
"""deaths.py — the deaths Wikipedia moved out of the year article.

Every year page from 1977 on had **no deaths on it at all**, and nobody noticed for two
coverage audits, because provenance testing cannot see an absence and the famous-events
sweep tests events. Elvis Presley is not on 1977, Steve Jobs is not on 2011, Nelson
Mandela is not on 2013.

The cause is a change in how Wikipedia is organised, not a bug in reading it. Up to 1976
the year article carries its own Deaths section. From 1977 the article says
`{{Main|Deaths in 1977}}` and the list lives in a separate article — "Deaths in 1977" and
"Deaths in 1978" as one page per year, and from 1979 as twelve pages per year, "Deaths in
January 1979" and so on. This harvests those 566 articles, parses them, and merges the
result into the year's claims with each claim carrying its own source, because the
citation on a bullet must point at the revision that bullet actually came from.

Two source layouts, both handled:

  A  year list   * [[January 2]] – [[Erroll Garner]], American musician (b. [[1921]])
                 with "** name" lines nested under a bare "* [[January 14]]" bullet
  B  month list  ===1===        (a day heading)
                 *[[Moses Anderson]], 84, American Roman Catholic prelate, cardiac arrest.

In layout B the line carries no date, so the day comes from the heading it sits under and
is prefixed for display exactly the way nested bullets already are: `date_prefix` is shown,
`raw` stays the untouched source line, and verify.py re-derives both.

Run it AFTER extract.py (which rewrites data/claims) and BEFORE classify.py.

Usage:
  deaths.py [--from 1977] [--to 2025] [--refresh] [--workers 4]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import clean_line, LINK_RE  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
API = "https://en.wikipedia.org/w/api.php"
# Wikimedia's User-Agent policy wants a way to reach the operator. A URL satisfies it;
# set SLASHYEAR_CONTACT to add your own address when running the pipeline yourself.
UA = "slashyear-deaths/1.0 (https://www.slashyear.com" + (
    "; " + os.environ["SLASHYEAR_CONTACT"] if os.environ.get("SLASHYEAR_CONTACT") else ""
) + ")"
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def fetch(title: str) -> dict | None:
    """One article: resolved title, revision id and wikitext, or None if it redirects
    away (which is how "Deaths in 2013" behaves — it points at an index of months)."""
    import time

    import requests
    s = requests.Session()
    s.headers["User-Agent"] = UA
    for attempt in range(4):
        try:
            r = s.get(API, params={"action": "query", "prop": "revisions",
                                   "rvprop": "content|ids", "rvslots": "main",
                                   "titles": title, "redirects": 1,
                                   "format": "json", "formatversion": 2}, timeout=60)
            if r.status_code in (429, 503):
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            page = r.json()["query"]["pages"][0]
            if page.get("missing") or page.get("title") != title:
                return None
            rev = page["revisions"][0]
            return {
                "source": {
                    "site": "en.wikipedia.org",
                    "title": page["title"],
                    "pageid": page["pageid"],
                    "revid": rev["revid"],
                    "url": "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_"),
                    "permalink": f"https://en.wikipedia.org/w/index.php?oldid={rev['revid']}",
                    "license": "CC BY-SA 4.0",
                    "retrieved": dt.date.today().isoformat(),
                },
                "wikitext": rev["slots"]["main"]["content"],
            }
        except Exception:
            time.sleep(2 ** attempt)
    return None


def harvest_year(year: int) -> list[dict]:
    whole = fetch(f"Deaths in {year}")
    if whole:
        return [whole]
    out = []
    for m in MONTHS:
        doc = fetch(f"Deaths in {m} {year}")
        if doc:
            out.append(doc)
    return out


# --- parsing ------------------------------------------------------------------------

DAY_HEADING = re.compile(r"^=+\s*(\d{1,2})\s*=+\s*$")
MONTH_HEADING = re.compile(r"^=+\s*(" + "|".join(MONTHS) + r")(?:\s+\d{4})?\s*=+\s*$")
DATE_LINE = re.compile(r"^(" + "|".join(MONTHS) + r")\s+(\d{1,2})\b")


def parse_doc(doc: dict, year: int) -> list[dict]:
    """Both layouts, one pass. A line is a death when we know its day."""
    w = doc["wikitext"]
    month = None
    day = None
    out = []
    for raw_line in w.split("\n"):
        line = raw_line.rstrip()
        hm = MONTH_HEADING.match(line)
        if hm:
            month, day = hm.group(1), None
            continue
        hd = DAY_HEADING.match(line)
        if hd and month:
            d = int(hd.group(1))
            day = d if 1 <= d <= DAYS[MONTHS.index(month)] else None
            continue
        if re.match(r"^=+[^=]", line):        # any other heading ends the run
            if not MONTH_HEADING.match(line):
                day = None
            continue
        if not line.startswith("*"):
            continue
        body = line.lstrip("*").strip()
        if len(body) < 20:
            continue
        sentence, links, ok = clean_line(body)
        if not ok or not sentence:
            continue
        # layout A prints the date in the line itself
        m = DATE_LINE.match(sentence)
        inherited = None
        if m:
            month_here, day_here = m.group(1), int(m.group(2))
            date_label = f"{month_here} {day_here}"
            mon, dy = MONTHS.index(month_here) + 1, day_here
            text = sentence
            # A line that is only a date ("* [[January 14]]"), or a date plus a group
            # heading that ends in a colon ("October 20 - Three members of Lynyrd
            # Skynyrd, killed in plane crash:"), is a header for the names nested under
            # it, not an entry. Publishing it puts a bullet on the page that ends in a
            # colon and names nobody. Its day is what the children inherit.
            if len(sentence) <= len(date_label) + 3 or sentence.rstrip().endswith(":"):
                month, day = month_here, day_here
                continue
        elif month and day:
            inherited = f"{month} {day}"
            date_label, mon, dy = inherited, MONTHS.index(month) + 1, day
            text = f"{inherited} – {sentence}"
        else:
            continue
        if sentence.rstrip().endswith(":"):     # group heading, see above
            continue
        if len(text) < 30 or len(text) > 1200 or not re.search(r"[a-zA-Z]{3}", text):
            continue
        out.append({
            "id": f"{year}:d{hashlib.sha1(text.encode()).hexdigest()[:12]}",
            "kind": "death",
            "date": date_label,
            "month": mon,
            "day": dy,
            "section_trail": ["Deaths", date_label.split()[0]],
            "text": text,
            "body": sentence,
            "links": links[:12],
            "raw": body,
            "date_prefix": inherited,
            "source": doc["source"],
            "from_deaths_list": True,
            # classify.py assigns Births/Deaths from `kind` without embedding anything;
            # setting it here means a re-merge does not have to wait on the GPU.
            "theme": "Deaths",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="y0", type=int, default=1977)
    ap.add_argument("--to", dest="y1", type=int, default=2025)
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw", "deaths"))
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--refresh", action="store_true", help="re-download cached articles")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    os.makedirs(a.raw, exist_ok=True)
    years = [y for y in range(a.y0, a.y1 + 1)]

    todo = [y for y in years
            if a.refresh or not os.path.exists(os.path.join(a.raw, f"{y}.json"))]
    if todo:
        print(f"harvesting deaths lists for {len(todo)} years ...")
        done = 0
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(harvest_year, y): y for y in todo}
            for fut in as_completed(futs):
                y = futs[fut]
                docs = fut.result()
                json.dump({"year": y, "docs": docs},
                          open(os.path.join(a.raw, f"{y}.json"), "w", encoding="utf-8"),
                          ensure_ascii=False)
                done += 1
                if done % 5 == 0:
                    print(f"    {done}/{len(todo)} years", flush=True)

    total_added = 0
    thin = []
    for y in years:
        rawp = os.path.join(a.raw, f"{y}.json")
        claimp = os.path.join(a.claims, f"{y}.json")
        if not os.path.exists(rawp) or not os.path.exists(claimp):
            continue
        rec = json.load(open(rawp, encoding="utf-8"))
        claims_doc = json.load(open(claimp, encoding="utf-8"))
        kept = [c for c in claims_doc["claims"] if not c.get("from_deaths_list")]
        seen = {c["text"].lower()[:120] for c in kept}
        added = []
        for doc in rec["docs"]:
            for c in parse_doc(doc, y):
                k = c["text"].lower()[:120]
                if k in seen:
                    continue
                seen.add(k)
                added.append(c)
        claims_doc["claims"] = kept + added
        json.dump(claims_doc, open(claimp, "w", encoding="utf-8"), ensure_ascii=False)
        total_added += len(added)
        if len(added) < 20:
            thin.append((y, len(added), len(rec["docs"])))

    print(f"merged {total_added:,} deaths into {len(years)} years "
          f"({total_added // max(len(years), 1):,} per year)")
    if thin:
        print("  thin years (year, deaths added, source articles):", thin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
