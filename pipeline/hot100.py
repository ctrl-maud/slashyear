#!/usr/bin/env python3
"""hot100.py — every Billboard Hot 100 number one, week by week, quoted from Wikipedia.

The site's rule is that every line is quoted from a specific Wikipedia revision, and a
"number one this week" fact is no exception: we do not bring our own chart data. Each
year has a list article ("List of Billboard Hot 100 number ones of 1969") whose chart
table gives issue date, title and artist. This fetches those articles, records the
revision each one was read at, and flattens the tables into one row per chart week.

The tables are hand-made and drift between years, so nothing here assumes a layout:

  - a song that held the top spot for N weeks is written once with rowspan=N and is
    expanded back to N issue dates;
  - columns are found by their header text (Issue date / Song / Artist(s)), not position;
  - 1958 is a redirect into "List of Billboard number-one singles of 1958", whose earlier
    tables are the pre-Hot 100 charts, so only the section the redirect points at is read;
  - dates come as {{dts|August 4}}, plain "January 2", or with a year; titles as
    "[[Song (band song)|Song]]"{{dagger}}; artists as {{sortname|Marvin|Gaye}}.

Output is data/extras/hot100.json: the source revisions, and the weeks each citing the
revid it came from. The weeks must form an unbroken 7-day sequence from 1958-08-04; any
gap or duplicate is printed, since it means a table was misread.

Usage:
  hot100.py [--from 1958] [--to 2026] [--out data/extras/hot100.json] [--cache DIR]
            [--check 1969-07-19 ...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time

import mwparserfromhell as mwp
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://en.wikipedia.org/w/api.php"
UA = "slashyear-build/1.0 (https://slashyear.com; ahmadopsr@gmail.com)"
TITLE = "List of Billboard Hot 100 number ones of {}"
FIRST = dt.date(1958, 8, 4)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}
CHECKS = ["1969-07-19", "1985-07-13", "1999-12-25", "2015-03-07"]
# issues off the weekly rhythm in Billboard itself, each footnoted in the articles:
# Monday -> Saturday dating from 1962, the Sunday July 4 1976 bicentennial issue, and
# the Wednesday January 3 2018 issue when chart dating moved
KNOWN = {"1962-01-06", "1976-07-04", "1976-07-10", "2018-01-03", "2018-01-06"}

# templates that are footnotes, markers or anchors and carry no visible title/artist text
DROP = {"efn", "sfn", "refn", "ref", "r", "note", "notetag", "ref label", "anchor",
        "dagger", "double-dagger", "double dagger", "ddagger", "†", "‡", "*",
        "cn", "citation needed", "sup", "hs", "hidden sort key", "sort key",
        "nbsp", "efn-ua", "efn-lr", "nts", "nowrap begin", "nowrap end"}


def fetch(session, title: str) -> dict | None:
    """Resolved title, revid, timestamp, wikitext and redirect fragment, or None."""
    for attempt in range(5):
        try:
            r = session.get(API, params={"action": "query", "prop": "revisions",
                                         "rvprop": "ids|content|timestamp", "rvslots": "main",
                                         "titles": title, "redirects": 1,
                                         "format": "json", "formatversion": 2}, timeout=60)
            if r.status_code in (429, 503):
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            q = r.json()["query"]
            page = q["pages"][0]
            if page.get("missing") or "revisions" not in page:
                return None
            rev = page["revisions"][0]
            frag = next((x.get("tofragment") for x in q.get("redirects", [])), None)
            return {"title": page["title"], "revid": rev["revid"],
                    "timestamp": rev["timestamp"], "fragment": frag,
                    "text": rev["slots"]["main"]["content"]}
        except requests.RequestException:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"could not fetch {title!r}")


def search(session, year: int) -> str | None:
    """Fallback when the expected title does not exist: the best search hit."""
    r = session.get(API, params={"action": "query", "list": "search", "format": "json",
                                 "formatversion": 2, "srlimit": 5,
                                 "srsearch": f"intitle:Billboard intitle:{year} Hot 100 number ones"},
                    timeout=60)
    for hit in r.json()["query"]["search"]:
        if str(year) in hit["title"] and "number" in hit["title"].lower():
            return hit["title"]
    return None


def section(text: str, heading: str | None) -> str:
    """The body under a heading, up to the next heading of the same or higher level."""
    if not heading:
        return text
    m = re.search(r"^(=+)\s*" + re.escape(heading) + r"\s*\1\s*$", text, re.M)
    if not m:
        return text
    rest = text[m.end():]
    end = re.search(r"^={1,%d}[^=].*?=+\s*$" % len(m.group(1)), rest, re.M)
    return rest[:end.start()] if end else rest


def strip_refs(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref\b[^>]*?/>", "", text, flags=re.I)
    return re.sub(r"<ref\b[^>]*>.*?</ref\s*>", "", text, flags=re.I | re.S)


def tables(text: str) -> list[str]:
    """Top-level {| ... |} blocks; nested tables stay inside their parent."""
    out, depth, cur = [], 0, []
    for line in text.split("\n"):
        s = line.lstrip()
        if s.startswith("{|"):
            depth += 1
        if depth:
            cur.append(line)
        if s.startswith("|}") and depth:
            depth -= 1
            if not depth:
                out.append("\n".join(cur))
                cur = []
    return out


def split_top(s: str, sep: str) -> list[str]:
    """Split on sep only where it is outside [[...]] and {{...}}."""
    parts, depth, i, start = [], 0, 0, 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1; i += 2; continue
        if two in ("]]", "}}"):
            depth = max(0, depth - 1); i += 2; continue
        if depth == 0 and s.startswith(sep, i):
            parts.append(s[start:i]); i += len(sep); start = i; continue
        i += 1
    parts.append(s[start:])
    return parts


def cell(raw: str, header: bool) -> dict:
    bits = split_top(raw, "|")
    attrs, content = "", raw
    if len(bits) > 1 and "[[" not in bits[0] and "{{" not in bits[0]:
        attrs, content = bits[0], "|".join(bits[1:])
    span = lambda k: int(m.group(1)) if (m := re.search(k + r"\s*=\s*[\"']?(\d+)", attrs, re.I)) else 1
    return {"header": header, "content": content.strip(),
            "rowspan": span("rowspan"), "colspan": span("colspan")}


def rows(table: str) -> list[list[dict]]:
    """Wikitable rows as lists of cells, before spans are applied."""
    out, cur = [], []
    for line in table.split("\n")[1:]:
        s = line.strip()
        if s.startswith("|}"):
            break
        if s.startswith("|-"):
            if cur:
                out.append(cur)
            cur = []
        elif s.startswith("|+"):
            continue
        elif s.startswith("!"):
            for c in split_top(s[1:], "!!"):
                for c2 in split_top(c, "||"):
                    cur.append(cell(c2, True))
        elif s.startswith("|"):
            for c in split_top(s[1:], "||"):
                cur.append(cell(c, False))
        elif cur and s:
            cur[-1]["content"] += " " + s
    if cur:
        out.append(cur)
    return out


def grid(rws: list[list[dict]]) -> list[list[dict]]:
    """Apply rowspan/colspan so every row has one entry per column."""
    out, pending = [], {}
    for r in rws:
        line, col, cells = [], 0, list(r)
        while cells or any(c >= col for c in pending):
            if col in pending:
                c, left = pending[col]
                line.append(c)
                pending[col] = (c, left - 1)
                if left - 1 == 0:
                    del pending[col]
                col += 1
                continue
            if not cells:
                line.append(None); col += 1
                continue
            c = cells.pop(0)
            for _ in range(c["colspan"]):
                line.append(c)
                if c["rowspan"] > 1:
                    pending[col] = (c, c["rowspan"] - 1)
                col += 1
        out.append(line)
    return out


def render(t) -> str:
    name = str(t.name).strip().lower().replace("_", " ")
    pos = [plain(str(p.value)) for p in t.params if not p.showkey]
    named = {str(p.name).strip(): plain(str(p.value)) for p in t.params if p.showkey}
    if name in DROP or name.startswith(("cite", "efn", "sfn")):
        return ""
    if name == "sort":
        return pos[1] if len(pos) > 1 else (pos[0] if pos else "")
    if name == "sortname":
        return named.get("display") or " ".join(x for x in pos[:2] if x)
    if name in ("dts", "date", "start date", "dts2"):
        return " ".join(x for x in pos if x not in ("", "link=off"))
    if name in ("ill", "interlanguage link"):
        return named.get("lt") or (pos[0] if pos else "")
    if name in ("lang", "langx"):
        return pos[1] if len(pos) > 1 else ""
    if name in ("'", "\""):
        return "'" if name == "'" else '"'
    return pos[0] if pos else ""


def plain(wt: str) -> str:
    """Visible text of a wikitext fragment: links -> label, templates rendered, no markup."""
    wt = re.sub(r"<br\s*/?>", " ", wt, flags=re.I)
    code = mwp.parse(wt)
    for t in code.filter_templates(recursive=False):
        code.replace(t, render(t))
    for f in code.filter_wikilinks(recursive=False):
        if str(f.title).strip().lower().startswith(("file:", "image:", "category:")):
            code.replace(f, "")
    s = code.strip_code(normalize=True, collapse=True)
    s = s.replace("\xa0", " ").replace("&nbsp;", " ")
    s = re.sub(r"<[^>]+>", "", s).replace("'''", "").replace("''", "")
    s = s.replace("†", "").replace("‡", "").replace("§", "")
    return re.sub(r"\s+", " ", s).strip()


def untitle(s: str) -> str:
    """Drop the quotation marks Wikipedia puts around song titles, including both sides
    of a double A-side ("Don't" / "I Beg of You")."""
    s = s.strip().strip("*").strip()
    m = re.match(r"^[\"“]([^\"“”]+)[\"”]\s*(\([^\"“”]*\))$", s)
    if m:  # "Macarena" (Bayside Boys Mix)
        return f"{m.group(1).strip()} {m.group(2)}"
    if s.startswith(("\"", "“")) and s.endswith(("\"", "”")):
        inner = s[1:-1]
        if not re.search(r"[\"“”]", inner):
            return inner.strip()
        parts = re.split(r"[\"”]\s*(/|and|&|b/w)\s*[\"“]", inner)
        if all(not re.search(r"[\"“”]", p) for p in parts[::2]):
            return " / ".join(p.strip() for p in parts[::2])
    return s


def to_date(text: str, year: int) -> dt.date | None:
    s = text.replace(",", " ").strip()
    m = re.match(r"^(\d{4})\s+(\d{1,2})\s+(\d{1,2})$", s) or re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^([A-Za-z]+)\.?\s+(\d{1,2})(?:\s+(\d{4}))?$", s) or None
    if m and m.group(1).lower()[:3] in {k[:3] for k in MONTHS}:
        mon = next(v for k, v in MONTHS.items() if k.startswith(m.group(1).lower()[:3]))
        return dt.date(int(m.group(3) or year), mon, int(m.group(2)))
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?$", s)
    if m and m.group(2).lower() in MONTHS:
        return dt.date(int(m.group(3) or year), MONTHS[m.group(2).lower()], int(m.group(1)))
    return None


def column(headers: list[str], *names) -> int | None:
    for i, h in enumerate(headers):
        if any(re.search(n, h, re.I) for n in names):
            return i
    return None


def parse_year(page: dict, year: int) -> list[dict]:
    """One row per issue date in the article's chart table(s)."""
    text = strip_refs(section(page["text"], page.get("fragment")))
    out = []
    for tbl in tables(text):
        g = grid(rows(tbl))
        hi = next((i for i, r in enumerate(g)
                   if any(c and c["header"] and re.search(r"\bdate\b|\bweek\b", plain(c["content"]), re.I)
                          for c in r)), None)
        if hi is None:
            continue
        headers = [plain(c["content"]) if c else "" for c in g[hi]]
        cd = column(headers, r"issue date", r"\bdate\b", r"\bweek\b")
        ct = column(headers, r"^song", r"^title", r"^single", r"song", r"title")
        ca = column(headers, r"^artist", r"performer", r"artist")
        if None in (cd, ct, ca):
            continue
        for r in g[hi + 1:]:
            if len(r) <= max(cd, ct, ca) or not r[cd]:
                continue
            d = to_date(plain(r[cd]["content"]), year)
            if not d:
                continue
            out.append({"date": d.isoformat(),
                        "title": untitle(plain(r[ct]["content"])) if r[ct] else "",
                        "artist": plain(r[ca]["content"]) if r[ca] else "",
                        "revid": page["revid"]})
    return out


