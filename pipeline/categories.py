#!/usr/bin/env python3
"""categories.py — Wikipedia's own categories for every entity our event rows link.

Built for theming.py: the site's only model-made decision is which section a sentence
files under, and until this existed there was no ground truth to check it against
except a list we wrote ourselves. Wikipedia already publishes a taxonomy for every
article -- "Category:Plays by Sophocles", "Category:Battles involving England" -- and
that taxonomy is the source's, not ours.

Fetches the non-hidden categories for every distinct link in the event claims and
caches them to data/categories.json. Resumable: only titles the cache has never seen
are requested.

Usage:
  categories.py [--claims data/claims] [--out data/categories.json] [--workers 8]
"""
import os
from __future__ import annotations
import argparse, glob, json, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://en.wikipedia.org/w/api.php"
# Wikimedia's User-Agent policy wants a way to reach the operator. A URL satisfies it;
# set SLASHYEAR_CONTACT to add your own address when running the pipeline yourself.
UA = "slashyear-categories/1.0 (https://www.slashyear.com" + (
    "; " + os.environ["SLASHYEAR_CONTACT"] if os.environ.get("SLASHYEAR_CONTACT") else ""
) + ")"
LOCK = threading.Lock()


def isyear(n: str) -> bool:
    try:
        int(n); return True
    except ValueError:
        return False


def fetch(session, titles):
    """{title: [category, ...]} for up to 50 titles, following redirects."""
    out, cont = {}, {}
    for _ in range(12):
        params = {"action": "query", "prop": "categories", "titles": "|".join(titles),
                  "cllimit": "max", "clshow": "!hidden", "format": "json",
                  "formatversion": 2, "redirects": 1}
        params.update(cont)
        for attempt in range(5):
            try:
                r = session.get(API, params=params, timeout=60)
                j = r.json()
                break
            except Exception:
                time.sleep(1.5 * (attempt + 1))
                j = None
        if not j:
            return out, False
        norm = {}
        for k in ("normalized", "redirects"):
            for m in j.get("query", {}).get(k, []):
                norm[m["to"]] = norm.get(m["from"], m["from"])
        for p in j.get("query", {}).get("pages", []):
            t = p.get("title", "")
            cats = [c["title"].replace("Category:", "") for c in p.get("categories", [])]
            for name in {t, norm.get(t, t)}:
                out.setdefault(name, [])
                out[name] += cats
        if "continue" in j:
            cont = j["continue"]
            continue
        return out, True
    return out, True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "categories.json"))
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    wanted = set()
    for f in glob.glob(os.path.join(a.claims, "*.json")):
        if not isyear(os.path.basename(f)[:-5]):
            continue
        for c in json.load(open(f, encoding="utf-8"))["claims"]:
            if c.get("kind") == "event":
                wanted.update(c["links"])
    cache = {}
    if os.path.exists(a.out):
        cache = json.load(open(a.out, encoding="utf-8"))
    todo = sorted(t for t in wanted if t and t not in cache)
    print(f"{len(wanted)} distinct links, {len(cache)} cached, {len(todo)} to fetch",
          flush=True)
    batches = [todo[i:i + 50] for i in range(0, len(todo), 50)]
    done = [0]

    def work(batch):
        s = requests.Session(); s.headers["User-Agent"] = UA
        got, ok = fetch(s, batch)
        with LOCK:
            for t in batch:
                cache.setdefault(t, [])
            for t, cats in got.items():
                cache[t] = sorted(set(cats))
            done[0] += 1
            if done[0] % 100 == 0:
                print(f"  {done[0]}/{len(batches)} batches", flush=True)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(work, batches))
    json.dump(cache, open(a.out, "w", encoding="utf-8"))
    have = sum(1 for t in wanted if cache.get(t))
    print(f"wrote {a.out}: {len(cache)} titles, {have} with at least one category")
    return 0


if __name__ == "__main__":
    sys.exit(main())
