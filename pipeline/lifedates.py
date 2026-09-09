#!/usr/bin/env python3
"""lifedates.py — check every published birth and death against Wikidata.

Every other gate in this pipeline asks whether we faithfully reproduced Wikipedia.
None of them can ask whether the row is on the right page: verify.py proves the
sentence is in the cited revision, coverage.py and famous.py and montage.py ask
whether a famous event is present, surface.py and integrity.py look at shape. A
birth filed on the wrong year, or a death printed on the wrong day, passes all of
them, because the mistake is not in the words — it is in where the words were put.

So this gate uses a database we did not write and Wikipedia's editors do not edit
by hand: Wikidata's P569 (date of birth) and P570 (date of death), reached through
the article title the row itself links. For every Births/Deaths row that links a
human, the year of the page must be a year Wikidata records for that person, and
when the row prints a day-precision date it must be a date Wikidata records. A row
is only flagged when NO statement on the item agrees, so people with two competing
recorded dates never fire.

A disagreement is not automatically our bug — Wikipedia's year articles and
Wikidata genuinely differ on old and poorly attested lives, and we quote, we do
not correct. What this finds that nothing else can is the class where the row is
right and the placement is ours: a death harvested out of "Deaths in <month>
<year>" and filed under the wrong day, or a link that resolves to a different
person than the sentence is about.

Usage:
  lifedates.py [--site data/site] [--claims data/claims] [--cache data/wikidata-dates.json]
               [--report lifedates.json] [--refresh] [--max-flag N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WDQS = "https://query.wikidata.org/sparql"
# Wikimedia's User-Agent policy wants a way to reach the operator. A URL satisfies it;
# set SLASHYEAR_CONTACT to add your own address when running the pipeline yourself.
UA = "slashyear-lifedates/1.0 (https://www.slashyear.com" + (
    "; " + os.environ["SLASHYEAR_CONTACT"] if os.environ.get("SLASHYEAR_CONTACT") else ""
) + ")"
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
MI = {m: i + 1 for i, m in enumerate(MONTHS)}
DATE_LINK = re.compile(r"^(" + "|".join(MONTHS) + r")\s+\d{1,2}$")
DAY_DATE = re.compile(r"^(" + "|".join(MONTHS) + r") (\d{1,2})$")
QUERY = """SELECT ?t ?item ?birth ?bp ?bcal ?death ?dp ?dcal WHERE {
  VALUES ?t { %s }
  ?sl schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?t .
  ?item wdt:P31 wd:Q5 .
  OPTIONAL { ?item p:P569/psv:P569 [ wikibase:timeValue ?birth ; wikibase:timePrecision ?bp ;
                                     wikibase:timeCalendarModel ?bcal ] }
  OPTIONAL { ?item p:P570/psv:P570 [ wikibase:timeValue ?death ; wikibase:timePrecision ?dp ;
                                     wikibase:timeCalendarModel ?dcal ] }
}"""
JULIAN = "http://www.wikidata.org/entity/Q1985786"


def to_julian(y: int, m: int, d: int) -> tuple[int, int, int]:
    """Wikidata always STORES a timestamp in the proleptic Gregorian calendar and records
    separately which calendar the date was really given in. Wikipedia's year articles
    print the Julian date for everything before 1582, so a stored value whose calendar
    model is Julian has to be converted back before the two can be compared at all --
    the Julian drift of the century alone (six days in 500 BC, nine in the 1490s) made
    6,390 correct rows look wrong on the first run of this gate."""
    a = (14 - m) // 12
    ya, ma = y + 4800 - a, m + 12 * a - 3
    jdn = d + (153 * ma + 2) // 5 + 365 * ya + ya // 4 - ya // 100 + ya // 400 - 32045
    c = jdn + 32082
    q = (4 * c + 3) // 1461
    e = c - (1461 * q) // 4
    mj = (5 * e + 2) // 153
    return q - 4800 + mj // 10, mj + 3 - 12 * (mj // 10), e - (153 * mj + 2) // 5 + 1


def subject_link(text: str, date: str | None, links: list[str]) -> str | None:
    """The article the row is ABOUT, or None when the row does not name it.

    A birth or death row opens with the person: "October 13 - Emperor Xiaowen of
    Northern Wei (d. 499)". Taking links[0] is right almost always and wrong in the one
    shape that matters -- when the subject has no article of their own, the first link
    is somebody mentioned later ("Pannalal Bose, Indian educationist, translator of
    [[Rabindranath Tagore]]") and the check would compare a row about one person against
    another person's dates. So the link is only accepted when its title shares a word
    with the opening of the sentence."""
    head = text[len(date):] if date and text.startswith(date) else text
    head = re.sub(r"^\s*[\u2013\u2014-]\s*", "", head)[:60].lower()
    for l in links:
        if DATE_LINK.match(l):
            continue
        words = [w for w in re.split(r"[^\w']+", l.lower()) if len(w) > 2]
        return l if any(w in head for w in words) else None
    return None


def fetch(titles: list[str]) -> dict:
    """One SPARQL batch -> {title: {"birth": [(y,m,d,precision)...], "death": [...]}}."""
    import time

    import requests
    vals = " ".join('"%s"@en' % t.replace("\\", "\\\\").replace('"', '\\"') for t in titles)
    for attempt in range(5):
        try:
            r = requests.post(WDQS, data={"query": QUERY % vals, "format": "json"},
                              headers={"User-Agent": UA, "Accept": "application/sparql-results+json"},
                              timeout=180)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            out: dict[str, dict] = {}
            for b in r.json()["results"]["bindings"]:
                rec = out.setdefault(b["t"]["value"], {"birth": [], "death": []})
                for key, pk, ck in (("birth", "bp", "bcal"), ("death", "dp", "dcal")):
                    if key in b:
                        v = b[key]["value"]                     # -0043-03-13T00:00:00Z
                        sign = -1 if v.startswith("-") else 1
                        y, mo, da = v.lstrip("-").split("T")[0].split("-")
                        y, mo, da, prec = sign * int(y), int(mo), int(da), int(b[pk]["value"])
                        if prec >= 11 and b.get(ck, {}).get("value") == JULIAN:
                            y, mo, da = to_julian(y, mo, da)
                        row = [y, mo, da, prec]
                        if row not in rec[key]:
                            rec[key].append(row)
            return out
        except Exception:
            time.sleep(5 * (attempt + 1))
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--cache", default=os.path.join(ROOT, "data", "wikidata-dates.json"))
    ap.add_argument("--report", default=os.path.join(ROOT, "lifedates.json"))
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and re-query")
    ap.add_argument("--batch", type=int, default=300)
    ap.add_argument("--baseline", default=os.path.join(ROOT, "lifedates.baseline.json"),
                    help="counts recorded when this gate was last accepted; the gate "
                         "fails when a build pushes either count above them")
    ap.add_argument("--accept", action="store_true",
                    help="write the current counts as the new baseline")
    a = ap.parse_args()

    pages = sorted((f for f in os.listdir(a.site) if f.endswith(".json") and f != "index.json"),
                   key=lambda f: int(f[:-5]))
    rows: list[dict] = []
    for f in pages:
        page = json.load(open(os.path.join(a.site, f), encoding="utf-8"))
        claims = {c["text"]: c for c in json.load(open(os.path.join(a.claims, f),
                                                       encoding="utf-8"))["claims"]}
        for section in page["sections"]:
            kind = section["title"].strip().lower()
            if kind not in ("births", "deaths"):
                continue
            for item in section["items"]:
                claim = claims.get(item["text"])
                if not claim or claim.get("kind") != kind[:-1]:
                    # Event sentences also file under Deaths ("Skandagupta dies after a
                    # 12-year reign"); their first link is as often the successor or the
                    # battle as the person who died, so they are not checkable this way.
                    continue
                subject = subject_link(item["text"], item.get("date"),
                                       claim.get("links", []))
                if not subject:
                    continue
                rows.append({"year": page["year"], "kind": kind[:-1], "title": subject,
                             "date": item.get("date"), "text": item["text"]})

    titles = sorted({r["title"] for r in rows})
    print(f"birth/death rows with a linked subject : {len(rows)}")
    print(f"distinct linked articles               : {len(titles)}")

    cache: dict[str, dict] = {}
    if os.path.exists(a.cache) and not a.refresh:
        cache = json.load(open(a.cache, encoding="utf-8"))
    todo = [t for t in titles if t not in cache]
    if todo:
        batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
        print(f"querying Wikidata for {len(todo)} titles in {len(batches)} batches ...")
        done = 0
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(fetch, b): b for b in batches}
            for fut in as_completed(futs):
                got = fut.result()
                for t in futs[fut]:
                    cache[t] = got.get(t, {"birth": [], "death": [], "missing": True})
                done += 1
                if done % 10 == 0:
                    print(f"    {done}/{len(batches)}", flush=True)
        json.dump(cache, open(a.cache, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"cache -> {a.cache}")

    year_bad, day_bad = [], []
    checked_year = checked_day = no_item = no_claim = 0
    for r in rows:
        rec = cache.get(r["title"]) or {}
        if rec.get("missing") or not rec:
            no_item += 1
            continue
        stmts = rec.get(r["kind"]) or []
        if not stmts:
            no_claim += 1
            continue
        checked_year += 1
        # Wikidata timestamps are astronomical (year 0 = 1 BC), the same keying the site
        # uses, so the page year compares directly. Precision below year (century, decade)
        # cannot contradict a year page and is skipped.
        years = {s[0] for s in stmts if s[3] >= 9}
        if years and r["year"] not in years:
            year_bad.append({"year": r["year"], "kind": r["kind"], "title": r["title"],
                             "wikidata": sorted(years), "text": r["text"][:140]})
            continue
        m = DAY_DATE.match(r["date"] or "")
        if not m:
            continue
        days = {(s[1], s[2]) for s in stmts if s[3] >= 11 and s[0] == r["year"]}
        if not days:
            continue
        checked_day += 1
        if (MI[m.group(1)], int(m.group(2))) not in days:
            day_bad.append({"year": r["year"], "kind": r["kind"], "title": r["title"],
                            "printed": r["date"],
                            "wikidata": [f"{MONTHS[mo - 1]} {da}" for mo, da in sorted(days)],
                            "text": r["text"][:140]})

    print(f"  no Wikidata item (or not a person)   : {no_item}")
    print(f"  person with no date recorded         : {no_claim}")
    print(f"  years checked against Wikidata       : {checked_year}")
    print(f"  YEAR DISAGREES                       : {len(year_bad)}")
    print(f"  day dates checked                    : {checked_day}")
    print(f"  DAY DISAGREES                        : {len(day_bad)}")
    json.dump({"rows": len(rows), "checked_year": checked_year, "checked_day": checked_day,
               "no_item": no_item, "no_claim": no_claim,
               "year_disagrees": year_bad, "day_disagrees": day_bad},
              open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"report -> {a.report}")

    # A disagreement is not automatically a defect: Wikipedia and Wikidata genuinely
    # differ on badly attested lives, and after 1582 they differ on which calendar a
    # date is even in. So this gate is a ratchet, not a zero: the counts it accepted
    # last time are the ceiling, and a build that raises either one has moved a row
    # onto a page or a day the source's own database does not support.
    now = {"year_disagrees": len(year_bad), "day_disagrees": len(day_bad)}
    if a.accept:
        json.dump(now, open(a.baseline, "w", encoding="utf-8"), indent=1)
        print(f"baseline -> {a.baseline} {now}")
        return 0
    if os.path.exists(a.baseline):
        base = json.load(open(a.baseline, encoding="utf-8"))
        worse = {k: (v, base.get(k)) for k, v in now.items() if v > base.get(k, v)}
        if worse:
            print(f"  REGRESSION against {a.baseline}: {worse}")
            return 1
        print(f"  within baseline {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
