#!/usr/bin/env python3
"""dates.py — cross-cut the year pages into 366 calendar-date pages.

Every published entry already carries the day it happened on (`item.date`, e.g.
"September 7"), because that is how the source article writes it. Nothing new is
written here: the same sentence, the same citation, the same revision id, re-filed
under its day instead of its year.

Why this exists at all: a year page is a near-duplicate of the Wikipedia article it
quotes, and no amount of on-page work makes a duplicate outrank its original. A date
page is not a duplicate of anything — no single Wikipedia article holds "everything
that happened on 7 September across 2,909 years" — and "<month> <day> in history" is
a query people actually type. It also doubles the internal link graph: every year page
now links out to the days it contains and every day links back to the years, which is
the mechanic that makes a reference site crawlable rather than a heap of orphans.

Only day-precision dates qualify. "June" or "June-November" is a month, not a day, and
those entries stay on their year page only.

An event written as a span of days is filed on every day it covers, not only the first.
The source writes "October 24-29 - Wall Street Crash of 1929", so the entry carries
October 24 and the October 29 page -- Black Tuesday, the date the crash is actually
remembered by -- had no crash on it. Spans are capped at 14 days, because past that the
source is describing a campaign rather than an event, and the sentence keeps its printed
span so the reader always sees the range they landed inside.

Usage:
  dates.py [--site data/site] [--out data/site/dates]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
DAY_DATE = re.compile(r"^(" + "|".join(MONTHS) + r") (\d{1,2})$")
# "January 5 - Edward the Confessor dies..." -> the sentence without its date prefix.
LEAD_IN = re.compile(r"^\s*[–—-]\s*")
_M = "|".join(MONTHS)
# The trailing (?![\d,]) is load-bearing: without it "November 5 - 11,000 scientists
# publish a study" reads as the span 5-11 and the study lands on the 6th through the 11th.
SPAN_SAME = re.compile(rf"^({_M})\s+(\d{{1,2}})\s*[–—-]\s*(\d{{1,2}})(?![\d,])")
SPAN_CROSS = re.compile(rf"^({_M})\s+(\d{{1,2}})\s*[–—-]\s*({_M})\s+(\d{{1,2}})(?![\d,])")
MAX_SPAN_DAYS = 14


def span_days(text: str) -> list[tuple[str, int]]:
    """Every (month, day) an entry printed as a span covers, or [] when it is not one.

    "November 22-26", "September 22-October 2". A same-month match only counts when the
    second number is genuinely later and within the month, because "October 3 - 2,000
    people die" has the same shape and means nothing of the kind."""
    m = SPAN_CROSS.match(text)
    if m:
        m1, d1, m2, d2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        i1, i2 = MONTHS.index(m1), MONTHS.index(m2)
        if not (1 <= d1 <= DAYS[i1] and 1 <= d2 <= DAYS[i2]):
            return []
        out, mi, day, guard = [], i1, d1, 0
        while guard <= MAX_SPAN_DAYS:
            out.append((MONTHS[mi], day))
            if mi == i2 and day == d2:
                return out
            day += 1
            if day > DAYS[mi]:
                mi, day = (mi + 1) % 12, 1
            guard += 1
        return []
    m = SPAN_SAME.match(text)
    if m:
        mo, d1, d2 = m.group(1), int(m.group(2)), int(m.group(3))
        i = MONTHS.index(mo)
        if 1 <= d1 < d2 <= DAYS[i] and d2 - d1 <= MAX_SPAN_DAYS:
            return [(mo, d) for d in range(d1, d2 + 1)]
    return []


def slug(month: str, day: int) -> str:
    return f"{month.lower()}-{day}"


def strip_prefix(text: str, date: str) -> str:
    """Drop the date the source printed at the head of the sentence, since the page is
    that date. Anything that does not actually start with the date is left alone."""
    if not text.startswith(date):
        return text
    rest = text[len(date):]
    # "August 13-29 - The 2004 Summer Olympics are held in Athens": the sentence prints a
    # range longer than span_days will file (an Olympics runs 16 days, the span cap is
    # 14), so it is filed on its first day only -- and stripping "August 13" off the front
    # leaves "29 - The 2004 Summer Olympics". Never cut a printed range in half.
    if re.match(r"^\s*[–—-]\s*\d", rest):
        return text
    stripped = LEAD_IN.sub("", rest)
    return stripped if stripped and stripped != rest else text


def kind(section_title: str) -> str:
    t = section_title.strip().lower()
    return "Births" if t == "births" else "Deaths" if t == "deaths" else "Events"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "site", "dates"))
    a = ap.parse_args()

    buckets: dict[str, list[dict]] = {}
    files = sorted((f for f in os.listdir(a.site) if f.endswith(".json") and f != "index.json"),
                   key=lambda f: int(f[:-5]))
    for f in files:
        page = json.load(open(os.path.join(a.site, f), encoding="utf-8"))
        for section in page["sections"]:
            k = kind(section["title"])
            for item in section["items"]:
                if not item.get("date"):
                    continue
                m = DAY_DATE.match(item["date"])
                if not m:
                    continue
                month, day = m.group(1), int(m.group(2))
                if day < 1 or day > DAYS[MONTHS.index(month)]:
                    continue
                # A span keeps the range the source printed, on EVERY day it covers.
                # Stripping "August 28" off "August 28-30 - Second Battle of Bull Run"
                # left the August 28 page carrying a sentence that began "30 - Second
                # Battle of Bull Run", and 613 rows shipped in that shape.
                days = span_days(item["text"])
                text = item["text"] if days else strip_prefix(item["text"], item["date"])
                row = {
                    "year": page["year"],
                    "year_label": page["label"],
                    "kind": k,
                    "section": section["title"],
                    "text": text,
                    "cite": item["cite"],
                }
                if days:
                    row["spanned"] = True
                for mo, dy in (days or [(month, day)]):
                    buckets.setdefault(slug(mo, dy), []).append(row)

    os.makedirs(a.out, exist_ok=True)
    index = []
    total = 0
    for mi, month in enumerate(MONTHS):
        for day in range(1, DAYS[mi] + 1):
            s = slug(month, day)
            rows = sorted(buckets.get(s, []), key=lambda r: r["year"])
            groups = [{"title": g, "items": [r for r in rows if r["kind"] == g]}
                      for g in ("Events", "Births", "Deaths")]
            groups = [g for g in groups if g["items"]]
            years = [r["year"] for r in rows]
            page = {
                "slug": s,
                "label": f"{month} {day}",
                "month": month,
                "day": day,
                "groups": groups,
                "count": len(rows),
                "span": [rows[0]["year_label"], rows[-1]["year_label"]] if rows else None,
                "years": sorted(set(years)),
            }
            json.dump(page, open(os.path.join(a.out, f"{s}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False)
            index.append({"slug": s, "label": page["label"], "month": month, "day": day,
                          "count": page["count"]})
            total += len(rows)

    json.dump({"dates": index, "total": total},
              open(os.path.join(a.out, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)
    empty = [d["slug"] for d in index if d["count"] == 0]
    print(f"  {len(index)} date pages, {total} entries filed"
          f"{', empty: ' + ','.join(empty) if empty else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
