#!/usr/bin/env python3
"""disagreements.py — every place two sources the build checks against each other disagree.

The build keeps a fact only where independent sources agree. What it throws away is a
record of its own: dates on which Wikipedia and Wikidata contradict each other. This
writes that record, with what each source says and where, and decides nothing about
which one is right.

Three checks feed it:
  - stateleaders.py: a Wikipedia state-leader list's term against the person's Wikidata
    position-held statements (kept only where Wikidata has dated terms of its own);
  - lifedates.py: a birth or death in a Wikipedia year article against the person's
    Wikidata date (only rows where the linked person is the sentence's subject);
  - the Nobel Prize API against Wikidata's award-received statements.

Usage:
  disagreements.py [--extras data/extras] [--site site/out]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
HEAD = re.compile(r"^\s*(?:(?:%s)(?:\s+\d{1,2})?|\d{1,2}\s+(?:%s))[^–—]{0,40}[–—]\s*" % ("|".join(MONTHS), "|".join(MONTHS)))


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


def load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def revids(site_out: str) -> dict:
    """(year, text) -> cite, from the published search shards."""
    idx = load(os.path.join(site_out, "api", "text", "index.json"))
    out = {}
    if not idx:
        return out
    for i in range(idx["shards"]):
        for r in load(os.path.join(site_out, "api", "text", f"d-{i}.json")) or []:
            out[(r[0], r[4])] = {"url": r[5], "title": r[6], "revid": r[7]}
    return out


def leaders(extras: str) -> list[dict]:
    """Rows the list dates and Wikidata dates differently for the same office. A row whose
    Wikidata record simply has no statement for that office (a post Wikidata names
    differently, or not at all) is a gap, not a disagreement, and is left out."""
    import sys
    sys.path.insert(0, HERE)
    from stateleaders import words
    rep = load(os.path.join(extras, "stateleaders-report.json"))
    wdc = load(os.path.join(extras, "stateleaders-wikidata.json"))
    doc = load(os.path.join(extras, "stateleaders.json"))
    if not (rep and wdc and doc):
        return []
    arts = {s["title"]: s for s in doc["sources"]}
    rows = []
    for v in rep["verdicts"]:
        if not (v["reason"] or "").startswith("no Wikidata term agrees") or not v["qid"]:
            continue
        m = re.match(r"^(.*?),\s*([^()]*?)\s*\((\d{3,4})\s*[–-]\s*(\d{3,4})\)\s*$", v["quote"])
        if not m or v["quote"].count("(") != 1:
            continue
        title, a, b = m.group(2), int(m.group(3)), int(m.group(4))
        context = words(title) | words(v["state"])
        item = wdc["wd"].get(v["qid"]) or {}
        same_post = []
        for t in item.get("terms", []):
            label = wdc["pos_label"].get(t["pos"], "")
            if t.get("start") is None or t.get("end") is None or label.lower().startswith("member of"):
                continue
            if words(label) & context:
                same_post.append({"post": label, "start": t["start"], "end": t["end"]})
        if not same_post:
            continue
        art = arts.get(v["article"], {})
        gap = min(max(abs(t["start"] - a), abs(t["end"] - b)) for t in same_post)
        if gap <= 1:
            continue
        rows.append({
            "state": v["state"], "person": v["person"], "post": title or None, "wikidata": v["qid"],
            "wikipedia_says": f"{a}–{b}", "wikipedia_quote": v["quote"],
            "wikipedia_source": {"article": v["article"], "revid": art.get("revid"), "url": art.get("permalink")},
            "wikidata_says": sorted(same_post, key=lambda t: (t["start"], t["end"])),
            "wikidata_url": f"https://www.wikidata.org/wiki/{v['qid']}",
            "difference_years": gap,
            "note": "a gap this large usually means the list links to an article about a different person of the same name" if gap >= 25 else None,
        })
    rows.sort(key=lambda r: (-r["difference_years"], r["state"]))
    return rows


def subject_is(title: str, text: str) -> bool:
    """The linked person is the sentence's subject: every word of the title (outside any
    parenthesis) is in the sentence's first clause. 'X, grandchild of President Y' fails."""
    t = norm(re.sub(r"\(.*?\)", "", title)).split()
    first = norm(HEAD.sub("", text).split(",")[0].split("(")[0]).split()
    return bool(t) and all(w in first for w in t)


