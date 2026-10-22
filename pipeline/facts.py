#!/usr/bin/env python3
"""facts.py — one file per year of the things the year articles do not say.

prices.py, leaders.py and hot100.py each fetch one outside source. This joins them into a
single record per year, which is what the year page's "at a glance" panel, the /born
pages and /api/facts/<year>.json all render from, so the page and the API cannot
disagree. Nothing is estimated: a figure the source does not have for that year is left
out, never interpolated, and every figure carries the source it came from.

Usage:
  facts.py [--extras data/extras] [--first 1800] [--last 2025]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

from leaders_reference import CHECKED

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def load(path: str):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def overlaps(h: dict, year: int) -> bool:
    start = h["start"][:4]
    end = (h.get("end") or "9999")[:4]
    return int(start) <= year <= int(end)


def in_office(state: dict, year: int) -> list[dict]:
    out = []
    for off in state["offices"]:
        holders = [h for h in off["holders"] if overlaps(h, year)]
        if not holders:
            continue
        out.append({
            "role": off["role"],
            "office": off["name"],
            "office_qid": off["qid"],
            "also_head_of_government": bool(off.get("also_head_of_government")),
            "holders": [{k: h[k] for k in ("qid", "name", "start", "end") if k in h}
                        | ({"acting": True} if h.get("acting") else {})
                        | ({"approx": True} if h.get("approx") else {})
                        for h in holders],
        })
    out.sort(key=lambda o: o["role"] != "head_of_state")
    return out


def state_alive(state: dict, year: int) -> bool:
    lo = state.get("from")
    hi = state.get("to")
    return (lo is None or lo <= year) and (hi is None or year <= hi)


def matches(reference: list, year: int, offices: list[dict]) -> bool:
    """The people Wikidata puts in the office this year are exactly the reference's."""
    want = {t for t, lo, hi in reference if lo <= year <= hi}
    got = {h["name"] for o in offices for h in o["holders"]}
    return bool(got) and all(any(t in g for t in want) for g in got) \
        and all(any(t in g for g in got) for t in want)


def leaders_for(doc: dict, year: int) -> list[dict]:
    """The checked offices (leaders_reference.CHECKED) whose Wikidata holders for this
    year agree with the reference list. A year that disagrees is left out."""
    by_name = {s["name"]: s for s in doc["states"]}
    rows: dict[str, dict] = {}
    for chain, role, (first, last), reference in CHECKED:
        if not first <= year <= last:
            continue
        for name in chain:
            s = by_name.get(name)
            if not s or not state_alive(s, year):
                continue
            offices = [o for o in in_office(s, year)
                       if o["role"] == role or (role == "head_of_government" and o["also_head_of_government"])]
            if not offices:
                continue
            if matches(reference, year, offices):
                # One seat recorded under several office items (Monarch of Great Britain,
                # King of Ireland, monarch of the United Kingdom of Great Britain and
                # Ireland in 1801): keep the item that runs latest, the seat's current name.
                offices = [max(offices, key=lambda o: max(h.get("end") or "9999" for h in o["holders"]))]
            if matches(reference, year, offices):
                row = rows.setdefault(s["qid"], {"state": s["name"], "qid": s["qid"], "slug": s["slug"],
                                                 "page": bool(s.get("page")), "offices": []})
                row["offices"] += [o for o in offices if o not in row["offices"]]
            break
    for row in rows.values():
        row["offices"].sort(key=lambda o: o["role"] != "head_of_state")
    return list(rows.values())


def hot100_for(doc: dict, year: int) -> dict | None:
    weeks = [w for w in doc["weeks"] if w["date"].startswith(f"{year}-")]
    if not weeks:
        return None
    songs: dict[tuple[str, str], int] = {}
    order = []
    for w in weeks:
        k = (w["title"], w["artist"])
        if k not in songs:
            order.append(k)
            songs[k] = 0
        songs[k] += 1
    src = next((s for s in doc["sources"] if s["year"] == year), None)
    return {
        "weeks": [{"date": w["date"], "title": w["title"], "artist": w["artist"]} for w in weeks],
        "songs": [{"title": t, "artist": a, "weeks": songs[(t, a)]} for t, a in order],
        "source": src,
    }


