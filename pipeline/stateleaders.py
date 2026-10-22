#!/usr/bin/env python3
"""stateleaders.py — who led every state, year by year, quoted from Wikipedia and checked
against Wikidata.

Wikipedia keeps a "List of state leaders in ..." article for each century (two for the
19th and 20th, one per decade since 2000). Each is a tree in wikitext: a state, its
offices, and under each office the people who held it with their years:

    *[[France]]: [[French Fifth Republic|Fifth Republic]]
    :*[[List of presidents of France|Presidents]] ([[...|complete list]]) –
    ::*[[Charles de Gaulle]], President (1959–1969)

Every holder line kept here is quoted as written, with the article's revision id, the
same way the year pages quote their entries. A holder is published for a year only when
two independent records agree on it:

  - the list says the person held the post that year, with plain years or dates (a line
    with "c.", "?", a decade, "early/mid/late", or no link to the person's article is
    not dated firmly enough to use, and is dropped);
  - the person's own Wikidata item has a position-held (P39) or noble-title (P97)
    statement whose start and end years each fall within a year of the list's term,
    and which covers that year. A statement with no end takes the person's death.

A year that only one side has is left out, never guessed. The verdicts and the reason
for every dropped line are written to data/extras/stateleaders-report.json.

Usage:
  stateleaders.py [--out data/extras/stateleaders.json] [--first 1800] [--last 2025]
                  [--pin data/extras/stateleaders-revids.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UA = "slashyear-pipeline/1.0 (https://slashyear.com; ahmadopsr@gmail.com)"
WP_API = "https://en.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
NOW = dt.date.today().year

# (article, first year it covers, last year). Where two cover a year the later wins.
ARTICLES = [
    ("List of state leaders in the 18th century", 1701, 1800),
    ("List of state leaders in the 19th century (1801–1850)", 1801, 1850),
    ("List of state leaders in the 19th century (1851–1900)", 1851, 1900),
    ("List of state leaders in the 20th century (1901–1950)", 1901, 1950),
    ("List of state leaders in the 20th century (1951–2000)", 1951, 2000),
    ("List of state leaders in the 2000s", 2000, 2009),
    ("List of state leaders in the 2010s", 2010, 2019),
    ("List of state leaders in the 2020s", 2020, 2029),
]

S = requests.Session()
S.headers["User-Agent"] = UA


def api(url: str, params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": 2, "maxlag": 5}
    for attempt in range(8):
        try:
            r = S.post(url, data=params, timeout=90)
            if r.status_code == 200:
                d = r.json()
                if d.get("error", {}).get("code") == "maxlag":
                    time.sleep(5 + attempt * 5)
                    continue
                return d
        except requests.RequestException:
            pass
        time.sleep(2 + attempt * 3)
    raise RuntimeError(f"{url} failed: {params.get('action')} {str(params)[:200]}")


def fetch_article(title: str, revid: int | None) -> dict:
    p = {"action": "query", "prop": "revisions", "rvprop": "ids|timestamp|content", "rvslots": "main"}
    p |= {"revids": revid} if revid else {"titles": title}
    page = api(WP_API, p)["query"]["pages"][0]
    rv = page["revisions"][0]
    return {"title": page["title"], "revid": rv["revid"], "timestamp": rv["timestamp"],
            "text": rv["slots"]["main"]["content"]}


# ---------------------------------------------------------------- wikitext -> tree

LINK = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]")


def strip_markup(text: str) -> str:
    """Wikitext of one line, minus everything that is not reader-visible prose or a link."""
    text = re.sub(r"<!--.*?-->", "", text)
    text = re.sub(r"<ref[^>/]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text)
    text = re.sub(r"\[\[(?:File|Image):(?:[^\[\]]|\[\[[^\[\]]*\]\])*\]\]", "", text)
    text = re.sub(r"\{\{(?:nowrap|nobr|small)\|([^{}|]*)\}\}", r"\1", text, flags=re.I)
    for _ in range(3):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"</?(?:small|span|sup|sub|abbr|s|u|b|i)[^>]*>", "", text)
    text = text.replace("'''", "").replace("''", "").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def plain(text: str) -> str:
    return LINK.sub(lambda m: m.group(2) or m.group(1), text).strip()


def target(m: re.Match) -> str:
    t = m.group(1).strip().replace("_", " ")
    return t[:1].upper() + t[1:]


def parse_tree(text: str) -> list[dict]:
    """Bulleted lines as nodes with depth, parent and the modern-country / region heading
    they sit under."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref[^>/]*>.*?</ref>", "", text, flags=re.S)
    nodes: list[dict] = []
    stack: list[dict] = []
    region = group = None
    for raw in text.split("\n"):
        h = re.match(r"^(=+)\s*(.*?)\s*\1\s*$", raw)
        if h:
            if len(h.group(1)) == 2:
                region = plain(strip_markup(h.group(2)))
            group = None
            stack = []
            continue
        g = re.match(r"^''([^'\[\]]+)''\s*$", raw.strip())
        if g:
            group = g.group(1).strip()
            stack = []
            continue
        m = re.match(r"^([*:#]+)\s*(.*)$", raw)
        if not m:
            if strip_markup(raw):         # prose ends the tree; an image or template line does not
                stack = []
            continue
        prefix, body = m.groups()
        if "*" not in prefix and "#" not in prefix:
            continue                      # ":''Colony, 1575–1951''" style notes
        depth = len(prefix)
        while stack and stack[-1]["depth"] >= depth:
            stack.pop()
        node = {"depth": depth, "raw": strip_markup(body), "parent": stack[-1] if stack else None,
                "region": region, "group": group}
        nodes.append(node)
        stack.append(node)
    return nodes


