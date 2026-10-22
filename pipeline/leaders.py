#!/usr/bin/env python3
"""leaders.py — who ran every country, year by year, from Wikidata.

A year page can say that a treaty was signed or a war began, but a reader looking at
1970 also wants to know who was in charge: who was President, who was Prime Minister,
who sat on the throne. That table is not in the year articles we harvest, and building
it by hand for two hundred countries and two hundred years would be a second project.
Wikidata already has it, as structured statements, under CC0.

The model is simple and the data is not. A state names its offices with P1906 (office
held by head of state) and P1313 (office held by head of government); a person holds
an office through P39 (position held) with P580/P582 start and end qualifiers. In
practice:

  - Many historical states (Nazi Germany, West Germany, the Third Republic, the Qing)
    carry neither property. For those the offices are found the other way round: an
    office whose P1001 (applies to jurisdiction) is the state and whose class climbs
    through P279 to head of state (Q48352) or head of government (Q2285706). A state
    that still has nothing borrows the offices of its P17 country or its P1366
    successor, clipped to its own lifespan, so West Germany gets the Federal
    Chancellors from 1949 to 1990 and nobody after.
  - Offices are renamed and re-itemised. "Monarch of the United Kingdom" replaced
    "monarch of the United Kingdom of Great Britain and Ireland"; "Prime Minister of
    France" replaced "President of the Council". Each office's P1365/P155 predecessors
    are followed, as long as the predecessor is itself a head-of-state or head-of-
    government office, so a country's page keeps its whole line.
  - One term is often recorded as several statements (one per election), or twice at
    different precisions. Statements are deduplicated, and a person's overlapping or
    back-to-back terms of the same office are merged into one, keeping the most
    precise date that agrees.
  - Old holders often have a start and no end. The end is taken as the next holder's
    start, then the holder's death, then the state's dissolution; only the latest
    holder of a living state is left open as "still in office".

Holders must be humans (P31 Q5): Wikidata also records fictional characters and
regimes ("Dictatorship of Fulgencio Batista") as office holders. Every holder term kept
has a start date, and overlaps 1800 to today and the state's
own lifespan. Year-precision dates are widened to the whole year and marked approx.

Usage:
  leaders.py [--out data/extras/leaders.json] [--site data/site] [--min-sitelinks N]
             [--since 1800-01-01]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import unicodedata

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WDQS = "https://query.wikidata.org/sparql"
UA = "slashyear-build/1.0 (https://slashyear.com; ahmadopsr@gmail.com)"
SOVEREIGN, COUNTRY, HISTORICAL = "Q3624078", "Q6256", "Q3024240"
HOS, HOG = "Q48352", "Q2285706"
NOT_HEADS = {"Q5784340", "Q719039", "Q3273157", "Q203184", "Q2762318", "Q42178", "Q877955"}
ROLE = {"P1906": "head_of_state", "P1313": "head_of_government",
        HOS: "head_of_state", HOG: "head_of_government"}
ACTING = re.compile(r"\b(acting|interim|ad interim|caretaker|provisional)\b", re.I)
ENTITY = "http://www.wikidata.org/entity/"

STATES_QUERY = """SELECT DISTINCT ?s ?label ?links WHERE {
  ?s wdt:P31 wd:%s ; rdfs:label ?label ; wikibase:sitelinks ?links .
  FILTER(LANG(?label) = "en") %s
}"""
ENDED_SINCE = '?s wdt:P576 ?gone . FILTER(?gone >= "%s"^^xsd:dateTime)'
PROPS_QUERY = """SELECT ?s ?p ?v WHERE {
  VALUES ?s { %s }
  VALUES ?p { wdt:P1906 wdt:P1313 wdt:P17 wdt:P1366 }
  ?s ?p ?v .
}"""
LIFESPAN_QUERY = """SELECT ?s ?k ?rank ?t ?prec WHERE {
  VALUES ?s { %s }
  { ?s p:P571 ?st . ?st psv:P571 ?v ; wikibase:rank ?rank .
    ?v wikibase:timeValue ?t ; wikibase:timePrecision ?prec . BIND("from" AS ?k) } UNION
  { ?s p:P576 ?st . ?st psv:P576 ?v ; wikibase:rank ?rank .
    ?v wikibase:timeValue ?t ; wikibase:timePrecision ?prec . BIND("to" AS ?k) }
}"""
ALIAS_QUERY = """SELECT ?s ?alias WHERE {
  VALUES ?s { %s }
  ?s skos:altLabel ?alias . FILTER(LANG(?alias) = "en")
}"""
JURISDICTION_QUERY = """SELECT DISTINCT ?s ?o WHERE {
  VALUES ?s { %s }
  ?o wdt:P1001 ?s ; (wdt:P31|wdt:P279)/wdt:P279* ?sup .
  VALUES ?sup { wd:Q48352 wd:Q2285706 }
}"""
OFFICE_QUERY = """SELECT ?o ?label ?c ?prev WHERE {
  VALUES ?o { %s }
  OPTIONAL { ?o rdfs:label ?label . FILTER(LANG(?label) = "en") }
  OPTIONAL { ?o wdt:P31|wdt:P279 ?c }
  OPTIONAL { ?o wdt:P1365|wdt:P155 ?prev }
}"""
CLASS_QUERY = """SELECT ?c ?sup WHERE {
  VALUES ?c { %s }
  VALUES ?sup { %s }
  ?c wdt:P279* ?sup .
}"""
HOLDERS_QUERY = """SELECT ?office ?person ?label ?st ?start ?sp ?end ?ep ?q ?death WHERE {
  VALUES ?office { %s }
  ?person wdt:P31 wd:Q5 ; p:P39 ?st . ?st ps:P39 ?office ; wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  ?person rdfs:label ?label . FILTER(LANG(?label) = "en")
  OPTIONAL { ?st pqv:P580 [ wikibase:timeValue ?start ; wikibase:timePrecision ?sp ] }
  OPTIONAL { ?st pqv:P582 [ wikibase:timeValue ?end ; wikibase:timePrecision ?ep ] }
  OPTIONAL { ?st pq:P1642|pq:P5102|pq:P2868 ?q }
  OPTIONAL { ?person wdt:P570 ?death }
}"""
LABEL_QUERY = """SELECT ?x ?label WHERE {
  VALUES ?x { %s }
  ?x rdfs:label ?label . FILTER(LANG(?label) = "en")
}"""


def sparql(query: str, tries: int = 6) -> list[dict]:
    cache = os.environ.get("WDQS_CACHE")
    if cache:
        key = os.path.join(cache, hashlib.sha1(query.encode()).hexdigest() + ".json")
        if os.path.exists(key):
            return json.load(open(key, encoding="utf-8"))
        os.makedirs(cache, exist_ok=True)
    rows = _sparql(query, tries)
    if cache:
        json.dump(rows, open(key, "w", encoding="utf-8"))
    return rows


def _sparql(query: str, tries: int) -> list[dict]:
    for attempt in range(tries):
        try:
            r = requests.post(WDQS, data={"query": query, "format": "json"},
                              headers={"User-Agent": UA,
                                       "Accept": "application/sparql-results+json"},
                              timeout=120)
        except requests.RequestException as e:
            print(f"  WDQS: {type(e).__name__}, retrying", file=sys.stderr)
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            print(f"  WDQS: HTTP {r.status_code}, retrying", file=sys.stderr)
            time.sleep(int(r.headers.get("Retry-After", 0) or 0) or 10 * (attempt + 1))
            continue
        r.raise_for_status()
        time.sleep(1)
        return r.json()["results"]["bindings"]
    raise RuntimeError("WDQS kept failing")


def batched(query: str, ids, size: int = 200, *extra) -> list[dict]:
    """Runs query over ids in VALUES batches. A batch WDQS keeps rejecting (usually a
    timeout on a heavy one) is split in half and retried, down to a single id."""
    def run(chunk: list[str]) -> list[dict]:
        q = query % ((" ".join("wd:" + x for x in chunk),) + extra)
        try:
            return sparql(q, 3 if len(chunk) > 1 else 6)
        except RuntimeError:
            if len(chunk) == 1:
                raise
            half = len(chunk) // 2
            return run(chunk[:half]) + run(chunk[half:])

    ids = sorted(ids)
    out: list[dict] = []
    for i in range(0, len(ids), size):
        out += run(ids[i:i + size])
    return out


def qid(b: dict, key: str) -> str | None:
    v = b.get(key, {}).get("value", "")
    return v[len(ENTITY):] if v.startswith(ENTITY) else None


def parse_time(value: str, precision: int, end: bool) -> tuple[dt.date, bool] | None:
    """A Wikidata timestamp -> (date, approx), widened to the edge of its precision."""
    if precision < 9 or value.startswith("-"):
        return None
    y, m, d = (int(x) for x in value.lstrip("+").split("T")[0].split("-"))
    if not 1 <= y <= 9999:
        return None
    if precision == 9:
        return (dt.date(y, 12, 31) if end else dt.date(y, 1, 1)), True
    if precision == 10:
        m = m or 1
        nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
        return (nxt - dt.timedelta(days=1) if end else dt.date(y, m, 1)), True
    try:
        return dt.date(y, m or 1, d or 1), False
    except ValueError:
        return None


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fetch_states(since: dt.date) -> dict[str, dict]:
    states: dict[str, dict] = {}
    for t in (SOVEREIGN, COUNTRY, HISTORICAL):
        alive = ENDED_SINCE % since.isoformat() if t == HISTORICAL else ""
        for b in sparql(STATES_QUERY % (t, alive)):
            s = states.setdefault(qid(b, "s"), {"name": b["label"]["value"], "types": set(),
                                                "links": int(b["links"]["value"]),
                                                "P1906": [], "P1313": [], "P17": [], "P1366": []})
            s["types"].add(t)
    best: dict[tuple, tuple] = {}
    rank = {"PreferredRank": 2, "NormalRank": 1}
    for b in batched(LIFESPAN_QUERY, states):
        r = rank.get(b["rank"]["value"].rsplit("#", 1)[-1], 0)
        if not r:
            continue
        k = (qid(b, "s"), b["k"]["value"])
        p = parse_time(b["t"]["value"], int(b["prec"]["value"]), k[1] == "to")
        if p is None:
            continue
        cur = best.get(k)
        later = cur and (p[0] > cur[1][0] if k[1] == "to" else p[0] < cur[1][0])
        if cur is None or r > cur[0] or (r == cur[0] and later):
            best[k] = (r, p)
    for (s, k), (_, p) in best.items():
        states[s][k] = p[0]
    keep = {}
    for q, s in states.items():
        if s.get("to") and s["to"] < since:
            continue
        if s["types"] == {HISTORICAL} and not s.get("to"):
            continue
        keep[q] = s
    for b in batched(PROPS_QUERY, keep):
        v = qid(b, "v")
        if v:
            keep[qid(b, "s")][b["p"]["value"].rsplit("/", 1)[-1]].append(v)
    for q in [q for q, s in keep.items() if s["types"] == {COUNTRY}]:
        if any(p != q for p in keep[q]["P17"]):
            del keep[q]
    return keep


def fetch_offices(ids) -> dict[str, dict]:
    offices = {}
    for b in batched(OFFICE_QUERY, ids, 150):
        o = offices.setdefault(qid(b, "o"), {"name": None, "classes": set(), "prev": set()})
        if "label" in b:
            o["name"] = b["label"]["value"]
        if qid(b, "c"):
            o["classes"].add(qid(b, "c"))
        if qid(b, "prev"):
            o["prev"].add(qid(b, "prev"))
    classes = {c for o in offices.values() for c in o["classes"]}
    sups: dict[str, set] = {}
    targets = " ".join("wd:" + c for c in sorted(NOT_HEADS | {HOS, HOG}))
    for b in batched(CLASS_QUERY, classes, 150, targets):
        sups.setdefault(qid(b, "c"), set()).add(qid(b, "sup"))
    for o in offices.values():
        hit = set().union(*(sups.get(c, set()) for c in o["classes"])) if o["classes"] else set()
        o["role"] = None if hit & NOT_HEADS else (
            ROLE[HOS] if HOS in hit else ROLE[HOG] if HOG in hit else None)
    return offices


def fetch_holders(office_ids) -> dict[str, list[dict]]:
    stmts: dict[str, dict] = {}
    quals: set[str] = set()
    for b in batched(HOLDERS_QUERY, office_ids, 40):
        st = stmts.setdefault(b["st"]["value"], {"office": qid(b, "office"),
                                                 "qid": qid(b, "person"),
                                                 "name": b["label"]["value"],
                                                 "start": None, "end": None,
                                                 "death": None, "quals": set()})
        if "start" in b:
            p = parse_time(b["start"]["value"], int(b["sp"]["value"]), False)
            if p and (st["start"] is None or p[0] < st["start"][0]):
                st["start"] = p
        if "end" in b:
            p = parse_time(b["end"]["value"], int(b["ep"]["value"]), True)
            if p and (st["end"] is None or p[0] > st["end"][0]):
                st["end"] = p
        if b.get("death", {}).get("type") == "literal":
            st["death"] = parse_time(b["death"]["value"], 11, True)
        if qid(b, "q"):
            st["quals"].add(qid(b, "q"))
            quals.add(qid(b, "q"))
    acting = {qid(b, "x") for b in batched(LABEL_QUERY, quals)
              if ACTING.search(b["label"]["value"])}
    by_office: dict[str, list[dict]] = {}
    for st in stmts.values():
        if st["start"] is None:
            continue
        st["acting"] = bool(st.pop("quals") & acting)
        by_office.setdefault(st.pop("office"), []).append(st)
    return {o: terms(ts) for o, ts in by_office.items()}


def pick(dates: list[tuple], latest: bool) -> tuple:
    """The outermost date of a merged term, preferring a precise date in the same year."""
    edge = max(dates) if latest else min(dates)
    if edge[1]:
        exact = [d for d in dates if not d[1] and d[0].year == edge[0].year]
        if exact:
            return max(exact) if latest else min(exact)
    return edge


def terms(stmts: list[dict]) -> list[dict]:
    """Every statement of one office -> one clean, ordered list of terms."""
    seen, ts = set(), []
    for s in stmts:
        k = (s["qid"], s["start"], s["end"])
        if k not in seen:
            seen.add(k)
            ts.append(dict(s))
    ts.sort(key=lambda t: t["start"][0])
    for t in ts:
        if t["end"] is None:
            nxt = [u["start"] for u in ts if u["qid"] != t["qid"] and u["start"][0] > t["start"][0]]
            if nxt:
                t["end"] = min(nxt)
            elif t["death"] and t["death"][0] >= t["start"][0]:
                t["end"] = t["death"]
    merged: list[dict] = []
    for t in ts:
        mine = [m for m in merged if m["qid"] == t["qid"]]
        last = mine[-1] if mine else None
        if last and (last["end"] is None or
                     t["start"][0] <= last["end"][0] + dt.timedelta(days=1)):
            last["starts"].append(t["start"])
            last["ends"].append(t["end"])
            last["acting"] = last["acting"] and t["acting"]
            continue
        merged.append(dict(t, starts=[t["start"]], ends=[t["end"]]))
    for m in merged:
        m["start"] = pick(m.pop("starts"), False)
        ends = m.pop("ends")
        m["end"] = None if None in ends else pick(ends, True)
    merged.sort(key=lambda t: (t["start"][0], t["name"]))
    return merged


def assign_offices(states: dict, min_links: int) -> dict[str, dict]:
    """state -> {office: role}, from P1906/P1313, then P1001, then the P17/P1366 parent."""
    direct = {o for s in states.values() for p in ("P1906", "P1313") for o in s[p]}
    juris: dict[str, set] = {}
    # A state that names both offices needs no lookup; P1001 alone matches over 100,000
    # offices for the big states (ministries, embassies), so the query keeps only the
    # ones whose class climbs to head of state or government.
    need = [q for q, s in states.items() if not (s["P1906"] and s["P1313"])]
    for b in batched(JURISDICTION_QUERY, need, 25):
        juris.setdefault(qid(b, "s"), set()).add(qid(b, "o"))
    offices = fetch_offices(direct | set().union(*juris.values()))
    frontier = {p for o in offices.values() for p in o["prev"]} - set(offices)
    for _ in range(4):
        if not frontier:
            break
        offices.update(fetch_offices(frontier))
        frontier = {p for o in offices.values() for p in o["prev"]} - set(offices)

    own: dict[str, dict] = {}
    for q, s in states.items():
        roles = {}
        for p in ("P1906", "P1313"):
            for o in s[p]:
                if o in roles and roles[o] != ROLE[p]:
                    roles[o] = "both"
                else:
                    roles.setdefault(o, ROLE[p])
        for role in ("head_of_state", "head_of_government"):
            if not any(r in (role, "both") for r in roles.values()):
                for o in juris.get(q, ()):
                    if offices.get(o, {}).get("role") == role:
                        roles.setdefault(o, role)
        own[q] = roles
    for q, s in states.items():
        if own[q] or s["links"] < min_links:
            continue
        for parent in s["P17"] + s["P1366"]:
            if parent != q and own.get(parent):
                own[q] = dict(own[parent])
                break
    for roles in own.values():
        todo = list(roles)
        while todo:
            o = todo.pop()
            for p in offices.get(o, {}).get("prev", ()):
                role = offices.get(p, {}).get("role")
                if p not in roles and role and roles[o] in (role, "both"):
                    roles[p] = role
                    todo.append(p)
    return own, offices


def iso(d: tuple | None) -> str | None:
    return d[0].isoformat() if d else None


def build(a) -> dict:
    since = dt.date.fromisoformat(a.since)
    today = dt.date.today()
    states = fetch_states(since)
    print(f"  candidate states                     : {len(states)}")
    own, offices = assign_offices(states, a.min_sitelinks)
    holders = fetch_holders({o for roles in own.values() for o in roles})
    print(f"  offices with holders                 : {len(holders)}")

    out = []
    for q, s in states.items():
        lo = max(s.get("from") or since, since)
        hi = min(s.get("to") or today, today)
        offs = []
        for o, role in own[q].items():
            if not offices.get(o, {}).get("name"):
                continue
            hs = []
            for t in holders.get(o, []):
                end = t["end"]
                if end is None and s.get("to"):
                    end = (s["to"], False)
                if t["start"][0] > hi or (end and end[0] < lo):
                    continue
                h = {"qid": t["qid"], "name": t["name"], "start": iso(t["start"]),
                     "end": iso(end), "acting": t["acting"]}
                if t["start"][1] or (end and end[1]):
                    h["approx"] = True
                hs.append(h)
            if hs:
                e = {"role": "head_of_state" if role == "both" else role, "qid": o,
                     "name": offices[o]["name"], "holders": hs}
                if role == "both":
                    e["also_head_of_government"] = True
                offs.append(e)
        if offs:
            offs.sort(key=lambda e: (e["role"] != "head_of_state", e["holders"][0]["start"]))
            out.append({"qid": q, "name": s["name"], "links": s["links"],
                        "from": s["from"].year if s.get("from") else None,
                        "to": s["to"].year if s.get("to") else None, "offices": offs})
    attach_slugs(out, states, a.site)
    out.sort(key=lambda s: (s["name"].lower(), s["from"] or 0))
    for s in out:
        del s["links"]
    return {"source": {"name": "Wikidata", "url": "https://www.wikidata.org",
                       "license": "CC0 1.0", "retrieved": today.isoformat(),
                       "query": HOLDERS_QUERY % "<offices>"},
            "states": out}


def attach_slugs(out: list[dict], states: dict, site: str) -> None:
    """A state that is a country page on the site takes that page's slug, by English
    label first and then by alias, so "People's Republic of China" lands on /china."""
    places = json.load(open(os.path.join(site, "cross", "index.json"), encoding="utf-8"))["places"]
    pages = {p["label"].lower(): p["slug"] for p in places}
    taken: dict[str, dict] = {}
    for s in out:
        slug = pages.get(s["name"].lower())
        if slug and slug not in taken:
            taken[slug] = s
    aliases: dict[str, list[str]] = {}
    for b in batched(ALIAS_QUERY, [s["qid"] for s in out if s not in taken.values()]):
        aliases.setdefault(qid(b, "s"), []).append(b["alias"]["value"].lower())
    cands = sorted((s for s in out if s not in taken.values()),
                   key=lambda s: (s["to"] is not None, -s["links"]))
    for s in cands:
        for al in aliases.get(s["qid"], ()):
            slug = pages.get(al)
            if slug and slug not in taken:
                taken[slug] = s
                break
    for slug, s in taken.items():
        s["slug"], s["page"] = slug, True
    used = set(taken)
    for s in sorted(out, key=lambda s: (s["to"] is not None, -s["links"])):
        if "slug" in s:
            continue
        slug = slugify(s["name"]) or s["qid"].lower()
        if slug in used:
            slug = f"{slug}-{s['from']}" if s["from"] else f"{slug}-{s['qid'].lower()}"
        used.add(slug)
        s["slug"] = slug
    for s in out:
        page = s.pop("page", None)
        offs = s.pop("offices")
        if page:
            s["page"] = True
        s["offices"] = offs


def in_office(data: dict, slug: str, day: str) -> list[str]:
    s = next((s for s in data["states"] if s["slug"] == slug), None)
    if s is None:
        return [f"{slug}: (missing)"]
    rows = []
    for o in s["offices"]:
        who = [h["name"] + (" (acting)" if h["acting"] else "")
               for h in o["holders"] if h["start"] <= day and (h["end"] is None or h["end"] >= day)]
        role = "HoS+HoG" if o.get("also_head_of_government") else \
            "HoS" if o["role"] == "head_of_state" else "HoG"
        rows.append(f"  {s['name']} {role} {o['name']}: {', '.join(who) or '-'}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "extras", "leaders.json"))
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--since", default="1800-01-01")
    ap.add_argument("--min-sitelinks", type=int, default=40,
                    help="a state with no offices of its own borrows its parent's only above this")
    ap.add_argument("--check", nargs="*", metavar="SLUG@DATE",
                    help="print who was in office, e.g. united-states@1970-06-01")
    a = ap.parse_args()

    data = build(a)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    n = sum(len(o["holders"]) for s in data["states"] for o in s["offices"])
    print(f"  states                               : {len(data['states'])}")
    print(f"  holder terms                         : {n}")
    print(f"leaders -> {a.out}")
    for c in a.check or ():
        slug, day = c.split("@")
        print(f"{slug} on {day}:")
        print("\n".join(in_office(data, slug, day)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