def life(site_out: str) -> tuple[list[dict], list[dict]]:
    rep = load(os.path.join(ROOT, "lifedates.json"))
    if not rep:
        return [], []
    cites = revids(site_out)
    years, days = [], []
    for r in rep.get("year_disagrees", []):
        if not subject_is(r["title"], r["text"]):
            continue
        wd = sorted(set(r["wikidata"]))
        if r["year"] in wd:
            continue
        # A row that carries the other life date in brackets was filed under the wrong
        # kind by the classifier, so Wikidata was asked the wrong question: not a conflict.
        other = re.search(r"\((?:b|born)\.?\s*(?:c\.\s*)?(\d{3,4})" if r["kind"] == "birth" else r"\((?:d|died)\.?\s*(?:c\.\s*)?(\d{3,4})", r["text"])
        if other:
            continue
        mark = re.search(r"\((?:d|died)\.?\s*(?:c\.\s*)?(\d{3,4})" if r["kind"] == "birth" else r"\((?:b|born)\.?\s*(?:c\.\s*)?(\d{3,4})", r["text"])
        if mark and int(mark.group(1)) in wd:
            continue
        years.append({"kind": r["kind"], "person": r["title"], "wikipedia_says": r["year"],
                      "wikidata_says": wd, "wikipedia_text": r["text"],
                      "wikipedia_source": cites.get((r["year"], r["text"])),
                      "difference_years": min(abs(r["year"] - w) for w in wd),
                      "approximate": bool(re.search(r"approximate|probable|traditional|\bc\.|circa|uncertain|possibly|\bor\b", r["text"], re.I))})
    for r in rep.get("day_disagrees", []):
        if r["year"] < 1583 or not subject_is(r["title"], r["text"]):
            continue
        def doy(s):
            mo, d = s.split()
            try:
                return dt.date(2001, MONTHS.index(mo) + 1, int(d))
            except (ValueError, IndexError):
                return None
        a = doy(r["printed"])
        bs = [doy(w) for w in r["wikidata"]]
        if not a or not all(bs):
            continue
        gap = min(abs((a - b).days) for b in bs)
        gap = min(gap, 365 - gap)
        days.append({"kind": r["kind"], "person": r["title"], "year": r["year"],
                     "wikipedia_says": r["printed"], "wikidata_says": r["wikidata"],
                     "wikipedia_text": r["text"], "wikipedia_source": cites.get((r["year"], r["text"])),
                     "difference_days": gap,
                     "calendar_note": "a 10-13 day gap is the size of the Julian/Gregorian difference; one source may be giving the old-style date" if 10 <= gap <= 13 else None})
    years.sort(key=lambda x: (-x["difference_years"], x["wikipedia_says"]))
    days.sort(key=lambda x: (x["year"], x["person"]))
    return years, days


def nobel(extras: str) -> list[dict]:
    doc = load(os.path.join(extras, "nobel.json"))
    return doc.get("disagreements", []) if doc else []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extras", default=os.path.join(ROOT, "data", "extras"))
    ap.add_argument("--site", default=os.path.join(ROOT, "site", "out"))
    a = ap.parse_args()
    ld = leaders(a.extras)
    ly, lday = life(a.site)
    nb = nobel(a.extras)
    out = {
        "generated": dt.date.today().isoformat(),
        "what": "Facts on which two sources slashyear checks against each other disagree. Each row gives what each "
                "source says and where; none says which source is right. Leaders' terms and Nobel Prizes are "
                "published only where the sources agree, so those rows were held back. Birth and death lines are "
                "still quoted on year pages exactly as Wikipedia prints them; these rows mark the ones Wikidata "
                "dates differently.",
        "sections": {
            "leaders": {"title": "Leaders' terms: Wikipedia's state-leader lists vs Wikidata",
                        "rule": "Wikidata holds the same office for the person (a post sharing a word with the list's title or state), but no such statement starts and ends within a year of the list's term",
                        "rows": ld},
            "life_years": {"title": "Birth and death years: Wikipedia year articles vs Wikidata",
                           "rule": "the year article files the person's birth or death under a year Wikidata does not give; only rows where the person is the sentence's subject",
                           "rows": ly},
            "life_days": {"title": "Birth and death days: Wikipedia year articles vs Wikidata (1583 on)",
                          "rule": "same year, different calendar day",
                          "rows": lday},
            "nobel": {"title": "Nobel Prizes: the Nobel Prize API vs Wikidata",
                      "rule": "Wikidata has no award-received statement for that prize in that year for the item the API names",
                      "rows": nb},
        },
    }
    for s in out["sections"].values():
        s["count"] = len(s["rows"])
    path = os.path.join(a.extras, "disagreements.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("disagreements:", {k: v["count"] for k, v in out["sections"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