def prices_for(doc: dict, year: int) -> dict | None:
    cpi = doc["cpi"]["years"].get(str(year))
    if cpi is None:
        return None
    latest = doc["cpi"]["latest"]
    factor = latest["value"] / cpi
    items = []
    for it in doc["items"]:
        then = it["years"].get(str(year))
        if then is None:
            continue
        items.append({
            "id": it["id"], "label": it["label"], "unit": it["unit"],
            "then": then,
            "then_in_today_dollars": round(then * factor, 4),
            "now": it["latest"]["value"], "now_date": it["latest"]["date"],
            "source": it["source"],
        })
    return {
        "cpi": cpi,
        "cpi_now": latest["value"],
        "cpi_now_date": latest["date"],
        "dollar_today": round(factor, 4),
        "cpi_source": doc["cpi"]["source"],
        "items": items,
    }


def famous_births(claims_dir: str, notability: dict, year: int, n: int = 15) -> list[dict]:
    """The year's births ranked by the length of the person's own article, the same
    proxy notability.py uses for everything else. The published year page shows only a
    handful of births; "born in 1985" is asked about the famous ones."""
    path = os.path.join(claims_dir, f"{year}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    seen = set()
    rows = []
    for c in doc["claims"]:
        if c.get("kind") != "birth" or not c.get("links"):
            continue
        person = c["links"][0]
        if person in seen:
            continue
        seen.add(person)
        src = c.get("source") or doc["source"]
        rows.append((notability.get(person, 0), {
            "text": c["text"],
            "person": person,
            "cite": {"url": src["permalink"] + "#Births", "title": src["title"], "revid": src["revid"]},
        }))
    rows.sort(key=lambda r: -r[0])
    return [r for _, r in rows[:n] if _ > 0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extras", default=os.path.join(ROOT, "data", "extras"))
    ap.add_argument("--first", type=int, default=1800)
    ap.add_argument("--last", type=int, default=2025)
    a = ap.parse_args()

    prices = load(os.path.join(a.extras, "prices.json"))
    leaders = load(os.path.join(a.extras, "leaders.json"))
    hot100 = load(os.path.join(a.extras, "hot100.json"))
    notability = load(os.path.join(ROOT, "data", "notability.json")) or {}
    claims = os.path.join(ROOT, "data", "claims")
    out = os.path.join(a.extras, "facts")
    os.makedirs(out, exist_ok=True)

    index = []
    for year in range(a.first, a.last + 1):
        rec: dict = {"year": year}
        if prices:
            pop = prices["population"]["years"].get(str(year))
            if pop:
                rec["population"] = {"value": pop, "source": prices["population"]["source"]}
            p = prices_for(prices, year)
            if p:
                rec["prices"] = p
        if leaders:
            key = leaders_for(leaders, year)
            if key:
                rec["leaders"] = {"key": key, "source": leaders["source"],
                                  "checked": "each office-year matches an independent list of holders"}
        if hot100:
            h = hot100_for(hot100, year)
            if h:
                rec["hot100"] = h
        if len(rec) == 1:
            continue
        births = famous_births(claims, notability, year)
        if births:
            rec["births"] = births
        with open(os.path.join(out, f"{year}.json"), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, separators=(",", ":"))
        index.append({
            "year": year,
            "population": "population" in rec,
            "prices": "prices" in rec,
            "leaders": len(rec.get("leaders", {}).get("key", [])),
            "hot100": "hot100" in rec,
        })
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"built": dt.date.today().isoformat(), "years": index}, fh,
                  separators=(",", ":"))
    print(f"facts: {len(index)} years; prices {sum(r['prices'] for r in index)}, "
          f"leaders {sum(bool(r['leaders']) for r in index)}, hot100 {sum(r['hot100'] for r in index)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
