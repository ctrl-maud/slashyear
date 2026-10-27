#!/usr/bin/env python3
"""nobel.py — every Nobel Prize, kept only where Wikidata independently agrees.

Primary source : Nobel Prize API v2.1 (CC0)  -> laureates + nobelPrizes
Cross-check    : Wikidata (CC0)               -> P166 (award received) + P585 (point in time)

A (year, category, laureate) row is kept only if Wikidata has a non-deprecated
P166 statement on the laureate's item pointing at the Wikidata item for that
same Nobel category, with a P585 qualifier whose year (precision >= year)
equals the Nobel API awardYear. Everything else goes to `disagreements`.

Writes data/extras/nobel.json; raw responses are cached under data/raw/nobel/ (delete it
to refetch).
"""
import datetime
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXTRAS = os.path.join(ROOT, "data", "extras")
RAW = os.path.join(ROOT, "data", "raw", "nobel")
OUT = os.path.join(EXTRAS, "nobel.json")
UA = "slashyear-data/1.0 (slashyearcom@gmail.com)"
NOBEL = "https://api.nobelprize.org/2.1"
SPARQL = "https://query.wikidata.org/sparql"

# Nobel API English category label -> Wikidata item (labels verified via SPARQL)
CAT_QID = {
    "Physics": "Q38104",
    "Chemistry": "Q44585",
    "Physiology or Medicine": "Q80061",
    "Literature": "Q37922",
    "Peace": "Q35637",
    "Economic Sciences": "Q47170",
}
QID_CAT = {v: k for k, v in CAT_QID.items()}
QID_LABEL = {
    "Q38104": "Nobel Prize in Physics",
    "Q44585": "Nobel Prize in Chemistry",
    "Q80061": "Nobel Prize in Physiology or Medicine",
    "Q37922": "Nobel Prize in Literature",
    "Q35637": "Nobel Peace Prize",
    "Q47170": "Prize in Economic Sciences in Memory of Alfred Nobel",
}

S = requests.Session()
S.headers["User-Agent"] = UA


def get_json(url, params, cache_name):
    path = os.path.join(RAW, cache_name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    for attempt in range(5):
        r = S.get(url, params=params, timeout=60)
        if r.status_code == 200:
            data = r.json()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            time.sleep(0.5)
            return data
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"GET {url} {params} failed: {r.status_code}")


def fetch_all(endpoint, key):
    items, offset, limit = [], 0, 100
    while True:
        d = get_json(f"{NOBEL}/{endpoint}", {"offset": offset, "limit": limit},
                     f"{endpoint}_{offset:05d}.json")
        items.extend(d[key])
        count = d["meta"]["count"]
        offset += limit
        if offset >= count:
            break
    assert len(items) == count, (endpoint, len(items), count)
    return items


