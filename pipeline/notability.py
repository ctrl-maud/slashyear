#!/usr/bin/env python3
"""notability.py — measure how big a deal each linked entity is.

A year page shows ten entries per section out of the hundreds available, so the ranking
decides what the site is actually about. The first attempt ranked by how many year
articles link an entity, which rewards "Spain" and "France" and buried the Apollo 11
Moon landing under an obscure killing that happened to mention two countries.

Article byte length is a far better proxy and is free in bulk: Wikipedia will report
info for 50 titles per request, and the encyclopedia has already done the work of
deciding that Apollo 11 deserves 150 KB and a village stub deserves 2 KB.

Writes data/notability.json — {article title: byte length}.

Usage:
  notability.py [--claims data/claims] [--out data/notability.json] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

API = "https://en.wikipedia.org/w/api.php"
UA = "slashyear-rebuild/1.0 (https://www.slashyear.com; ahmadopsr@gmail.com)"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def chunk_lengths(titles: list[str]) -> dict[str, int]:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    params = {"action": "query", "prop": "info", "titles": "|".join(titles),
              "redirects": 1, "format": "json", "formatversion": 2}
    for attempt in range(4):
        try:
            r = s.get(API, params=params, timeout=45)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            d = r.json().get("query", {})
            out: dict[str, int] = {}
            byname = {p["title"]: p.get("length", 0) for p in d.get("pages", [])
                      if not p.get("missing")}
            # map redirects and normalisations back onto the titles we asked for
            alias = {}
            for n in d.get("normalized", []):
                alias[n["from"]] = n["to"]
            for n in d.get("redirects", []):
                alias[n["from"]] = n["to"]
            for t in titles:
                final = t
                for _ in range(3):
                    final = alias.get(final, final)
                if final in byname:
                    out[t] = byname[final]
            return out
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "notability.json"))
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    titles: set[str] = set()
    for fn in os.listdir(a.claims):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(a.claims, fn), encoding="utf-8"))
        for c in d["claims"]:
            titles.update(l.strip() for l in c["links"] if l.strip())
    titles = sorted(t for t in titles if len(t) < 240 and "|" not in t)
    print(f"{len(titles)} distinct linked entities")

    known: dict[str, int] = {}
    if os.path.exists(a.out):
        known = json.load(open(a.out, encoding="utf-8"))
        titles = [t for t in titles if t not in known]
        print(f"  {len(titles)} still to fetch")

    batches = [titles[i:i + 50] for i in range(0, len(titles), 50)]
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(chunk_lengths, b) for b in batches]
        for fut in as_completed(futs):
            known.update(fut.result())
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(batches)} batches, {len(known)} known", flush=True)
                json.dump(known, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(known, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"done: {len(known)} entities measured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
