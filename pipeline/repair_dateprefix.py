"""Corpus reconcile for inherited date prefixes, 2026-09-10.

The OWN_DAY rule (a nested bullet that already opens with its own day never inherits the
parent bullet's date) was added to extract.py after most of the corpus was extracted, so the
stored claims disagreed with what extract.py produces today in both directions: legacy rows
with the parent date baked into `text` on top of the child's own day (published as a double
date — "August 3 – August 3 – Jeffrey Amherst..."), and newer rows that skipped the prefix
in `text` but still stored `date_prefix`, which verify.py replays onto the re-derived line.

This makes every claim self-consistent by re-deriving from its own `raw` wikitext, exactly
the way verify.py replays it (date_prefix, then month_prefix, then context_suffix):

  1. strip a baked-in prefix when the remainder opens with its own day, re-parsing
     date/body the way extract.py does;
  2. then set `date_prefix` to whatever value actually reproduces `text` from
     clean_line(raw) — the leading "Month Day" when the text carries one the raw does
     not, None when the text is the raw line as-is.

Rows that reproduce neither way are left untouched and counted; they were already drifted
before this script existed and verify.py will keep naming them.

Idempotent; safe to re-run.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import MONTH_RE, OWN_DAY, clean_line, parse_date, strip_date_lead  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = re.compile(rf"^((?:{MONTH_RE})\s+\d{{1,2}}) – ")


def compose(redone: str, dp: str | None, mp: str | None, ctx: str | None) -> str:
    if dp:
        redone = f"{dp} – {redone}"
    if mp:
        redone = f"{mp} {redone}"
    if ctx:
        redone = f"{redone} — {ctx}"
    return redone


def main() -> int:
    stripped = restored = cleared = drifted = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "claims", "*.json"))):
        d = json.load(open(path, encoding="utf-8"))
        changed = False
        for c in d["claims"]:
            mp, ctx = c.get("month_prefix"), c.get("context_suffix")
            redone, _links, ok = clean_line(c["raw"])
            if not ok or not redone:
                continue
            # 1. Un-double legacy rows: prefix baked into text over the child's own day.
            m = PREFIX.match(c["text"])
            if (m and c.get("date_prefix") == m.group(1)
                    and OWN_DAY.match(c["text"][m.end():])
                    and compose(redone, None, mp, ctx) == c["text"][m.end():]):
                rest = c["text"][m.end():]
                c["text"] = rest
                c["date"], c["month"], c["day"] = parse_date(rest, c.get("section_trail"))
                c["body"] = strip_date_lead(rest) if c["date"] else rest
                stripped += 1
                changed = True
                print(f"  strip {d['year']}: {rest[:90]}")
            # 2. Make date_prefix agree with what reproduces `text` from `raw`.
            if compose(redone, None, mp, ctx) == c["text"]:
                dp = None
            else:
                m = PREFIX.match(c["text"])
                if m and compose(redone, m.group(1), mp, ctx) == c["text"]:
                    dp = m.group(1)
                else:
                    drifted += 1
                    continue
            if c.get("date_prefix") != dp:
                if dp:
                    restored += 1
                else:
                    cleared += 1
                c["date_prefix"] = dp
                changed = True
        if changed:
            json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"double prefixes stripped: {stripped}; prefixes restored: {restored}; "
          f"cleared: {cleared}; still drifted (left alone): {drifted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