# ---------------------------------------------------------------- dates

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
POINT = re.compile(rf"^(?:(?:\d{{1,2}} )?(?:{MONTHS}) )?(\d{{3,4}})$")
FUZZY = re.compile(r"\bc\.|\bca\.|circa|\?|\d0s\b|early|\bmid|late|\bBC|\bpost-|\bpre-|before|after|around|century", re.I)


def point(s: str) -> int | None:
    m = POINT.match(s.strip().rstrip(",;."))
    return int(m.group(1)) if m else None


def parse_terms(group: str) -> list[tuple[int, int | None]] | None:
    """'1959–1969', '1969', 'since 26 September 2017', '1991–1992, 1996–1999',
    '25 February 2019 – 15 June 2021' -> [(start, end or None if ongoing)].
    None if the group is not a firm date expression."""
    g = group.strip()
    if not g or FUZZY.search(g) or not re.search(r"\d{3,4}", g):
        return None
    terms = []
    for part in re.split(r",\s*(?=\d|since)|;\s*|\s+and\s+", g):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(?:since|from)\s+(.+)$", part, re.I)
        if m:
            s = point(m.group(1))
            if s is None:
                return None
            terms.append((s, None))
            continue
        bits = re.split(r"\s*[–—−-]\s*|\s+to\s+", part)
        if len(bits) == 1:
            s = point(bits[0])
            if s is None:
                return None
            terms.append((s, s))
        elif len(bits) == 2:
            s = point(bits[0])
            if bits[1].strip().lower() in ("present", "incumbent", "today"):
                e = None
            else:
                e = point(bits[1])
                if e is None:
                    return None
            if s is None or (e is not None and e < s):
                return None
            terms.append((s, e))
        else:
            return None
    return terms or None


# ---------------------------------------------------------------- holders

PAREN = re.compile(r"\(([^()]*)\)")


def holder_segments(raw: str) -> list[dict] | None:
    """A holder line -> [{persons, title, terms}], or None if the line is not one.

    The line must open with a link to the person ('[[Charles de Gaulle]], President
    (1959–1969)'); several people may share a title ('[[A]], [[B]], joint Prime
    ministers (1975–1976)'); one person may list several posts separated by ';' or ','."""
    if not raw.startswith("[["):
        return None
    persons = []
    pos = 0
    while True:
        m = LINK.match(raw, pos)
        if not m:
            break
        persons.append((target(m), (m.group(2) or m.group(1)).strip()))
        pos = m.end()
        nxt = re.match(r"\s*(?:,| and)\s*(?=\[\[)", raw[pos:])
        if not nxt:
            break
        pos += nxt.end()
    rest = raw[pos:]
    if len(persons) > 1 and re.match(r"\s*\(", rest):
        # '[[Adolf Hitler]], [[Führer]] (1934–1945)': the last link is the post.
        last = list(LINK.finditer(raw[:pos]))[-1]
        rest = raw[last.start():]
        persons = persons[:-1]
    segs = []
    last = 0
    for m in PAREN.finditer(rest):
        terms = parse_terms(m.group(1))
        if terms is None:
            if re.search(r"\d{3,4}", m.group(1)) and not re.search(r"complete list", m.group(1)):
                return [{"persons": persons, "title": None, "terms": None, "fuzzy": m.group(1)}]
            continue
        title = plain(rest[last:m.start()]).strip(" ,;:–-")
        segs.append({"persons": persons, "title": title or None, "terms": terms})
        last = m.end()
    if not segs:
        return [{"persons": persons, "title": None, "terms": None}] if persons else None
    return segs


