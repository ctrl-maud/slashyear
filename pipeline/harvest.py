#!/usr/bin/env python3
"""harvest.py — pull the source article for every year the site documents.

Every claim on the rebuilt slashyear.com has to be traceable to something a reader can
open and check. This fetches the English Wikipedia article for each year in years.json
and stores the raw wikitext together with the exact revision id it came from, so a
citation can point at a permanent revision rather than a page that may have changed.

Years are stored in astronomical numbering, matching the live site's URLs:
  2025  -> "2025"          (2025 CE)
  9     -> "AD 9"          (9 CE)
  -2999 -> "3000 BC"       (3000 BCE)

Usage:
  harvest.py [--years years.json] [--out data/raw] [--workers 8] [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

API = "https://en.wikipedia.org/w/api.php"
UA = "slashyear-rebuild/1.0 (https://www.slashyear.com; ahmadopsr@gmail.com)"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def titles_for(year: int, exact: bool = False) -> list[str]:
    """Candidate article titles for an astronomical year number, best first."""
    if 0 < year < 10:
        # "2" is the article about the number two, and "AD 1" is a page listing
        # seaplanes and airships. Single-digit years live at "n (year)" or in "0s".
        return [f"{year} (year)", f"AD {year}", "0s"]
    if year > 0:
        # Bare numbers up to ~1600 are often disambiguation pages ("1000", "911");
        # the year article then lives at "AD n".
        if year >= 100:
            return [str(year), f"AD {year}"] if year >= 1000 else [str(year), f"AD {year}"]
        return [f"AD {year}", str(year)]
    bce = abs(year) + 1  # astronomical -2999 is 3000 BCE
    cands = [f"{bce} BC"]
    century = (bce - 1) // 100 + 1
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(
        century % 10 if century % 100 not in (11, 12, 13) else 0, "th"
    )
    if exact:
        return cands
    cands.append(f"{century}{suffix} century BC")
    if bce % 1000 == 0:
        mil = bce // 1000
        msuffix = {1: "st", 2: "nd", 3: "rd"}.get(mil % 10, "th")
        cands.append(f"{mil}{msuffix} millennium BC")
    return cands


def label_for(year: int) -> str:
    return f"{year} CE" if year > 0 else f"{abs(year) + 1} BCE"


# An article about the integer, not the year: "2", "3" and "5" are natural-number
# articles, and "AD 1" is a hand-written list of seaplanes and airships. Both slip past
# the disambiguation template, and both would publish a year page about arithmetic.
NUMBER_RE = re.compile(r"\{\{\s*short description\s*\|\s*Natural number|"
                       r"\{\{\s*infobox number", re.I)
MAYREFER_RE = re.compile(r"'''[^']{1,60}'''[^\n]{0,40}\bmay refer to\b", re.I)

DISAMBIG_RE = re.compile(r"\{\{\s*(disambiguation|disambig|dab|hndis|numberdis|number disambiguation|set index)",
                         re.I)


EVENTS_POINTER = re.compile(r"\{\{For\|[^|}]*events[^|}]*\|([^}|]+)\}\}", re.I)


def events_companion(wikitext: str) -> str | None:
    """Wikipedia is rewriting year articles into prose and moving the dated list into a
    companion "<year> events" article. 1453 is already split that way, and the prose
    article carries no bullets at all -- harvesting it gave us a 1453 with births and
    deaths and no Fall of Constantinople. When an article points at such a companion and
    has no dated list of its own, the companion is the better source for the whole year:
    it carries Events, Births and Deaths in the standard shape."""
    m = EVENTS_POINTER.search(wikitext)
    if not m:
        return None
    # Count only bullets that are NOT under Births/Deaths: the prose article keeps its
    # birth and death lists, so a plain bullet count looks healthy while the entire
    # events half of the year is missing.
    top, event_bullets = None, 0
    for line in wikitext.split("\n"):
        h = re.match(r"^(={2,6})\s*(.+?)\s*\1\s*$", line)
        if h and len(h.group(1)) == 2:
            top = h.group(2).strip().lower()
        elif line.startswith("*") and top and not top.startswith(("birth", "death",
                                                                 "reference", "bibliog")):
            event_bullets += 1
    return m.group(1).strip() if event_bullets < 10 else None


def is_disambiguation(wikitext: str) -> bool:
    """Bare numeric titles like "1000" or "911" are disambiguation pages on Wikipedia;
    the year article lives at "AD 1000". Detect and skip so we never harvest a page
    about a pickup truck as if it were a year."""
    return bool(DISAMBIG_RE.search(wikitext) or NUMBER_RE.search(wikitext)
                or MAYREFER_RE.search(wikitext[:600]))


def fetch(session: requests.Session, title: str) -> dict | None:
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext|revid|displaytitle",
        "redirects": 1,
        "format": "json",
        "formatversion": 2,
    }
    for attempt in range(4):
        try:
            r = session.get(API, params=params, timeout=45)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                return None
            p = d["parse"]
            return {
                "title": p["title"],
                "pageid": p.get("pageid"),
                "revid": p.get("revid"),
                "wikitext": p["wikitext"],
            }
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def harvest_year(year: int, outdir: str, force: bool, exact: bool = False) -> tuple[int, str]:
    path = os.path.join(outdir, f"{year}.json")
    if os.path.exists(path) and not force:
        return year, "cached"
    session = requests.Session()
    session.headers["User-Agent"] = UA
    for title in titles_for(year, exact):
        got = fetch(session, title)
        if got:
            companion = events_companion(got["wikitext"])
            if companion:
                better = fetch(session, companion)
                if better and sum(1 for l in better["wikitext"].split("\n")
                                  if l.startswith("*")) >= 10:
                    got = better
        if got and len(got["wikitext"]) > 500 and not is_disambiguation(got["wikitext"]):
            rec = {
                "year": year,
                "label": label_for(year),
                "source": {
                    "site": "en.wikipedia.org",
                    "title": got["title"],
                    "pageid": got["pageid"],
                    "revid": got["revid"],
                    "url": f"https://en.wikipedia.org/wiki/{got['title'].replace(' ', '_')}",
                    "permalink": f"https://en.wikipedia.org/w/index.php?oldid={got['revid']}",
                    "license": "CC BY-SA 4.0",
                    "retrieved": time.strftime("%Y-%m-%d"),
                },
                "wikitext": got["wikitext"],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False)
            return year, f"ok {got['title']} rev{got['revid']}"
    return year, "MISS"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", default=os.path.join(ROOT, "years.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--exact", action="store_true",
                    help="for BCE years accept only the exact '<n> BC' article, never the "
                         "century or millennium article it would otherwise fall back to")
    a = ap.parse_args()

    years = json.load(open(a.years))
    os.makedirs(a.out, exist_ok=True)
    misses, ok, cached = [], 0, 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(harvest_year, y, a.out, a.force, a.exact): y for y in years}
        for i, fut in enumerate(as_completed(futs), 1):
            y, status = fut.result()
            if status == "MISS":
                misses.append(y)
            elif status == "cached":
                cached += 1
            else:
                ok += 1
            if i % 50 == 0:
                print(f"  {i}/{len(years)} ok={ok} cached={cached} miss={len(misses)}", flush=True)

    print(f"done: ok={ok} cached={cached} miss={len(misses)}")
    if misses:
        print("missing:", sorted(misses))
        json.dump(sorted(misses), open(os.path.join(a.out, "_misses.json"), "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
