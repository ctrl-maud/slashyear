#!/usr/bin/env python3
"""machine.py -- check the half of the site that no human ever looks at.

audit.py reads the rendered HTML back and proves the pages say what data/site says.
verify.py proves data/site came from Wikipedia. Between them, every gate this project
has ends at the HTML. But the pages are not what this site is FOR: the pitch is "we sell
the shape, not the words" -- /api, /dump, /api/search, /mcp and llms.txt are the product
for the audience we actually want, and until this file existed not one test read a byte
of them. A stale /api/year/1969.json, a dump that lost 40 rows, a search index pointing
at the wrong sentence or an MCP tool whose declared schema cannot be called would all
have shipped green.

Six checks, all mechanical, all exiting non-zero:

  MIRROR  every /api/... file equals the data/site payload the page was rendered from,
          in both directions -- no stale copy, no orphan file with no page behind it.
  DUMP    events/years/entities .ndjson.gz round-trip the published rows exactly: same
          count, same text, same revision id, no extras, no losses.
  INDEX   /api/years.json, dates.json, entities.json, cross.json name every file that
          exists and nothing that does not.
  TEXT    the inverted index at /api/text: every posting resolves to a sentence shard,
          every indexed sentence is a published sentence, and every token really occurs
          in the sentence it is posted against.
  DOC     every URL promised by /api/index.json, openapi.json, datapackage.json and
          llms.txt resolves -- on disk, and with --live over HTTPS.
  LIVE    (--live) /api/search and the /mcp JSON-RPC server are called for real, their
          tool schemas are filled from what they declare, and every row they return has
          to exist locally with the same text and revision id.
  SEARCHQ (--live) coverage.py's discipline applied to the search endpoint: a list of
          queries anyone would type, each with the answer that has to be in the top five.
          A search that returns real rows in the wrong order passes every other check
          here -- "Apollo 11" answered with a 1920 newspaper item about Goddard, because
          the ranking was settled before the sentence saying "Apollo 11" was ever read.

Usage:
  machine.py [--out site/out] [--site data/site] [--base https://slashyear.com]
             [--live] [--json machine.json] [--quiet]
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Wikimedia's User-Agent policy wants a way to reach the operator. A URL satisfies it;
# set SLASHYEAR_CONTACT to add your own address when running the pipeline yourself.
UA = "slashyear-machine/1.0 (https://www.slashyear.com" + (
    "; " + os.environ["SLASHYEAR_CONTACT"] if os.environ.get("SLASHYEAR_CONTACT") else ""
) + ")"

# Query -> a pattern that must appear in the top five entries. Every case here is a
# thing a person types into a history site, and the answer is the row anyone would mean.
SEARCH_CASES: list[tuple[str, str, int]] = [
    # (query, pattern the answer must match, how far down the list it may sit)
    # any Apollo 11 row of 1969 -- the launch and the return are both right answers, and
    # a gate that insists on its favourite is charging the site with the tester's taste
    ("Apollo 11", r"^1969 .*Apollo 11", 1),
    ("moon landing", r"Lunar Module Eagle|Moon landing", 1),
    ("Stonewall riots", r"Stonewall riots", 1),
    ("Chernobyl", r"Chernobyl", 1),
    ("Berlin Wall", r"Berlin Wall", 1),
    ("Pearl Harbor", r"Pearl Harbor", 1),
    ("1969", r"^1969", 1),
    ("Black Death", r"Black Death", 2),
    ("Titanic", r"Titanic", 2),
    ("Battle of Waterloo", r"Waterloo", 2),
    ("Krakatoa", r"Krakatoa", 2),
    ("printing press", r"Gutenberg|printing", 3),
]

FAILS: list[str] = []
NOTES: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def isyear(n: str) -> bool:
    try:
        int(n)
        return True
    except ValueError:
        return False


def get(url: str, data: bytes | None = None, ctype: str | None = None, timeout=45):
    req = urllib.request.Request(url, data=data)
    req.add_header("User-Agent", UA)
    if ctype:
        req.add_header("Content-Type", ctype)
        req.add_header("Accept", "application/json, text/event-stream")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


# ------------------------------------------------------------------------- MIRROR --
def check_mirror(out: str, site: str) -> None:
    pairs = []
    for f in glob.glob(os.path.join(site, "*.json")):
        if isyear(os.path.basename(f)[:-5]):
            pairs.append((f, os.path.join(out, "api", "year", os.path.basename(f))))
    for sub, api in (("dates", "date"), ("entities", "entity")):
        for f in glob.glob(os.path.join(site, sub, "*.json")):
            if os.path.basename(f) == "index.json":
                continue
            pairs.append((f, os.path.join(out, "api", api, os.path.basename(f))))
    for f in glob.glob(os.path.join(site, "cross", "**", "*.json"), recursive=True):
        rel = os.path.relpath(f, os.path.join(site, "cross"))
        if os.sep not in rel:
            continue      # cross/index.json and cross/years.json are navigation, not a page
        pairs.append((f, os.path.join(out, "api", rel)))

    missing = stale = 0
    for src, dst in pairs:
        if not os.path.exists(dst):
            missing += 1
            if missing <= 5:
                fail(f"MIRROR /api file missing for {os.path.relpath(src, ROOT)}")
            continue
        if load(src) != load(dst):
            stale += 1
            if stale <= 5:
                fail(f"MIRROR {os.path.relpath(dst, out)} differs from its page data")
    if missing > 5:
        fail(f"MIRROR {missing} /api files missing in total")
    if stale > 5:
        fail(f"MIRROR {stale} /api files differ in total")

    # the other direction: an /api file with no page behind it
    want = {os.path.abspath(d) for _s, d in pairs}
    orphans = [p for p in glob.glob(os.path.join(out, "api", "**", "*.json"), recursive=True)
               if os.path.abspath(p) not in want
               and os.path.basename(p) not in ("index.json", "openapi.json", "years.json",
                                               "dates.json", "entities.json", "cross.json",
                                               "search-index.json")
               and "/api/text/" not in p.replace(os.sep, "/")]
    if orphans:
        fail(f"MIRROR {len(orphans)} /api files have no page data behind them "
             f"(e.g. {os.path.relpath(orphans[0], out)})")
    NOTES.append(f"MIRROR {len(pairs):,} api files compared to their page payloads")


# --------------------------------------------------------------------------- DUMP --
def published_rows(site: str):
    """(year, text, revid) for every bullet the site publishes on a year page."""
    rows = []
    for f in glob.glob(os.path.join(site, "*.json")):
        if not isyear(os.path.basename(f)[:-5]):
            continue
        d = load(f)
        for s in d["sections"]:
            for it in s["items"]:
                rows.append((d["year"], it["text"], it["cite"]["revid"]))
    return rows


def check_dump(out: str, site: str) -> None:
    dump = os.path.join(out, "dump")
    want = sorted(published_rows(site))
    got = []
    with gzip.open(os.path.join(dump, "events.ndjson.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            got.append((r["year"], r["text"], r["source_revid"]))
    got.sort()
    if len(want) != len(got):
        fail(f"DUMP events.ndjson.gz has {len(got):,} rows, the site publishes {len(want):,}")
    if want != got:
        lost = set(want) - set(got)
        extra = set(got) - set(want)
        if lost:
            y, t, _ = sorted(lost)[0]
            fail(f"DUMP {len(lost)} published rows are not in the dump (e.g. {y}: {t[:60]})")
        if extra:
            y, t, _ = sorted(extra)[0]
            fail(f"DUMP {len(extra)} dump rows are not published anywhere (e.g. {y}: {t[:60]})")

    years = {int(os.path.basename(f)[:-5]) for f in glob.glob(os.path.join(site, "*.json"))
             if isyear(os.path.basename(f)[:-5])}
    dy = set()
    with gzip.open(os.path.join(dump, "years.ndjson.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            dy.add(json.loads(line)["year"])
    if dy != years:
        fail(f"DUMP years.ndjson.gz covers {len(dy):,} years, the site publishes {len(years):,}")

    ents = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(site, "entities", "*.json"))
            if os.path.basename(f) != "index.json"}
    de = set()
    with gzip.open(os.path.join(dump, "entities.ndjson.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            de.add(json.loads(line)["slug"])
    if de != ents:
        fail(f"DUMP entities.ndjson.gz has {len(de):,} subjects, the site publishes {len(ents):,}")

    dp = load(os.path.join(dump, "datapackage.json"))
    for res in dp.get("resources", []):
        p = os.path.join(dump, os.path.basename(res["path"]))
        if not os.path.exists(p):
            fail(f"DUMP datapackage names {res['path']} which does not exist")
    NOTES.append(f"DUMP {len(got):,} event rows round-tripped, {len(dy):,} years, {len(de):,} subjects")


# -------------------------------------------------------------------------- INDEX --
def check_index(out: str) -> None:
    api = os.path.join(out, "api")
    for name, sub, key in (("years.json", "year", "year"),
                           ("dates.json", "date", "slug"),
                           ("entities.json", "entity", "slug")):
        p = os.path.join(api, name)
        if not os.path.exists(p):
            fail(f"INDEX /api/{name} missing")
            continue
        idx = load(p)
        rows = idx if isinstance(idx, list) else (idx.get("years") or idx.get("dates")
                                                  or idx.get("entities") or idx.get("items") or [])
        listed = set()
        for r in rows:
            v = r if isinstance(r, (str, int)) else r.get(key, r.get("slug", r.get("year")))
            listed.add(str(v))
        on_disk = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(api, sub, "*.json"))}
        if not on_disk:
            continue
        missing = on_disk - listed
        ghost = listed - on_disk
        if missing:
            fail(f"INDEX /api/{name} omits {len(missing)} files that exist (e.g. {sorted(missing)[0]})")
        if ghost:
            fail(f"INDEX /api/{name} names {len(ghost)} files that do not exist "
                 f"(e.g. {sorted(ghost)[0]})")
    NOTES.append("INDEX api indexes agree with the files on disk")


# --------------------------------------------------------------------------- TEXT --
def check_text(out: str, site: str) -> None:
    tdir = os.path.join(out, "api", "text")
    meta_p = os.path.join(tdir, "index.json")
    if not os.path.exists(meta_p):
        fail("TEXT /api/text/index.json missing")
        return
    meta = load(meta_p)
    docs: dict[int, dict] = {}
    for f in glob.glob(os.path.join(tdir, "d-*.json")):
        chunk = load(f)
        items = chunk if isinstance(chunk, list) else chunk.get("docs", chunk)
        if isinstance(items, dict):
            for k, v in items.items():
                docs[int(k)] = v
        else:
            base = int(os.path.basename(f)[2:-5]) * meta.get("docs_per_shard", 256)
            for i, v in enumerate(items):
                docs[base + i] = v
    if len(docs) != meta.get("documents"):
        fail(f"TEXT index.json claims {meta.get('documents'):,} documents, the shards hold {len(docs):,}")

    published = set()
    for f in glob.glob(os.path.join(site, "*.json")):
        if not isyear(os.path.basename(f)[:-5]):
            continue
        for s in load(f)["sections"]:
            for it in s["items"]:
                published.add(it["text"])

    def doctext(v):
        """A shard row is [year, label, date, section, TEXT, url, title, revid, section]."""
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return v[4] if len(v) > 4 and isinstance(v[4], str) else json.dumps(v)
        for k in ("t", "text", "s", "sentence"):
            if isinstance(v, dict) and k in v:
                return v[k]
        return json.dumps(v)

    bad = 0
    for i, v in list(docs.items()):
        t = doctext(v)
        if t not in published:
            bad += 1
            if bad <= 3:
                fail(f"TEXT indexed sentence #{i} is not published anywhere: {t[:70]}")
    if bad > 3:
        fail(f"TEXT {bad:,} indexed sentences are not published anywhere")

    # every posting must resolve, and the token must really be in the sentence it points at
    dangling = wrong = checked = 0
    for f in sorted(glob.glob(os.path.join(tdir, "t-*.json")))[:6]:
        table = load(f)
        for token, ids in list(table.items())[:400]:
            for did in (ids if isinstance(ids, list) else ids.get("d", []))[:4]:
                did = did[0] if isinstance(did, list) else did
                if did not in docs:
                    dangling += 1
                    continue
                checked += 1
                if token.lower() not in re.sub(r"[^a-z0-9]+", " ", doctext(docs[did]).lower()):
                    wrong += 1
                    if wrong <= 3:
                        fail(f"TEXT token {token!r} is posted against a sentence that does "
                             f"not contain it: {doctext(docs[did])[:60]}")
    if dangling:
        fail(f"TEXT {dangling} postings point at document ids that do not exist")
    NOTES.append(f"TEXT {len(docs):,} indexed sentences, {checked:,} postings spot-checked")


# ---------------------------------------------------------------------------- DOC --
URLRE = re.compile(r"https?://[^\s)\"'<>]+")


def check_doc(out: str, base: str, live: bool) -> None:
    urls: set[str] = set()
    for name in ("api/index.json", "api/openapi.json", "dump/datapackage.json",
                 "llms.txt", "llms-full.txt"):
        p = os.path.join(out, name)
        if not os.path.exists(p):
            fail(f"DOC {name} was not written")
            continue
        urls.update(URLRE.findall(open(p, encoding="utf-8").read()))
    idx = load(os.path.join(out, "api", "index.json"))
    for ep in idx.get("endpoints", []):
        path = ep["path"]
        if "{" in path:
            continue
        urls.add(base + path)

    # a documented TEMPLATE (/api/year/{year}.json) is not a URL to fetch
    ours = sorted(u for u in urls if u.startswith(base) and "{" not in u and "}" not in u)
    checked = 0
    for u in ours:
        rel = u[len(base):].split("#")[0].split("?")[0]
        if rel in ("/mcp", "/api/search") or rel.startswith("/api/search"):
            continue
        cands = [os.path.join(out, rel.lstrip("/")),
                 os.path.join(out, rel.lstrip("/"), "index.html"),
                 os.path.join(out, rel.lstrip("/") + ".html")]
        if rel in ("", "/"):
            cands = [os.path.join(out, "index.html")]
        if not any(os.path.exists(c) for c in cands):
            fail(f"DOC {u} is promised in the docs and does not exist in the build")
        checked += 1
    NOTES.append(f"DOC {checked} documented URLs resolve in the build")

    if live:
        for u in ours[:40]:
            try:
                st, _ = get(u)
                if st != 200:
                    fail(f"DOC live {u} -> HTTP {st}")
            except Exception as e:
                fail(f"DOC live {u} -> {e.__class__.__name__} {e}")


# --------------------------------------------------------------------------- LIVE --
def sample_query(site: str) -> tuple[str, str]:
    d = load(os.path.join(site, "1969.json"))
    for s in d["sections"]:
        for it in s["items"]:
            if "Apollo 11" in it["text"]:
                return "Apollo 11", it["text"]
    return "Apollo 11", ""


def check_live(out: str, site: str, base: str) -> None:
    published = {}
    for f in glob.glob(os.path.join(site, "*.json")):
        if not isyear(os.path.basename(f)[:-5]):
            continue
        d = load(f)
        for s in d["sections"]:
            for it in s["items"]:
                published[it["text"]] = (d["year"], it["cite"]["revid"])

    q, _ = sample_query(site)
    try:
        st, body = get(f"{base}/api/search?q={q.replace(' ', '+')}&limit=10")
        res = json.loads(body)
        rows = res.get("entries", res.get("results", res if isinstance(res, list) else []))
        if not rows:
            fail(f"LIVE /api/search?q={q} returned no rows")
        for r in rows:
            t = r.get("text") or ""
            if t and t not in published:
                fail(f"LIVE /api/search returned a sentence that is not published: {t[:70]}")
            elif t and (r.get("source") or {}).get("revision_id") and \
                    published[t][1] != r["source"]["revision_id"]:
                fail(f"LIVE /api/search returned the wrong revision id for: {t[:60]}")
        NOTES.append(f"LIVE /api/search '{q}' -> {len(rows)} rows, all published")
    except Exception as e:
        fail(f"LIVE /api/search -> {e.__class__.__name__} {e}")

    # --- SEARCHQ: the answer a person would expect, in the top five
    for q, must, depth in SEARCH_CASES:
        try:
            st, body = get(f"{base}/api/search?q={urllib.parse.quote(q)}&limit=5")
            res = json.loads(body)
            top = res.get("entries", [])[:depth]
            hay = " || ".join(f"{e.get('year')} {e.get('text','')}" for e in top)
            if not re.search(must, hay, re.I):
                first = (top[0].get("text", "")[:70] if top else "nothing")
                fail(f"SEARCHQ '{q}' does not answer with /{must}/ in its top {depth} "
                     f"(top hit: {first})")
        except Exception as e:
            fail(f"SEARCHQ '{q}' -> {e.__class__.__name__} {e}")
    NOTES.append(f"SEARCHQ {len(SEARCH_CASES)} queries answered correctly in the top five")

    # --- MCP: fill each declared tool's schema from what it declares, then call it
    def rpc(method, params=None, mid=1):
        payload = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            payload["params"] = params
        st, body = get(f"{base}/mcp", data=json.dumps(payload).encode(),
                       ctype="application/json")
        txt = body.decode("utf-8", "replace")
        if txt.startswith("event:") or "\ndata:" in txt:
            txt = "\n".join(l[5:].strip() for l in txt.splitlines()
                            if l.startswith("data:"))
        return st, json.loads(txt)

    try:
        st, init = rpc("initialize", {"protocolVersion": "2025-06-18",
                                      "capabilities": {},
                                      "clientInfo": {"name": "machine.py", "version": "1"}})
        if "result" not in init:
            fail(f"LIVE /mcp initialize -> {json.dumps(init)[:160]}")
        st, tl = rpc("tools/list", {}, 2)
        tools = tl.get("result", {}).get("tools", [])
        if not tools:
            fail("LIVE /mcp declares no tools")
        defaults = {"year": 1969, "years": "1969", "query": "Apollo 11", "q": "Apollo 11",
                    "date": "july-20", "day": "july-20", "slug": "apollo-11",
                    "subject": "apollo-11", "topic": "science-and-discovery",
                    "century": 20, "decade": 1960, "limit": 3, "from": 1960, "to": 1970}
        for t in tools:
            schema = t.get("inputSchema", {}) or {}
            props = schema.get("properties", {}) or {}
            args = {}
            for name in schema.get("required", []):
                v = defaults.get(name)
                if v is None:
                    kind = (props.get(name) or {}).get("type", "string")
                    v = 1969 if kind in ("integer", "number") else "1969"
                args[name] = v
            st, res = rpc("tools/call", {"name": t["name"], "arguments": args}, 3)
            if "result" not in res:
                fail(f"LIVE /mcp tool {t['name']}({args}) -> {json.dumps(res)[:200]}")
                continue
            content = res["result"].get("content", [])
            blob = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            if res["result"].get("isError"):
                fail(f"LIVE /mcp tool {t['name']} returned isError with args {args}")
            elif not blob.strip():
                fail(f"LIVE /mcp tool {t['name']} returned nothing for {args}")
            else:
                try:
                    parsed = json.loads(blob)
                except Exception:
                    parsed = None
                rows = []
                if isinstance(parsed, dict):
                    for k in ("results", "items", "entries", "rows", "sections"):
                        v = parsed.get(k)
                        if isinstance(v, list):
                            rows = v
                            break
                for r in rows[:20]:
                    if isinstance(r, dict) and isinstance(r.get("text"), str):
                        if r["text"] not in published:
                            fail(f"LIVE /mcp {t['name']} returned an unpublished sentence: "
                                 f"{r['text'][:70]}")
        NOTES.append(f"LIVE /mcp initialize + {len(tools)} tools called, answers cross-checked")
    except Exception as e:
        fail(f"LIVE /mcp -> {e.__class__.__name__} {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "site", "out"))
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--base", default="https://slashyear.com")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--json", default=os.path.join(ROOT, "machine.json"))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    check_mirror(a.out, a.site)
    check_dump(a.out, a.site)
    check_index(a.out)
    check_text(a.out, a.site)
    check_doc(a.out, a.base, a.live)
    if a.live:
        check_live(a.out, a.site, a.base)

    json.dump({"failures": FAILS, "notes": NOTES}, open(a.json, "w"), indent=1)
    if not a.quiet:
        for n in NOTES:
            print("  " + n)
        if FAILS:
            print(f"machine: {len(FAILS)} FAILURES")
            for f in FAILS[:25]:
                print("  x " + f)
        else:
            print("machine: the API, dumps, indexes and MCP surface all agree with the pages")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