def is_office(raw: str) -> bool:
    """'[[President of Italy|Presidents]] ([[...|complete list]]) –', 'Prime ministers –'."""
    return "complete list" in raw or bool(re.search(r"[–—-]\s*$", raw)) or not raw.startswith("[[")


def office_label(node: dict | None, state: dict) -> str | None:
    while node is not None and node is not state:
        if is_office(node["raw"]):
            t = plain(re.sub(r"\(\s*\[\[[^\]]*\|complete list\]\]\s*\)", "", node["raw"]))
            t = re.sub(r"\(\s*complete list\s*\)", "", t).strip(" –-:")
            if t:
                return t
        node = node["parent"]
    return None


def state_of(node: dict) -> dict:
    while node["parent"] is not None:
        node = node["parent"]
    return node


def state_info(st: dict) -> dict:
    links = [target(m) for m in LINK.finditer(st["raw"]) if "complete list" not in (m.group(2) or "")]
    name = re.sub(r"\s*\([^()]*complete list[^()]*\)", "", plain(st["raw"]))
    name = re.sub(r"\s*[–-]\s*$", "", name.strip(" –-:,"))
    return {"name": name, "link": links[0] if links else None}


def extract(article: dict, lo: int, hi: int) -> tuple[list[dict], list[dict]]:
    """Every holder line of one article -> rows (person, terms, state, office, quote);
    plus the lines that could not be used, with the reason."""
    rows, dropped = [], []
    nodes = parse_tree(article["text"])
    consumed = set()
    for n in nodes:
        if n["parent"] is None or id(n) in consumed:
            continue
        if is_office(n["raw"]):
            continue
        segs = holder_segments(n["raw"])
        if not segs:
            continue
        if all(s["terms"] is None and "fuzzy" not in s for s in segs):
            # '[[Muammar Gaddafi]],' with the posts on the lines below it.
            for k in (k for k in nodes if k["parent"] is n):
                consumed.add(id(k))
                last, ks = 0, []
                for m in PAREN.finditer(k["raw"]):
                    t = parse_terms(m.group(1))
                    if t:
                        ks.append({"persons": segs[0]["persons"], "terms": t,
                                   "title": plain(k["raw"][last:m.start()]).strip(" ,;:–-") or None,
                                   "quote": plain(n["raw"]).rstrip(" ,") + ", " + plain(k["raw"])})
                        last = m.end()
                add_rows(rows, dropped, ks, n, article, lo, hi)
            continue
        for s in segs:
            s["quote"] = plain(n["raw"])
        add_rows(rows, dropped, segs, n, article, lo, hi)
    return rows, dropped


def add_rows(rows, dropped, segs, n, article, lo, hi):
    st = state_of(n)
    info = state_info(st)
    office = office_label(n["parent"], st)
    for s in segs:
        if s["terms"] is None:
            dropped.append({"article": article["title"], "line": plain(n["raw"]),
                            "reason": "dates not firm" if "fuzzy" in s else "no dates"})
            continue
        if not any(a <= hi and (b if b is not None else NOW) >= lo for a, b in s["terms"]):
            continue
        for target_title, shown in s["persons"]:
            rows.append({
                "person": target_title, "name": shown, "title": s["title"], "terms": s["terms"],
                "state": info["name"], "state_link": info["link"], "group": n["group"],
                "region": n["region"], "office": office, "quote": s["quote"],
                "article": article["title"], "revid": article["revid"], "lo": lo, "hi": hi,
            })


