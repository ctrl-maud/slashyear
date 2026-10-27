#!/usr/bin/env python3
"""facts.py — one file per year of the things the year articles do not say.

prices.py, stateleaders.py and hot100.py each fetch one outside source. This joins them into a
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


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def load(path: str):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# The states the year page's panel names first, by the article each state's entry in the
# Wikipedia lists links to (the list's own heading where an entry has no link).
KEY = [
    ("United States", {"United States"}),
    ("United Kingdom", {"United Kingdom", "United Kingdom of Great Britain and Ireland", "Kingdom of Great Britain"}),
    ("France", {"France", "French First Republic", "First French Empire", "Bourbon Restoration in France",
                "July Monarchy", "French Second Republic", "Second French Empire", "French Third Republic",
                "Vichy France", "Provisional Government of the French Republic", "French Fourth Republic"}),
    ("Germany", {"Germany", "West Germany", "East Germany", "German Empire", "Weimar Republic", "Nazi Germany",
                 "Allied-occupied Germany", "North German Confederation", "Confederation of the Rhine"}),
    ("Russia", {"Russia", "Russian Empire", "Russian Republic", "Russian Soviet Federative Socialist Republic",
                "Soviet Union"}),
    ("China", {"China", "Qing dynasty", "Republic of China (1912–49)", "Empire of China (1915–16)"}),
    ("Japan", {"Japan", "Empire of Japan", "Tokugawa shogunate"}),
    ("India", {"India"}),
]


def leaders_for(doc: dict, year: int) -> dict | None:
    """Every state's office holders in one year, from stateleaders.json: each holder with
    the line quoted from the Wikipedia list and the Wikidata item that vouched for it."""
    src = None
    for s in doc["sources"]:
        if s["first"] <= year <= s["last"]:
            src = s                       # the later article wins where two cover a year
    if src is None:
        return None
    states: dict[str, dict] = {}
    for r in doc["rows"]:
        if year not in r["years"]:
            continue
        st = states.get(r["state"])
        if st is None:
            link = r["state_link"] or r["state"]
            st = states[r["state"]] = {
                "state": r["state"], "region": r["region"],
                "country": (r["group"] or link).split(":")[0].strip(),
                "wikipedia": r["state_link"],
                "key": next((k for k, links in KEY if link in links), None),
                "holders": [],
            }
        since = min(a for a, b in r["terms"] if a <= year <= (b if b is not None else year))
        h = next((h for h in st["holders"] if h["person"] == r["person"] and h["quote"] == r["quote"]), None)
        if h is None:
            st["holders"].append({"name": r["name"], "person": r["person"], "qid": r["qid"],
                                  "title": r["title"], "office": r["office"], "quote": r["quote"], "_since": since})
        elif r["title"] and r["title"] not in (h["title"] or ""):
            h["title"] = f"{h['title']}; {r['title']}" if h["title"] else r["title"]
    # Within one post, holders in the order they took it that year (the list gives a
    # returning holder's line once, at his first term: Trump before Biden in 2025).
    for st in states.values():
        posts = list(dict.fromkeys((h["title"] or h["office"] or "").lower() for h in st["holders"]))
        st["holders"].sort(key=lambda h: (posts.index((h["title"] or h["office"] or "").lower()), h["_since"]))
        for h in st["holders"]:
            del h["_since"]
    # A ruler whose reign the list carries under two headings of one country (Hirohito
    # under the Empire of Japan and the State of Japan) is one entry, not two.
    out = []
    for st in states.values():
        mine = {h["person"] for h in st["holders"]}
        if any(o["country"] == st["country"] and mine <= {h["person"] for h in o["holders"]} for o in out):
            continue
        out = [o for o in out if not (o["country"] == st["country"]
                                      and {h["person"] for h in o["holders"]} < mine)] + [st]
    if not out:
        return None
    return {
        "states": out,
        "source": {"name": "Wikipedia", "title": src["title"], "revid": src["revid"], "url": src["permalink"],
                   "license": "CC BY-SA 4.0", "retrieved": doc["built"]},
        "checked": "Each holder is quoted from the list and kept for this year only where the person's own "
                   "Wikidata record holds the same post over the same term, to within a year.",
    }


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


def nobel_for(doc: dict, year: int) -> dict | None:
    """The year's Nobel laureates, each kept only where Wikidata independently records the
    same prize in the same year (staging build in data/extras/nobel.json)."""
    prizes = doc["years"].get(str(year))
    none = doc.get("not_awarded", {}).get(str(year))
    if not prizes and not none:
        return None
    out = {"prizes": [{k: p[k] for k in ("category", "name", "kind", "qid", "motivation", "share", "nobel_url", "prize_status") if p.get(k)}
                      for p in prizes or []],
           "source": doc["source"], "checked_against": doc["checked_against"]}
    if none:
        out["not_awarded"] = none
    return out


def official_for(doc: dict, year: int) -> dict | None:
    """Annual values of the official series (data/extras/official.json), each with its
    publisher and the cross-check it passed. A series with no value for the year is absent."""
    out = {}
    for sid, s in doc["series"].items():
        v = s["annual"].get(str(year))
        if v is None:
            continue
        out[sid] = {"name": s["name"], "unit": s["unit"], "value": v, "annual_method": s.get("annual_method"),
                    "source": {"publisher": s["publisher"], "url": s["url"], "license": s["license"]}}
    return out or None


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
    leaders = load(os.path.join(a.extras, "stateleaders.json"))
    hot100 = load(os.path.join(a.extras, "hot100.json"))
    nobel = load(os.path.join(a.extras, "nobel.json"))
    official = load(os.path.join(a.extras, "official.json"))
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
            lead = leaders_for(leaders, year)
            if lead:
                rec["leaders"] = lead
        if hot100:
            h = hot100_for(hot100, year)
            if h:
                rec["hot100"] = h
        if official:
            o = official_for(official, year)
            if o:
                rec["official"] = o
        if nobel:
            n = nobel_for(nobel, year)
            if n:
                rec["nobel"] = n
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
            "leaders": len(rec.get("leaders", {}).get("states", [])),
            "hot100": "hot100" in rec,
            "nobel": len(rec.get("nobel", {}).get("prizes", [])),
            "official": sorted(rec.get("official", {})),
        })
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"built": dt.date.today().isoformat(), "years": index}, fh,
                  separators=(",", ":"))
    print(f"facts: {len(index)} years; prices {sum(r['prices'] for r in index)}, "
          f"leaders {sum(bool(r['leaders']) for r in index)}, hot100 {sum(r['hot100'] for r in index)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