def sparql(query, cache_name):
    path = os.path.join(RAW, cache_name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    for attempt in range(6):
        r = S.post(SPARQL, data={"query": query},
                   headers={"Accept": "application/sparql-results+json"}, timeout=120)
        if r.status_code == 200:
            data = r.json()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            time.sleep(2)
            return data
        wait = int(r.headers.get("Retry-After", 10 * (attempt + 1)))
        print(f"  SPARQL {r.status_code}, retry in {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"SPARQL failed: {r.status_code} {r.text[:300]}")


def laureate_name(l):
    if "orgName" in l:
        return l["orgName"]["en"].strip(), "org"
    name = (l.get("knownName") or l.get("fullName") or {}).get("en")
    return (name.strip() if name else name), "person"


def laureate_url(l):
    for ln in l.get("links", []):
        if ln.get("rel") == "external" and "laureate" in (ln.get("class") or []):
            return ln["href"]
    return f"https://www.nobelprize.org/laureate/{l['id']}"


def main():
    os.makedirs(RAW, exist_ok=True)
    retrieved = datetime.date.today().isoformat()

    laureates = fetch_all("laureates", "laureates")
    prizes = fetch_all("nobelPrizes", "nobelPrizes")
    print(f"laureates={len(laureates)} nobelPrizes={len(prizes)}", file=sys.stderr)

    # ---- rows from /laureates -------------------------------------------
    rows = []
    for l in laureates:
        name, kind = laureate_name(l)
        qid = (l.get("wikidata") or {}).get("id")
        for p in l.get("nobelPrizes", []):
            rows.append({
                "year": p["awardYear"],
                "category": p["category"]["en"],
                "name": name,
                "kind": kind,
                "qid": qid,
                "motivation": (p.get("motivation") or {}).get("en"),
                "share": p.get("portion"),
                "prize_status": p.get("prizeStatus"),
                "nobel_url": laureate_url(l),
                "_lid": l["id"],
            })

    # ---- internal consistency: /laureates vs /nobelPrizes ----------------
    from_prizes = {}
    not_awarded = {}
    for p in prizes:
        y, c = p["awardYear"], p["category"]["en"]
        if c not in CAT_QID:
            raise SystemExit(f"unexpected category {c!r}")
        ls = p.get("laureates") or []
        if not ls:
            not_awarded.setdefault(y, []).append(c)
        for l in ls:
            from_prizes[(y, c, l["id"])] = l
    from_laur = {(r["year"], r["category"], r["_lid"]): r for r in rows}
    assert len(from_laur) == len(rows), "duplicate (year,cat,laureate) rows"
    only_l = set(from_laur) - set(from_prizes)
    only_p = set(from_prizes) - set(from_laur)
    if only_l or only_p:
        raise SystemExit(f"Nobel API endpoints disagree: only in laureates={only_l}, only in prizes={only_p}")
    for k, r in from_laur.items():
        pl = from_prizes[k]
        pm = (pl.get("motivation") or {}).get("en")
        if pm != r["motivation"] or pl.get("portion") != r["share"]:
            raise SystemExit(f"Nobel API endpoints disagree on motivation/portion for {k}")
    print(f"rows={len(rows)}; /laureates and /nobelPrizes agree", file=sys.stderr)

    # ---- Wikidata cross-check -------------------------------------------
    qids = sorted({r["qid"] for r in rows if r["qid"]}, key=lambda q: int(q[1:]))
    awards_values = " ".join(f"wd:{q}" for q in CAT_QID.values())
    wd = {}         # input qid -> list of statements
    redirects = {}  # input qid -> target qid
    BATCH = 100
    for i in range(0, len(qids), BATCH):
        chunk = qids[i:i + BATCH]
        q = f"""
SELECT ?input ?item ?award ?st ?rank ?time ?prec ?novalue WHERE {{
  VALUES ?input {{ {' '.join('wd:' + x for x in chunk)} }}
  OPTIONAL {{ ?input owl:sameAs ?redir . }}
  BIND(COALESCE(?redir, ?input) AS ?item)
  ?item p:P166 ?st .
  ?st ps:P166 ?award ; wikibase:rank ?rank .
  VALUES ?award {{ {awards_values} }}
  OPTIONAL {{ ?st pqv:P585 ?tv . ?tv wikibase:timeValue ?time ; wikibase:timePrecision ?prec . }}
  OPTIONAL {{ ?st pq:P585 ?novalue . FILTER(isBlank(?novalue)) }}
}}"""
        print(f"  SPARQL batch {i // BATCH + 1}/{(len(qids) + BATCH - 1) // BATCH}", file=sys.stderr)
        res = sparql(q, f"wd_batch_{i // BATCH:03d}.json")
        for b in res["results"]["bindings"]:
            inp = b["input"]["value"].rsplit("/", 1)[1]
            item = b["item"]["value"].rsplit("/", 1)[1]
            if item != inp:
                redirects[inp] = item
            t = b.get("time", {}).get("value")
            wd.setdefault(inp, []).append({
                "st": b["st"]["value"],
                "award": b["award"]["value"].rsplit("/", 1)[1],
                "rank": b["rank"]["value"].rsplit("#", 1)[1],
                "year": t[:4] if t and t[0] != "-" else None,
                "time": t,
                "prec": int(b["prec"]["value"]) if "prec" in b else None,
            })
    # dedupe (a statement may appear twice if it has two P585 values -> keep each time)
    for k in wd:
        seen, out = set(), []
        for s in wd[k]:
            key = (s["st"], s["time"])
            if key not in seen:
                seen.add(key)
                out.append(s)
        wd[k] = out

    def describe(stmts, award):
        """Precise human-readable description of what Wikidata records."""
        rel = [s for s in stmts if s["award"] == award]
        if not rel:
            others = sorted({f"{QID_LABEL[s['award']]} ({s['award']})"
                             + (f" P585={s['year']}" if s["year"] else "") for s in stmts})
            base = f"no P166 statement for {QID_LABEL[award]} ({award})"
            return base + (f"; other Nobel P166: {', '.join(others)}" if others else "")
        parts = []
        for s in rel:
            if s["time"] is None:
                t = "no P585 qualifier"
            else:
                t = f"P585={s['time'][:10]} (precision {s['prec']})"
            parts.append(f"P166 {QID_LABEL[award]} ({award}), {t}, rank={s['rank']}")
        return "; ".join(parts)

    years, disagreements = {}, []
    kept = 0
    for r in sorted(rows, key=lambda r: (int(r["year"]), list(CAT_QID).index(r["category"]), r["name"] or "")):
        award = CAT_QID[r["category"]]
        nobel_desc = f"{r['category']} {r['year']}"
        if not r["qid"]:
            disagreements.append({
                "year": int(r["year"]), "category": r["category"], "name": r["name"], "qid": None,
                "nobel_api": nobel_desc, "wikidata": "no Wikidata QID given by Nobel API",
                "reason": "no_qid"})
            continue
        stmts = wd.get(r["qid"], [])
        rel = [s for s in stmts if s["award"] == award and s["rank"] != "DeprecatedRank"]
        match = [s for s in rel if s["year"] == r["year"] and s["prec"] is not None and s["prec"] >= 9]
        if match:
            row = {k: r[k] for k in ("category", "name", "kind", "qid", "motivation", "share", "nobel_url")}
            if r["qid"] in redirects:
                row["qid"] = redirects[r["qid"]]
                row["qid_api"] = r["qid"]
            if r["prize_status"] and r["prize_status"] != "received":
                row["prize_status"] = r["prize_status"]
            years.setdefault(r["year"], []).append(row)
            kept += 1
            continue
        if not [s for s in stmts if s["award"] == award]:
            reason = "wikidata_missing_award"
        elif not rel:
            reason = "wikidata_award_deprecated"
        elif all(s["time"] is None for s in rel):
            reason = "wikidata_no_p585"
        elif any(s["year"] == r["year"] for s in rel):
            reason = "wikidata_p585_imprecise"
        else:
            reason = "wikidata_year_differs"
        d = {"year": int(r["year"]), "category": r["category"], "name": r["name"], "qid": r["qid"],
             "nobel_api": nobel_desc, "wikidata": describe(stmts, award), "reason": reason}
        if r["qid"] in redirects:
            d["qid_redirects_to"] = redirects[r["qid"]]
        disagreements.append(d)

    # Wikidata-only claims: Nobel P166 on these items with no matching API row (informational)
    api_keys = {(r["qid"], CAT_QID[r["category"]], r["year"]) for r in rows if r["qid"]}
    api_by_qid = {}
    for r in rows:
        if r["qid"]:
            api_by_qid.setdefault(r["qid"], []).append(f"{r['category']} {r['year']}")
    wd_only = []
    for qid, stmts in wd.items():
        for s in stmts:
            if s["rank"] == "DeprecatedRank" or s["year"] is None:
                continue
            if (qid, s["award"], s["year"]) not in api_keys:
                wd_only.append({"qid": qid, "wikidata": f"P166 {QID_LABEL[s['award']]} ({s['award']}), P585={s['time'][:10]}",
                                "nobel_api": "; ".join(sorted(api_by_qid.get(qid, [])))})

    # ---- enrich disagreements: what is the API's QID, and whom does Wikidata credit? ----
    if disagreements:
        dq = sorted({d["qid"] for d in disagreements if d["qid"]})
        res = sparql(f"""
SELECT ?i ?l ?d WHERE {{
  VALUES ?i {{ {' '.join('wd:' + x for x in dq)} }}
  OPTIONAL {{ ?i rdfs:label ?l FILTER(lang(?l)="en") }}
  OPTIONAL {{ ?i schema:description ?d FILTER(lang(?d)="en") }}
}}""", "wd_disagreement_labels.json")
        lab = {}
        for b in res["results"]["bindings"]:
            lab[b["i"]["value"].rsplit("/", 1)[1]] = (b.get("l", {}).get("value"), b.get("d", {}).get("value"))
        for d in disagreements:
            award = CAT_QID[d["category"]]
            res = sparql(f"""
SELECT DISTINCT ?p ?pl WHERE {{
  ?p p:P166 ?st . ?st ps:P166 wd:{award} ; pq:P585 ?t ; wikibase:rank ?r .
  FILTER(?r != wikibase:DeprecatedRank && YEAR(?t) = {d["year"]})
  OPTIONAL {{ ?p rdfs:label ?pl FILTER(lang(?pl)="en") }}
}}""", f"wd_who_{award}_{d['year']}.json")
            who = sorted({(b["p"]["value"].rsplit("/", 1)[1], b.get("pl", {}).get("value"))
                          for b in res["results"]["bindings"]})
            if d["qid"] in lab:
                l_, d_ = lab[d["qid"]]
                d["wikidata_item"] = f"{d['qid']} = {l_!r}" + (f" ({d_})" if d_ else "")
            d["wikidata_recipients_that_year"] = [f"{q} {n}" for q, n in who]

    out = {
        "retrieved": retrieved,
        "source": {"name": "Nobel Prize API v2.1", "publisher": "Nobel Prize Outreach",
                   "url": "https://www.nobelprize.org/about/developer-zone-2/", "license": "CC0"},
        "checked_against": {"name": "Wikidata", "property": "P166 with P585", "license": "CC0"},
        "years": {y: years[y] for y in sorted(years, key=int)},
        "not_awarded": {y: sorted(not_awarded[y], key=list(CAT_QID).index) for y in sorted(not_awarded, key=int)},
        "disagreements": disagreements,
        "stats": {"rows": len(rows), "kept": kept, "dropped": len(rows) - kept},
    }
    assert out["stats"]["dropped"] == len(disagreements)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(EXTRAS, "nobel-wikidata-only.json"), "w", encoding="utf-8") as f:
        json.dump(wd_only, f, ensure_ascii=False, indent=1)
    print(json.dumps(out["stats"]), file=sys.stderr)
    from collections import Counter
    print("reasons:", Counter(d["reason"] for d in disagreements), file=sys.stderr)
    print("redirects:", redirects, file=sys.stderr)
    print("wikidata-only claims:", len(wd_only), file=sys.stderr)


if __name__ == "__main__":
    main()