def split_transitions(rows: list[dict]) -> list[dict]:
    """A ruler who carried over from one state to the next is listed under both with the
    same line ('Gojong, King (1863–1897), Emperor (1897–1907)' under Joseon and under the
    Korean Empire). When the line has one post per state, give each state its own post,
    in order, so Joseon does not get an emperor or West Germany a chancellor of reunified
    Germany."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["person"], r["quote"]), []).append(r)
    drop = set()
    for g in groups.values():
        states = list(dict.fromkeys(r["state"] for r in g))
        posts = list(dict.fromkeys((r["title"], tuple(map(tuple, r["terms"]))) for r in g))
        if 1 < len(states) == len(posts):
            for r in g:
                if states.index(r["state"]) != posts.index((r["title"], tuple(map(tuple, r["terms"])))):
                    drop.add(id(r))
    return [r for r in rows if id(r) not in drop]


# ---------------------------------------------------------------- Wikidata check

def qids_for(titles: list[str]) -> dict[str, str]:
    out = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        q = api(WP_API, {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
                         "titles": "|".join(chunk), "redirects": 1})["query"]
        alias = {t: t for t in chunk}
        for k in ("normalized", "redirects"):
            for r in q.get(k, []):
                for t, v in list(alias.items()):
                    if v == r["from"]:
                        alias[t] = r["to"]
        by_title = {p["title"]: p.get("pageprops", {}).get("wikibase_item")
                    for p in q["pages"] if not p.get("missing")}
        for t, v in alias.items():
            if by_title.get(v):
                out[t] = by_title[v]
    return out


def year_of(snak: dict) -> int | None:
    try:
        v = snak["datavalue"]["value"]
        if v["precision"] < 9:
            return None
        t = v["time"]
        y = int(t[1:t.index("-", 1)])
        return -y if t[0] == "-" else y
    except (KeyError, ValueError):
        return None


def wikidata_terms(qids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        ents = api(WD_API, {"action": "wbgetentities", "ids": "|".join(chunk),
                            "props": "claims|labels", "languages": "en"})["entities"]
        for q, e in ents.items():
            claims = e.get("claims", {})
            death = None
            for c in claims.get("P570", []):
                death = year_of(c["mainsnak"]) or death
            is_human = any(c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") == "Q5"
                           for c in claims.get("P31", []))
            terms = []
            for prop in ("P39", "P97"):
                for c in claims.get(prop, []):
                    if c.get("rank") == "deprecated":
                        continue
                    pos = c["mainsnak"].get("datavalue", {}).get("value", {}).get("id")
                    qual = c.get("qualifiers", {})
                    s = next((year_of(x) for x in qual.get("P580", []) if year_of(x) is not None), None)
                    en = next((year_of(x) for x in qual.get("P582", []) if year_of(x) is not None), None)
                    if s is None:
                        continue
                    terms.append({"pos": pos, "start": s, "end": en})
            out[q] = {"human": is_human, "death": death, "terms": terms,
                      "label": e.get("labels", {}).get("en", {}).get("value")}
    return out


def lifespans(qids: list[str]) -> dict[str, list]:
    """State item -> [year founded (P571), year dissolved (P576)], None where it has none."""
    out = {}
    for i in range(0, len(qids), 50):
        ents = api(WD_API, {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                            "props": "claims"})["entities"]
        for q, e in ents.items():
            c = e.get("claims", {})
            first = [y for x in c.get("P571", []) if (y := year_of(x["mainsnak"])) is not None]
            last = [y for x in c.get("P576", []) if (y := year_of(x["mainsnak"])) is not None]
            out[q] = [min(first) if first else None, max(last) if last else None]
    return out


def trim_to_lifespan(rows: list[dict], life: dict[str, list]) -> int:
    """A list entry often carries a ruler's whole reign past the state's own years, while
    the state before or after lists him too: Emperor Meiji under the Tokugawa shogunate
    until 1912 as well as under the Empire of Japan, Hindenburg under Nazi Germany from
    1925. Outside the years its state existed, an entry keeps a holder only if no other
    entry has that person for that year."""
    seen: dict[tuple[str, int], set[str]] = {}
    for r in rows:
        for y in r["years"]:
            seen.setdefault((r["person"], y), set()).add(r["state"])
    n = 0
    for r in rows:
        start, end = life.get(r["state_link"] or "") or (None, None)
        named = re.search(r"\((\d{4})[–-](\d{4}|present)\)", r["state"])   # 'Union of Burma (1948–1962)'
        if named:
            start, end = int(named.group(1)), (None if named.group(2) == "present" else int(named.group(2)))
        keep = [y for y in r["years"]
                if ((start is None or y >= start) and (end is None or y <= end))
                or seen[(r["person"], y)] == {r["state"]}]
        n += len(r["years"]) - len(keep)
        r["years"] = keep
    return n


def labels_for(qids: list[str]) -> dict[str, str]:
    out = {}
    for i in range(0, len(qids), 50):
        ents = api(WD_API, {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                            "props": "labels", "languages": "en"})["entities"]
        for q, e in ents.items():
            out[q] = e.get("labels", {}).get("en", {}).get("value", "")
    return out


STOP = {"the", "of", "and", "for", "in", "de", "del", "la", "le", "acting", "interim", "joint", "first"}


# Words for the same seat that share no letters: a Pope is the Vatican's sovereign, a
# queen regnant holds the post Wikidata calls "monarch of ...".
SAME = {"queen": "king", "monarch": "king", "sovereign": "king", "pope": "king", "empress": "emperor",
        "premier": "prime", "susuhunan": "sultan"}


def words(text: str | None) -> set[str]:
    return {SAME.get(w, w) for w in re.findall(r"[^\W\d_]{3,}", (text or "").lower()) if w not in STOP}


def verified_years(row: dict, wd: dict | None, pos_label: dict[str, str]) -> tuple[list[int], str | None]:
    """The years of the row's span in which both the list and Wikidata put this person in
    the post. A Wikidata term vouches for a list term when

      - its post's name shares a word with the list's title, office or state ("German
        Emperor" for an Emperor of the German Empire, not "King of Prussia"), and
      - both its start and end are within a year of the list's, or one term sits inside
        the other and they share a start or an end (a reign that Wikidata splits at
        1801, a chancellorship the list splits at reunification).

    Only the years both terms cover are kept, and seats in a legislature ("member of
    ...") never vouch for anything."""
    if wd is None:
        return [], "no Wikidata item"
    if not wd["human"]:
        return [], "Wikidata item is not a person"
    context = words(row["title"]) | words(row["office"]) | words(row["state"])
    years: set[int] = set()
    for s, e in row["terms"]:
        wp_end = e if e is not None else NOW
        for t in wd["terms"]:
            label = pos_label.get(t["pos"], "")
            if label.lower().startswith("member of") or not words(label) & context:
                continue
            wd_end = t["end"]
            if wd_end is None:
                wd_end = wd["death"] if wd["death"] is not None else (NOW if e is None else None)
            if wd_end is None:
                continue
            same_start, same_end = abs(t["start"] - s) <= 1, abs(wd_end - wp_end) <= 1
            nested = (s - 1 <= t["start"] and wd_end <= wp_end + 1) or (t["start"] - 1 <= s and wp_end <= wd_end + 1)
            if not (same_start and same_end) and not (nested and (same_start or same_end)):
                continue
            for y in range(max(s, t["start"]), min(wp_end, wd_end) + 1):
                if row["lo"] <= y <= row["hi"]:
                    years.add(y)
    if not years:
        return [], "no Wikidata term agrees with the list's dates"
    return sorted(years), None


# The official lists in leaders_reference.py, as a gate on the whole method: across these
# offices a published holder-year the official list does not have stops the build.
# (state names as the Wikipedia lists write them, words of the title, words that rule a
# line out, first year to check)
GATES = [
    ("US_PRESIDENT", {"United States"}, ("president",), ("vice",), 1801),
    ("UK_MONARCH", {"United Kingdom of Great Britain and Ireland", "United Kingdom of Great Britain and Northern Ireland",
                    "United Kingdom"}, ("king", "queen", "monarch"), (), 1801),
    ("UK_PRIME_MINISTER", {"United Kingdom of Great Britain and Ireland",
                           "United Kingdom of Great Britain and Northern Ireland", "United Kingdom"}, ("prime",), (), 1801),
    ("CANADA_PRIME_MINISTER", {"Canada", "Dominion of Canada"}, ("prime",), (), 1867),
    ("GERMANY_CHANCELLOR", {"West Germany", "Federal Republic of Germany", "Germany"}, ("chancellor",), (), 1949),
    ("FRANCE_PRESIDENT", {"French Fourth Republic", "France: Fifth Republic", "France"}, ("president",),
     ("council", "minister", "prime"), 1955),
]


def gate(rows: list[dict]) -> list[str]:
    import leaders_reference as ref
    errors = []
    for name, states, want_words, not_words, first in GATES:
        lst = getattr(ref, name)
        for y in range(first, 2026):
            want = {t.split()[-1] for t, lo, hi in lst if lo <= y <= hi}
            for r in rows:
                if y not in r["years"] or r["state"] not in states:
                    continue
                text = f"{r['title'] or ''} {r['office'] or ''}".lower()
                if not any(w in text for w in want_words) or any(w in text for w in not_words):
                    continue
                if not any(w in r["person"] for w in want):
                    errors.append(f"{name} {y}: {r['quote']} (official list: {sorted(want)})")
    return errors


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "extras", "stateleaders.json"))
    ap.add_argument("--first", type=int, default=1800)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--pin", default=os.path.join(ROOT, "data", "extras", "stateleaders-revids.json"),
                    help="article -> revid to reproduce an earlier pull; written after a fresh pull")
    ap.add_argument("--reuse", action="store_true", help="reuse the cached Wikidata answers from the last run")
    a = ap.parse_args()

    pins = json.load(open(a.pin)) if os.path.exists(a.pin) else {}
    sources, rows, dropped = [], [], []
    for title, lo, hi in ARTICLES:
        lo, hi = max(lo, a.first), min(hi, a.last)
        if lo > hi:
            continue
        art = fetch_article(title, pins.get(title))
        sources.append({"title": art["title"], "revid": art["revid"], "timestamp": art["timestamp"],
                        "first": lo, "last": hi,
                        "permalink": f"https://en.wikipedia.org/w/index.php?oldid={art['revid']}"})
        r, d = extract(art, lo, hi)
        rows += split_transitions(r)
        dropped += d
        print(f"{art['title']}: {len(r)} holder rows, {len(d)} undated", file=sys.stderr)
    if not os.path.exists(a.pin):
        json.dump({s["title"]: s["revid"] for s in sources}, open(a.pin, "w"), indent=1, ensure_ascii=False)

    persons = sorted({r["person"] for r in rows})
    cache = os.path.join(os.path.dirname(a.out), "stateleaders-wikidata.json")
    if a.reuse and os.path.exists(cache):
        c = json.load(open(cache))
        qmap, wd, pos_label, smap, life = c["qmap"], c["wd"], c["pos_label"], c.get("smap", {}), c.get("life", {})
    else:
        qmap, wd, pos_label, smap, life = {}, {}, {}, {}, {}
    missing = [p for p in persons if p not in qmap]
    qmap |= qids_for(missing)
    print(f"{len(persons)} people, {len(qmap)} with Wikidata items", file=sys.stderr)
    wd |= wikidata_terms(sorted(set(qmap.values()) - set(wd)))
    pos_label |= labels_for(sorted({t["pos"] for w in wd.values() for t in w["terms"] if t["pos"]} - set(pos_label)))
    smap |= qids_for(sorted({r["state_link"] for r in rows if r["state_link"]} - set(smap)))
    life |= lifespans(sorted(set(smap.values()) - set(life)))
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump({"qmap": qmap, "wd": wd, "pos_label": pos_label, "smap": smap, "life": life}, fh,
                  ensure_ascii=False)

    # A year covered by two articles (2000) is taken from the later one.
    owner = {}
    for s in sources:
        for y in range(s["first"], s["last"] + 1):
            owner[y] = s["title"]

    out_rows, verdicts = [], []
    for r in rows:
        q = qmap.get(r["person"])
        yrs, why = verified_years(r, wd.get(q) if q else None, pos_label)
        yrs = [y for y in yrs if owner.get(y) == r["article"]]
        verdicts.append({"article": r["article"], "state": r["state"], "quote": r["quote"],
                         "person": r["person"], "qid": q, "years": yrs, "reason": why})
        if yrs:
            out_rows.append({k: r[k] for k in ("person", "name", "title", "terms", "state", "state_link",
                                               "group", "region", "office", "quote", "revid")}
                            | {"qid": q, "years": yrs})

    doc = {"built": dt.date.today().isoformat(), "sources": sources,
           "method": "Quoted from Wikipedia's state-leader lists; a holder-year is kept only when the "
                     "person's Wikidata position-held statement agrees with the list's term to within a year.",
           "rows": out_rows}
    cut = trim_to_lifespan(out_rows, {link: life.get(q) for link, q in smap.items()})
    out_rows = [r for r in out_rows if r["years"]]
    print(f"{cut} holder-years moved off a state that did not exist yet or any more", file=sys.stderr)
    errors = gate(out_rows)
    if errors:
        print("stateleaders: disagrees with the official lists:\n  " + "\n  ".join(errors[:30]), file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
    report = os.path.join(os.path.dirname(a.out), "stateleaders-report.json")
    with open(report, "w", encoding="utf-8") as fh:
        json.dump({"verdicts": verdicts, "undated": dropped}, fh, ensure_ascii=False, indent=0)
    kept = sum(1 for v in verdicts if v["years"])
    print(f"stateleaders: {len(rows)} dated rows, {kept} verified, {len(rows) - kept} dropped; "
          f"{len(dropped)} undated lines; {len({(r['state'], y) for r in out_rows for y in r['years']})} state-years",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
