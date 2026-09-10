#!/usr/bin/env python3
"""indexnow.py — tell the search engines the pages exist, without owning an account.

IndexNow is the one submission channel that needs no login: publish a key as a file at
the site root, then POST the URL list. Bing, Yandex, Seznam and Naver share the same
endpoint, so one call reaches all of them. Google does not participate -- Google
discovery still comes from robots.txt, the sitemap and inbound links, and adding the
property in Search Console is the only step here that needs the owner's Google account.

Run it after a deploy, so every URL submitted is already live.

Usage:
  indexnow.py [--sitemap site/out/sitemap.xml] [--key data/indexnow.json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENDPOINT = "https://api.indexnow.org/indexnow"
# The documented ceiling is 10,000 URLs per request; the endpoint answered 403 for a
# single 3,278-URL payload and 200 for everything up to 2,000, so batch below that.
BATCH = 2000


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sitemap", default=os.path.join(ROOT, "site", "out", "sitemap.xml"))
    ap.add_argument("--key", default=os.path.join(ROOT, "data", "indexnow.json"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    urls = re.findall(r"<loc>([^<]+)</loc>", open(a.sitemap, encoding="utf-8").read())
    if not urls:
        print("no urls in sitemap", file=sys.stderr)
        return 1
    key = json.load(open(a.key, encoding="utf-8"))["key"]
    host = urllib.parse.urlparse(urls[0]).netloc

    for i in range(0, len(urls), BATCH):
        chunk = urls[i:i + BATCH]
        payload = json.dumps({
            "host": host,
            "key": key,
            "keyLocation": f"https://{host}/{key}.txt",
            "urlList": chunk,
        }).encode()
        print(f"  {len(chunk)} urls -> {ENDPOINT}")
        if a.dry_run:
            continue
        req = urllib.request.Request(
            ENDPOINT, data=payload,
            headers={"Content-Type": "application/json; charset=utf-8",
                     "User-Agent": "slashyear-indexnow/1.0 (+https://slashyear.com)"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f"  HTTP {r.status} {r.reason}")
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} {e.read()[:200]!r}", file=sys.stderr)
            return 1
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
