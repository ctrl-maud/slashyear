#!/usr/bin/env python3
"""play.py — the daily guess-the-year puzzles.

A reference site is visited once per question and then forgotten. A daily puzzle is the
one format that gives a reader a reason to come back tomorrow, and it needs nothing the
corpus does not already have: five sourced lines from one year, shown one at a time, and
the reader guesses the year.

The schedule is fixed at build time and published as one file per month, so the page is a
static fetch and every player gets the same puzzle on the same date. Rules for a clue:

  - an event, never a birth or death (a lifespan in parentheses gives the year away);
  - no number of three or more digits anywhere in it, since that is usually the year, a
    neighbouring year or an anniversary that dates it, and no short form of one ("Expo
    '92", "the 60s", "50th anniversary");
  - long enough to stand alone, short enough to read on a phone.

Clues run from the sections that are hardest to place (culture, science, crime) to the
ones that date a year at a glance (geopolitics, war), so each reveal makes it easier.

Usage:
  play.py [--site data/site] [--out data/extras/play] [--start 2026-10-22] [--days 400]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLUES = 5
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DASH = r"\s*[–—-]\s*"
DAY = r"\d{1,2}(?:st|nd|rd|th)?"
# "May 24 – ", "24 May – ", "July 29–August 21 – ", "May 8-9 - ", "June 28 (July 8 N.S.) – ",
# "Approximate date – ": the dating furniture the year articles put in front of a sentence.
DATE_PREFIX = re.compile(
    rf"^(?:(?:{DAY}(?:{DASH}{DAY})?\s+)?{MONTH}(?:\s+{DAY})?(?:{DASH}(?:{MONTH}\s*)?{DAY}(?:\s+{MONTH})?)?"
    rf"(?:\s*\([^)]*\))?|(?:Approximate|Probable) date|(?:Early|Late|Mid)?\s*(?:Spring|Summer|Autumn|Winter|{MONTH}))"
    rf"{DASH}")
LEFTOVER = re.compile(rf"^[^:]{{0,40}}\b{MONTH}\b[^:]{{0,15}}[–—-]|^c\.\s")
SHORT_YEAR = re.compile(r"['’‘]\d{2}\b|\b\d{2}s\b")
ANNIVERSARY = re.compile(r"\d+(?:st|nd|rd|th)\s+(?:anniversary|birthday)", re.I)
NUMBER = re.compile(r"\d{3,}")
EASY = ("Geopolitics", "Conflict", "Exploration")
SKIP = ("Births", "Deaths")
# Where the puzzle years come from: mostly the last two centuries, which a reader can
# reason about, with older years mixed in so the range is not a give-away.
BANDS = [((1800, 2025), 0.6), ((1500, 1799), 0.25), ((1000, 1499), 0.15)]


def candidates(page: dict) -> list[dict]:
    out = []
    for sec in page["sections"]:
        if sec["title"] in SKIP:
            continue
        for it in sec["items"]:
            text = it["text"]
            for _ in range(3):
                text = DATE_PREFIX.sub("", text).strip()
            if NUMBER.search(text) or not 50 <= len(text) <= 240:
                continue
            # A prefix the pattern did not fully take ("June 4 or June 5 –", "(N.S.) –")
            # leaves dating furniture at the head of the clue; drop the line instead.
            if LEFTOVER.match(text) or not text[0].isupper():
                continue
            if "century" in text.lower() or SHORT_YEAR.search(text) or ANNIVERSARY.search(text):
                continue
            out.append({
                "text": text,
                "easy": sec["title"].startswith(EASY),
                "cite": it["cite"],
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "extras", "play"))
    ap.add_argument("--start", default="2026-10-22")
    ap.add_argument("--days", type=int, default=400)
    a = ap.parse_args()

    pool: dict[int, list[dict]] = {}
    for f in os.listdir(a.site):
        if not f.endswith(".json") or f == "index.json":
            continue
        y = int(f[:-5])
        if not 1000 <= y <= 2025:
            continue
        with open(os.path.join(a.site, f), encoding="utf-8") as fh:
            c = candidates(json.load(fh))
        if len(c) >= CLUES:
            pool[y] = c

    rng = random.Random(f"slashyear-play-{a.start}")
    bands = []
    for (lo, hi), share in BANDS:
        ys = [y for y in pool if lo <= y <= hi]
        rng.shuffle(ys)
        bands.append([ys, share])
    days = []
    for i in range(a.days):
        live = [b for b in bands if b[0]]
        if not live:
            break
        # The first fortnight is what a new player meets; keep it in years they can place.
        pick = bands[0] if i < 14 and bands[0][0] else rng.choices(live, weights=[b[1] for b in live])[0]
        days.append(pick[0].pop())

    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):
        os.remove(os.path.join(a.out, f))
    start = dt.date.fromisoformat(a.start)
    months: dict[str, list[dict]] = {}
    for i, y in enumerate(days):
        c = pool[y][:]
        rng.shuffle(c)
        hard = [x for x in c if not x["easy"]]
        easy = [x for x in c if x["easy"]]
        chosen = (hard[: CLUES - min(2, len(easy))] + easy)[:CLUES]
        chosen.sort(key=lambda x: x["easy"])
        day = start + dt.timedelta(days=i)
        months.setdefault(day.isoformat()[:7], []).append({
            "number": i + 1,
            "date": day.isoformat(),
            "year": y,
            "clues": [{"text": x["text"], "cite": x["cite"]} for x in chosen],
        })
    # One file per month, not per day: Pages caps a deployment at 20,000 files and the
    # site is already close to it.
    for month, puzzles in months.items():
        with open(os.path.join(a.out, f"{month}.json"), "w", encoding="utf-8") as fh:
            json.dump({"month": month, "puzzles": puzzles}, fh, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(a.out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"start": a.start, "days": len(days), "clues": CLUES}, fh)
    eras = {f"{lo}-{hi}": sum(lo <= y <= hi for y in days) for (lo, hi), _ in BANDS}
    print(f"play: {len(days)} puzzles from {a.start}, pool {len(pool)} years, {eras}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
