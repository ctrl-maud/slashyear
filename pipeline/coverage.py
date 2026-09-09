#!/usr/bin/env python3
"""coverage.py -- does the record actually contain the events people look up?

verify.py proves provenance: every published sentence really is in the revision it cites,
character for character. It has never failed, and it cannot fail on a missing row, because
a row that was never extracted is not there to be checked. That is how this site shipped a
1969 page whose summary said "Apollo 11 lands the first humans on the Moon" above a dated
list that did not contain the landing, and a 1453 with no Fall of Constantinople.

So this is the other test. A fixed list of events that any person would name as the
defining event of its year, each with a phrase that must appear somewhere in that year's
published entries. It is deliberately small and deliberately famous: it is not a sample of
the corpus, it is a tripwire on the ranking and extraction rules, which is where coverage
gets lost. Run it after every build. Grow the list whenever a gap is found -- a case that
once broke is the most valuable case there is.

Usage:
  coverage.py [--site data/site] [--json report.json]
Exit status is 1 if any case is missing, so it can gate a deploy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# year -> phrase that must appear in that year's entries. Alternatives separated by "|".
# Every case marked (regression) was actually missing at some point and is kept forever.
CASES: dict[int, str] = {
    -43: "Caesar",                                    # assassination of Julius Caesar
    -479: "Thermopylae|Salamis|Plataea",
    476: "Romulus Augustulus",
    622: "Mecca|Medina",
    800: "Charlemagne",
    1066: "Battle of Hastings",
    1215: "Magna Carta",
    1258: "Baghdad|Mongol",
    1347: "Black Death|plague",
    1453: "Ottoman forces capture Constantinople",    # (regression) place headings
    1492: "Columbus",
    1517: "Luther|Ninety-five|Ottoman",
    1588: "Spanish Armada|Armada",
    1776: "Declaration of Independence",
    1789: "Storming of the Bastille",
    1815: "Waterloo",
    1859: "Origin of Species",
    1861: "Fort Sumter",
    1865: "Lincoln",
    1869: "Suez Canal",
    1885: "Berlin Conference|Congo",
    1903: "Wright",
    1912: "Titanic",
    1917: "Bolshevik|October Revolution",
    1928: "penicillin",
    1929: "Wall Street|stock market",
    1941: "Attack on Pearl Harbor",                   # (regression) ranking + date header
    1944: "D-Day: Approximately 160,000",             # (regression) length penalty
    1945: 'atomic bomb, codenamed "Little',
    1947: "India|Pakistan",
    1949: "People's Republic of China|NATO",
    1953: "Watson|double helix|DNA",
    1955: "Rosa Parks|Montgomery",
    1957: "Sputnik",
    1963: "Kennedy",
    1969: "Apollo 11 (Buzz Aldrin",                   # (regression) length penalty
    1986: "Chernobyl",
    1989: "Berlin Wall",
    1990: "Mandela",
    1991: "Soviet Union",
    1994: "Rwanda",
    2001: "2,977 people",                             # (regression) 600-char ceiling
    2004: "tsunami",
    2008: "Lehman|financial crisis",
    2011: "Mubarak|Arab Spring|bin Laden",
    2020: "COVID-19|coronavirus",
}

# A day that must carry a specific event, to catch date inheritance breaking. A year can
# hold an event and still file it with no day, which drops it off the calendar pages.
DAY_CASES: list[tuple[str, str]] = [
    ("december-7", "Attack on Pearl Harbor"),
    ("june-6", "D-Day"),
    ("july-20", "Moon|Apollo"),
    ("november-9", "Berlin Wall"),
    ("september-11", "2,977 people|September 11 attacks"),
]


def year_text(site: str, year: int) -> str | None:
    path = os.path.join(site, f"{year}.json")
    if not os.path.exists(path):
        return None
    doc = json.load(open(path, encoding="utf-8"))
    return "\n".join(i["text"] for s in doc.get("sections", []) for i in s["items"])


def date_text(site: str, slug: str) -> str | None:
    path = os.path.join(site, "dates", f"{slug}.json")
    if not os.path.exists(path):
        return None
    return json.dumps(json.load(open(path, encoding="utf-8")), ensure_ascii=False)


def hit(haystack: str | None, phrase: str) -> bool:
    if not haystack:
        return False
    return any(p.strip().lower() in haystack.lower() for p in phrase.split("|"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    missing, checked = [], 0
    for year, phrase in sorted(CASES.items()):
        checked += 1
        if not hit(year_text(a.site, year), phrase):
            missing.append((str(year), phrase))
    for slug, phrase in DAY_CASES:
        checked += 1
        if not hit(date_text(a.site, slug), phrase):
            missing.append((f"/on/{slug}", phrase))

    print(f"coverage: {checked - len(missing)}/{checked} canonical events present")
    for where, phrase in missing:
        print(f"  MISSING  {where:>14}  {phrase}")
    if a.json:
        json.dump({"checked": checked, "missing": [list(m) for m in missing]},
                  open(a.json, "w"), indent=1)
    if missing:
        print("\nA missing case is a coverage bug, not a source gap: check the ranking cap "
              "in build.py, the length ceiling in extract.py, and date_header().")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