def gaps(weeks: list[dict]) -> list[str]:
    msgs, prev = [], None
    if weeks and weeks[0]["date"] != FIRST.isoformat():
        msgs.append(f"first week is {weeks[0]['date']}, expected {FIRST}")
    for w in weeks:
        d = dt.date.fromisoformat(w["date"])
        if prev and (d - prev).days != 7 and w["date"] not in KNOWN:
            msgs.append(f"{prev} -> {d} ({(d - prev).days} days)")
        prev = d
    return msgs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="y0", type=int, default=1958)
    ap.add_argument("--to", dest="y1", type=int, default=dt.date.today().year)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "extras", "hot100.json"))
    ap.add_argument("--cache", help="directory to keep fetched articles in (optional)")
    ap.add_argument("--check", nargs="*", default=CHECKS, help="dates to spot check")
    a = ap.parse_args()

    s = requests.Session()
    s.headers["User-Agent"] = UA
    today = dt.date.today().isoformat()
    sources, weeks = [], []
    for y in range(a.y0, a.y1 + 1):
        cp = os.path.join(a.cache, f"{y}.json") if a.cache else None
        if cp and os.path.exists(cp):
            page = json.load(open(cp, encoding="utf-8"))
        else:
            page = fetch(s, TITLE.format(y))
            if page is None and (alt := search(s, y)):
                page = fetch(s, alt)
            if page is None:
                print(f"{y}: no article")
                continue
            page["retrieved"] = today
            if cp:
                os.makedirs(a.cache, exist_ok=True)
                json.dump(page, open(cp, "w", encoding="utf-8"))
            time.sleep(0.2)
        rows_ = [w for w in parse_year(page, y) if w["date"] >= FIRST.isoformat()]
        print(f"{y}: {len(rows_):3d} weeks  rev {page['revid']}  {page['title']}")
        if not rows_:
            continue
        sources.append({"year": y, "title": page["title"], "revid": page["revid"],
                        "url": f"https://en.wikipedia.org/w/index.php?oldid={page['revid']}",
                        "license": "CC BY-SA 4.0", "retrieved": page.get("retrieved", today)})
        weeks += rows_

    weeks.sort(key=lambda w: w["date"])
    seen, dups = set(), []
    for w in weeks:
        if w["date"] in seen:
            dups.append(w["date"])
        seen.add(w["date"])
    bad = [w for w in weeks if not w["title"] or not w["artist"]]

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"sources": sources, "weeks": weeks}, f, ensure_ascii=False, indent=1)
    print(f"wrote {a.out}: {len(weeks)} weeks, {weeks[0]['date']} .. {weeks[-1]['date']}")

    g = gaps(weeks)
    print("gap check: " + ("ok, no gaps or duplicates beyond the known off-cycle issues" if not g else f"{len(g)} problems"))
    for m in g:
        print("  " + m)
    for k in sorted(KNOWN & seen):
        print(f"  known off-cycle issue {k}")
    for d in dups:
        print(f"  duplicate {d}")
    for w in bad:
        print(f"  empty field {w}")
    for c in a.check:
        hit = [w for w in weeks if w["date"] <= c]
        if hit:
            w = hit[-1]
            print(f"  {c}: {w['date']}  \"{w['title']}\" — {w['artist']}")
    return 1 if g or dups or bad else 0


if __name__ == "__main__":
    sys.exit(main())
