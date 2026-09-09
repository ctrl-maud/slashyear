#!/usr/bin/env python3
"""cross.py — cut the year corpus along the three axes Wikipedia does not publish.

`dates.py` already re-files every entry by the day it names. This does the same trick
three more times, and for the same reason: a year page is a near-duplicate of the
Wikipedia article it quotes, and a duplicate never outranks its original. A page that
answers a question no single article answers is not a duplicate of anything.

  1. DECADES and CENTURIES. Not written as prose -- they are the navigation spine the
     site was missing. Every year was reachable only from one 1MB index page, which is
     the worst possible shape for a crawler: 2,909 links deep on a single URL and no
     hierarchy at all. Century -> decade -> year is three hops with ~50 links each.
  2. TOPICS. This is the half of the site that is genuinely ours. The section a sentence
     files under (Conflict & Security, Science & Discovery, ...) was decided here, not by
     Wikipedia, so "Science & Discovery in the 3rd century" is an aggregate that exists
     nowhere else. Births and Deaths are excluded: they are people, not subjects, and a
     list of them per century is just Wikipedia's own layout.

Nothing new is written. Same sentences, same citations, same revision ids, re-filed.

Thin pages are dropped rather than published: a page carrying three lines is a liability
in an index, not an asset. The floors are DECADE_MIN / CENTURY_MIN / TOPIC_MIN below.

Usage:
  cross.py [--site data/site] [--out data/site/cross]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Births/Deaths are people, not subjects -- see the docstring.
SKIP_TOPICS = {"Births", "Deaths"}
DECADE_MIN = 12      # entries; below this a decade page is thinner than one year page
CENTURY_MIN = 20
TOPIC_MIN = 8        # entries in one topic-century


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def slugify(title: str) -> str:
    s = title.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def century_of(year: int) -> tuple[str, str, int]:
    """(slug, label, sort key). Years are astronomical: 0 is 1 BCE, -43 is 44 BCE.

    A century here runs 1900-1999, not the pedant's 1901-2000. That is the only version
    that lets decades nest: under the strict definition the 1100s would sit in two
    centuries at once and show up on both pages, which is a duplicate page and a reader
    asking which one is wrong. The century pages say plainly which convention they use."""
    if year >= 1:
        n = year // 100 + 1
        return f"{ordinal(n)}-century", f"{ordinal(n)} century", n
    bce = 1 - year
    n = bce // 100 + 1
    return f"{ordinal(n)}-century-bc", f"{ordinal(n)} century BC", -n


def decade_of(year: int) -> tuple[str, str, int]:
    # Astronomical year 0 IS 1 BCE, so it belongs on the BC side. It used to fall through
    # to the AD branch, which put the one page labelled "1 BCE" in the AD decade 0s while
    # century_of already had it in the 1st century BC -- a breadcrumb that contradicted
    # itself.
    if year >= 1:
        d = (year // 10) * 10
        return f"{d}s", f"{d}s", d
    bce = 1 - year
    d = (bce // 10) * 10
    return f"{d}s-bc", f"{d}s BC", -(d + 10)


def load_years(site: str) -> list[dict]:
    out = []
    for f in sorted((f for f in os.listdir(site) if f.endswith(".json") and f != "index.json"),
                    key=lambda f: int(f[:-5])):
        out.append(json.load(open(os.path.join(site, f), encoding="utf-8")))
    return out


def entry(page: dict, section: str, item: dict) -> dict:
    return {
        "year": page["year"],
        "year_label": page["label"],
        "section": section,
        "date": item.get("date"),
        "text": item["text"],
        "cite": item["cite"],
    }


def write(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "site", "cross"))
    a = ap.parse_args()

    if os.path.isdir(a.out):
        shutil.rmtree(a.out)

    pages = load_years(a.site)

    decades: dict[str, dict] = {}
    centuries: dict[str, dict] = {}
    topics: dict[str, dict] = {}
    year_map: dict[str, dict] = {}

    for page in pages:
        y = page["year"]
        dslug, dlabel, dkey = decade_of(y)
        cslug, clabel, ckey = century_of(y)
        n_entries = sum(len(s["items"]) for s in page["sections"])

        d = decades.setdefault(dslug, {"slug": dslug, "label": dlabel, "key": dkey,
                                       "century": {"slug": cslug, "label": clabel},
                                       "years": [], "entries": 0})
        d["years"].append({"year": y, "label": page["label"], "entries": n_entries,
                           "lead_items": page.get("lead_items", [])[:3]})
        d["entries"] += n_entries

        c = centuries.setdefault(cslug, {"slug": cslug, "label": clabel, "key": ckey,
                                         "decades": {}, "years": 0, "entries": 0,
                                         "topics": {}, "highlights": []})
        c["decades"][dslug] = {"slug": dslug, "label": dlabel, "key": dkey}
        c["years"] += 1
        c["entries"] += n_entries
        if page.get("lead_items"):
            c["highlights"].append({"year": y, "label": page["label"],
                                    "text": page["lead_items"][0]})

        year_map[str(y)] = {"decade": {"slug": dslug, "label": dlabel},
                            "century": {"slug": cslug, "label": clabel}}

        for section in page["sections"]:
            title = section["title"]
            if title in SKIP_TOPICS:
                continue
            tslug = slugify(title)
            t = topics.setdefault(tslug, {"slug": tslug, "label": title, "total": 0,
                                          "by_century": {}})
            t["total"] += len(section["items"])
            bucket = t["by_century"].setdefault(cslug, {"slug": cslug, "label": clabel,
                                                        "key": ckey, "items": []})
            for item in section["items"]:
                bucket["items"].append(entry(page, title, item))
            c["topics"][tslug] = c["topics"].get(tslug, 0) + len(section["items"])

    # ---- decades ----------------------------------------------------------------
    kept_decades = sorted((d for d in decades.values() if d["entries"] >= DECADE_MIN),
                          key=lambda d: d["key"])
    for i, d in enumerate(kept_decades):
        d["years"].sort(key=lambda r: r["year"])
        d["prev"] = {"slug": kept_decades[i - 1]["slug"], "label": kept_decades[i - 1]["label"]} if i else None
        d["next"] = {"slug": kept_decades[i + 1]["slug"], "label": kept_decades[i + 1]["label"]} if i + 1 < len(kept_decades) else None
        write(os.path.join(a.out, "decade", f"{d['slug']}.json"), d)

    kept_decade_slugs = {d["slug"] for d in kept_decades}

    # ---- centuries --------------------------------------------------------------
    kept_centuries = sorted((c for c in centuries.values() if c["entries"] >= CENTURY_MIN),
                            key=lambda c: c["key"])
    for i, c in enumerate(kept_centuries):
        c["decades"] = sorted((d for d in c["decades"].values() if d["slug"] in kept_decade_slugs),
                              key=lambda d: d["key"])
        for d in c["decades"]:
            d["entries"] = decades[d["slug"]]["entries"]
            d["years"] = len(decades[d["slug"]]["years"])
        c["topics"] = sorted(({"slug": s, "label": topics[s]["label"], "count": n}
                              for s, n in c["topics"].items() if n >= TOPIC_MIN),
                             key=lambda t: -t["count"])
        # Spread across the whole century: taking the first eight made every century page
        # open on its first decade and stop.
        hl = c["highlights"]
        step = max(1, len(hl) // 8)
        c["highlights"] = hl[::step][:8]
        c["prev"] = {"slug": kept_centuries[i - 1]["slug"], "label": kept_centuries[i - 1]["label"]} if i else None
        c["next"] = {"slug": kept_centuries[i + 1]["slug"], "label": kept_centuries[i + 1]["label"]} if i + 1 < len(kept_centuries) else None
        write(os.path.join(a.out, "century", f"{c['slug']}.json"), c)

    kept_century_slugs = {c["slug"] for c in kept_centuries}

    # ---- topics -----------------------------------------------------------------
    topic_index = []
    n_topic_pages = 0
    for t in sorted(topics.values(), key=lambda t: -t["total"]):
        buckets = sorted((b for b in t["by_century"].values()
                          if len(b["items"]) >= TOPIC_MIN and b["slug"] in kept_century_slugs),
                         key=lambda b: b["key"])
        for i, b in enumerate(buckets):
            b["items"].sort(key=lambda r: r["year"])
            page = {
                "topic": {"slug": t["slug"], "label": t["label"]},
                "century": {"slug": b["slug"], "label": b["label"]},
                "count": len(b["items"]),
                "span": [b["items"][0]["year_label"], b["items"][-1]["year_label"]],
                "items": b["items"],
                "prev": {"slug": buckets[i - 1]["slug"], "label": buckets[i - 1]["label"]} if i else None,
                "next": {"slug": buckets[i + 1]["slug"], "label": buckets[i + 1]["label"]} if i + 1 < len(buckets) else None,
            }
            write(os.path.join(a.out, "topic", t["slug"], f"{b['slug']}.json"), page)
            n_topic_pages += 1
        hub = {
            "slug": t["slug"], "label": t["label"],
            "total": sum(len(b["items"]) for b in buckets),
            "centuries": [{"slug": b["slug"], "label": b["label"], "count": len(b["items"]),
                           "span": [b["items"][0]["year_label"], b["items"][-1]["year_label"]]}
                          for b in buckets],
            "highlights": [b["items"][len(b["items"]) // 2] for b in buckets[-6:]],
        }
        if not buckets:
            continue
        write(os.path.join(a.out, "topic", f"{t['slug']}.json"), hub)
        topic_index.append({"slug": t["slug"], "label": t["label"], "total": hub["total"],
                            "centuries": len(buckets)})

    # A year (or a decade) whose parent page fell under the floor must not link to a URL
    # that was never built. Null it out rather than publish a 404 in the link graph.
    for rec in year_map.values():
        if rec["decade"]["slug"] not in kept_decade_slugs:
            rec["decade"] = None
        if rec["century"]["slug"] not in kept_century_slugs:
            rec["century"] = None
    for d in kept_decades:
        if d["century"]["slug"] not in kept_century_slugs:
            d["century"] = None
        write(os.path.join(a.out, "decade", f"{d['slug']}.json"), d)

    index = {
        "centuries": [{"slug": c["slug"], "label": c["label"], "years": c["years"],
                       "entries": c["entries"], "key": c["key"]} for c in kept_centuries],
        "decades": [{"slug": d["slug"], "label": d["label"], "years": len(d["years"]),
                     "entries": d["entries"], "key": d["key"],
                     "century": d["century"]["slug"] if d["century"] else None}
                    for d in kept_decades],
        "topics": topic_index,
    }
    write(os.path.join(a.out, "index.json"), index)
    write(os.path.join(a.out, "years.json"), year_map)

    print(f"cross: {len(kept_centuries)} centuries, {len(kept_decades)} decades, "
          f"{len(topic_index)} topic hubs, {n_topic_pages} topic-century pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
