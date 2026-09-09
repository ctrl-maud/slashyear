#!/usr/bin/env python3
"""reclean.py -- re-render selected claims from their stored wikitext, in place.

extract.py rewrites data/claims from scratch, which ERASES the themes classify.py wrote
into the same files (README, "the traps that bite hardest"). When a cleaner bug is fixed
and the wikitext itself has not changed, the whole re-extract is not needed: every claim
already carries the exact source line in `raw`, so the affected claims can be re-rendered
with the current cleaner and written back, leaving theme, score, weight and every other
field untouched.

  python pipeline/reclean.py --match '\\{\\{\\s*(convert|cvt)\\s*\\|'          # dry run
  python pipeline/reclean.py --match '...' --apply

Prints every text that changes so the diff is reviewed before it is written.
"""
from __future__ import annotations
import argparse, glob, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import clean_line, parse_date, strip_date_lead   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rerender(c: dict) -> dict | None:
    """The tail of extract.extract(), applied to one stored claim."""
    sentence, links, ok = clean_line(c["raw"])
    if c.get("date_prefix") and sentence:
        sentence = f"{c['date_prefix']} – {sentence}"
    if not ok or len(sentence) < 30 or len(sentence) > 1200:
        return None
    if not re.search(r"[a-zA-Z]{3}", sentence):
        return None
    date_label, mon, day = parse_date(sentence, c["section_trail"])
    body = strip_date_lead(sentence) if date_label else sentence
    if len(body) < 20:
        return None
    year = int(c["id"].split(":", 1)[0])
    out = dict(c)
    out.update({"id": f"{year}:{hashlib.sha1(sentence.encode()).hexdigest()[:12]}",
                "date": date_label, "month": mon, "day": day,
                "text": sentence, "body": body, "links": links[:12]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--match", required=True, help="regex; a claim is re-rendered when its raw matches")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()

    rx = re.compile(a.match, re.I)
    touched = changed = dropped = 0
    shown = 0
    for path in sorted(glob.glob(os.path.join(a.claims, "*.json"))):
        doc = json.load(open(path, encoding="utf-8"))
        dirty = False
        for i, c in enumerate(doc["claims"]):
            if not rx.search(c.get("raw", "")):
                continue
            touched += 1
            new = rerender(c)
            if new is None:
                dropped += 1
                print(f"  ! {os.path.basename(path)}: would no longer render -- {c['text'][:90]!r}")
                continue
            if new["text"] == c["text"]:
                continue
            changed += 1
            dirty = True
            if shown < a.show:
                shown += 1
                print(f"  - {c['text'][:150]}")
                print(f"  + {new['text'][:150]}")
            doc["claims"][i] = new
        if dirty and a.apply:
            json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"reclean: {touched:,} claims matched, {changed:,} rendered differently, "
          f"{dropped} would drop out{'' if a.apply else '  (dry run -- pass --apply)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
