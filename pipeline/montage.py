#!/usr/bin/env python3
"""montage.py -- the year's own editors' picks must be on the year's page.

coverage.py and famous.py test 384 cases that *I* chose, so they can only ever find the
holes I thought to look for. This test writes its own cases out of the data: every year
article from 1900 on carries a photo montage whose caption names the handful of events
that year's editors chose to stand for the year. That caption is an importance signal we
did not invent.

The check: for each clause of the caption, find the best-matching PUBLISHED row and the
best-matching row we harvested and then DROPPED. If the dropped row matches the caption
clearly better than anything we published, the page is missing an event its own source
article says defined the year -- which is how 1940 lost the Dunkirk evacuation and the
Katyn massacre, 1944 the 20 July plot, 1961 the Bay of Pigs and 1971 the Pentagon Papers,
all while every other test passed.

The scorer here is deliberately NOT build.montage_picks: a test that reuses the selector's
own matcher would agree with it by construction.

  python pipeline/montage.py [--site data/site] [--claims data/claims] [--json report]
"""
from __future__ import annotations
import argparse, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP = set("the a an of and in on to for with at by from is are was were as its his her "
           "their this that it after before during over under into".split())


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']{4,}", text.lower()) if w not in STOP}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--gap", type=float, default=0.12,
                    help="how much better a dropped row must match before it is a failure")
    ap.add_argument("--floor", type=float, default=0.3,
                    help="a dropped row below this score is a coincidence, not the event")
    ap.add_argument("--json", dest="report",
                    default=os.path.join(ROOT, "montage.json"))
    a = ap.parse_args()

    fails, notes = [], []
    clauses = pages = 0
    for path in sorted(glob.glob(os.path.join(a.site, "[0-9-]*.json"))):
        doc = json.load(open(path, encoding="utf-8"))
        if doc.get("lead_from") != "article image footer":
            continue
        pages += 1
        year = doc["year"]
        published = {i["text"] for s in doc["sections"] for i in s["items"]}
        allc = json.load(open(os.path.join(a.claims, f"{year}.json"),
                              encoding="utf-8"))["claims"]
        dropped = [c["text"] for c in allc if c["text"] not in published]
        for clause in re.split(r"[;–]|\s+—\s+", doc["lead"]):
            clause = clause.strip()
            keys = words(clause)
            if len(clause) < 25 or len(keys) < 3:
                continue
            clauses += 1
            def score(t: str) -> float:
                return len(keys & words(t)) / len(keys)
            best_pub = max((score(t) for t in published), default=0.0)
            cand = max(((score(t), t) for t in dropped), default=(0.0, ""))
            if cand[0] >= a.floor and cand[0] - best_pub >= a.gap \
                    and len(keys & words(cand[1])) >= 2:
                fails.append(f"{year}: caption says {clause[:70]!r} -- best published row "
                             f"scores {best_pub:.2f}, but a DROPPED row scores {cand[0]:.2f}: "
                             f"{cand[1][:90]!r}")
            elif best_pub < 0.2 and cand[0] < 0.2:
                notes.append(f"{year}: {clause[:60]!r} is in the caption and in no bullet "
                             f"of the article at all")

    print(f"montage: {clauses:,} caption clauses across {pages} year pages")
    if notes:
        print(f"  . {len(notes)} clauses name something the source article never lists "
              f"as a bullet (nothing to publish): e.g. {notes[0]}")
    if a.report:
        json.dump({"pages": pages, "clauses": clauses, "failures": fails, "notes": notes},
                  open(a.report, "w", encoding="utf-8"), indent=1)
    if fails:
        print(f"montage: {len(fails)} FAILURES")
        for f in fails[:25]:
            print("  x " + f)
        return 1
    print("montage: every caption event the article lists is published")
    return 0


if __name__ == "__main__":
    sys.exit(main())
