#!/usr/bin/env python3
"""build.py — assemble the page payload for every year.

Selection, ordering and the lead sentence, all of it mechanical:

  sections  Canonical theme order; a section appears only if it has enough entries to
            be worth a heading. Bullets inside a section run in calendar order, undated
            entries last.
  ranking   A modern year has hundreds of sourced entries and a page shows a handful,
            so entries are ranked mainly by notability — the byte length of the
            Wikipedia articles an entry links to, which is the encyclopedia's own
            accumulated judgement of how much there is to say about a thing. Counting
            how many year articles link an entity is kept only as a weak tiebreak: on
            its own it ranks "Spain" above the Apollo 11 Moon landing.
  lead      The muted line under the year heading is the summary the source article's
            own editors wrote — the year montage caption or the lead paragraph — which
            is what makes 1969 open on the Moon landing rather than on whatever ranked
            highest. Where the source has no such summary, the three highest-ranked
            entries stand in verbatim. Either way the lead is a quotation, not a
            characterisation, so it is exactly as checkable as the body.
  citation  Every bullet carries the revision it came from and the section anchor
            inside it, so a reader lands on the exact paragraph.

Usage:
  build.py [--claims data/claims] [--out data/site] [--per-section 10]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
from famous import PEOPLE as CANON_PEOPLE  # noqa: E402

SECTION_ORDER = [
    "Geopolitics & Diplomacy",
    "Conflict & Security",
    "Exploration & Expansion",
    "Religion & Belief",
    "Economy & Finance",
    "Technology & Infrastructure",
    "Science & Discovery",
    "Health & Medicine",
    "Crime & Justice",
    "Disasters & Accidents",
    "Climate & Environment",
    "Culture & Society",
    "Births",
    "Deaths",
]
MIN_PER_SECTION = 2  # default; --min-per-section overrides

# Two shapes that must never reach a page, held here as well as fixed in extract.py
# because a fix in the extractor only reaches the corpus on a full re-extract, and a
# re-extract erases every theme (see README). Both were found by surface.py after the
# country-year harvest changed which rows rank high enough to be published.
COMMENTED = re.compile(r"<!--|-->")          # a line an editor took off the page
DOUBLE_SEP = re.compile(r"^[^–—-]{0,30}[–—-]\s*[–—-]")   # "September 18– – The island of Møn"
# The same editorial notes integrity.py refuses to see on a page ("[sic]", "citation
# needed"): they are the source editor talking about the sentence, not the sentence.
EDITORIAL = re.compile(r"citation needed|clarification needed|\[when\?\]|\[who\?\]|\[sic\]",
                       re.I)


def UNPUBLISHABLE(text: str) -> bool:
    return bool(COMMENTED.search(text) or DOUBLE_SEP.match(text) or EDITORIAL.search(text))

DATEISH = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|"
    r"December)\s+\d{1,2}$|^\d{1,4}s?(\s+(BC|AD|BCE|CE))?$|"
    # End-anchored on purpose: unanchored, this alternative also matched "20th Century
    # Fox", so a real subject was scored as a date link and dropped from the ranking.
    r"^\d{1,2}(st|nd|rd|th)\s+century(\s+(BC|BCE|AD|CE))?$",
    re.I)

# "August 24 – " / "August 28-30 – " at the head of a published row; what a place-article
# twin of the same sentence lacks. Used only to fold duplicates, never to edit text.
DATE_LEAD = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|"
    r"December)\s+\d{1,2}(\s*[–—-]\s*\d{1,2})?\s*[–—:-]\s*")


def prominence_table(docs: list[dict]) -> dict[str, int]:
    """How many distinct year articles link each entity. Calendar links ("January 1")
    appear in hundreds of year articles and mean nothing about importance, so they are
    excluded.

    Counted over the WORLD year articles only. This table is a divisor in weigh(), so
    letting the country-year harvest into it silently re-ranked every existing page: the
    attack on Pearl Harbor and the September 11 attacks both fell off pages they had held
    through sixteen review rounds, because 426,058 new claims moved the prominence of the
    entities they link. The country rows are chosen in their own pool and must not change
    the arithmetic of the pool they were never meant to compete in."""
    link_years: dict[str, set[int]] = {}
    for d in docs:
        for c in d["claims"]:
            if c.get("from_place"):
                continue
            for l in c["links"]:
                if DATEISH.match(l.strip()):
                    continue
                link_years.setdefault(l, set()).add(d["year"])
    return {k: len(v) for k, v in link_years.items()}


def weigh(c: dict, prom: dict[str, int], nota: dict[str, int]) -> float:
    links = [l.strip() for l in c["links"] if not DATEISH.match(l.strip())]

    # Births and deaths are ranked on the person alone, undiscounted.
    #
    # The discount below asks how many other year articles link an entity and treats a
    # high count as genericness, which is right for "Spain" and catastrophically wrong
    # for a person: appearing in many years is exactly what fame looks like. Measured on
    # 62 people anyone would name, only 15 were on the births or deaths list of their own
    # year -- 1879 published Grace Coolidge, Georgia Ann Robinson and Franz von Papen and
    # left out Albert Einstein, whose article is six times longer than any of theirs and
    # who is linked from 40 year articles instead of two. Shakespeare, Newton, Mandela,
    # Elvis, Picasso and Mozart were missing from their own years the same way.
    #
    # A birth or death line has a fixed shape -- "March 14 - Albert Einstein, German-born
    # physicist, Nobel Prize laureate (d. 1955)" -- so its subject is the first link that
    # is not a date, and there is no ambiguity to resolve. Events keep the discounted
    # ranking, which is measured good: 264 of 264 famous events are on their year page.
    if c.get("kind") in ("birth", "death"):
        subject = links[0] if links else ""
        notability = min(1.0, math.log1p(nota.get(subject, 0)) / math.log1p(200_000))
        spread = min(1.0, math.log1p(prom.get(subject, 1)) / math.log1p(250))
        return round(0.72 * notability
                     + 0.16 * spread
                     + 0.12 * (1.0 if c["date"] else 0.0), 5)

    # Size alone still ranks by country: "Spain" is a 400 KB article and appears in a
    # murder in Biscay as readily as in the fall of Granada. What matters is a big
    # article about something SPECIFIC to this year, so an entity's size is discounted
    # by how many other year articles link it. Apollo 11 (big, appears in ~2 years)
    # outranks Spain (big, appears in 200).
    def specific_size(l: str) -> float:
        size = nota.get(l, 0)
        years_linking = prom.get(l, 1)
        generic = min(1.0, math.log1p(max(0, years_linking - 3)) / math.log1p(60))
        return math.log1p(size) * (1.0 - 0.85 * generic)

    best = max([specific_size(l) for l in links] or [0.0])
    notability = min(1.0, best / math.log1p(200_000))
    p = max([prom.get(l, 1) for l in links] or [1])
    spread = min(1.0, math.log1p(p) / math.log1p(250))
    n = len(c["text"])
    # Length was scored as tidiness, and long entries were pushed to 0.35. But on a year
    # page length tracks importance: Wikipedia spends its longest bullet on the biggest
    # thing that happened. With a per-section cap in front of it that penalty deleted the
    # D-Day landings from 1944 and the Apollo 11 launch from 1969 while shorter, lesser
    # entries in the same section survived. Only a stub is now penalised.
    length_fit = 0.5 if n < 70 else 1.0
    return round(0.62 * notability
                 + 0.10 * spread
                 + 0.16 * (1.0 if c["date"] else 0.0)
                 + 0.12 * length_fit, 5)


def anchor_for(trail: list[str]) -> str:
    """Wikipedia section anchor for the deepest heading the claim sat under."""
    if not trail:
        return ""
    return trail[-1].replace(" ", "_")


def sort_key(c: dict):
    return (0 if c["month"] else 1, c["month"] or 13, c["day"] or 32, c["id"])


def as_sentence(body: str) -> str:
    # The body is the source line with its date lead removed, so on a BCE entry written
    # "626 BC - Nabopolassar revolts" what is left starts on the dash. Fine inside a
    # bullet, which shows the whole line, but the lead quotes bodies back to back.
    s = re.sub(r"^[\s,;:.\u2013\u2014-]+", "", body.strip())
    s = re.sub(r"\s*[:;]\s*$", "", s)
    # "c. 3000 BC: ..." is how the source writes an approximate date; upper-casing the
    # first letter turns the quotation into "C. 3000 BC" and reads like a typo.
    if s and s[0].islower() and not re.match(r"c\.\s*\d", s):
        s = s[0].upper() + s[1:]
    if not s.endswith((".", "!", "?")):
        s += "."
    return s


def build_lead(doc: dict, picked: list[dict], label: str) -> tuple[str, str, list[str]]:
    """Returns (lead text, where it came from). Nothing here is composed: a summary we
    wrote ourselves would be the one claim on the page with no source behind it."""
    # lead_items are the three highest-ranked entries of the year, and they are what the
    # decade and century pages show under each year. They used to be returned only when
    # the year had no montage-caption lead of its own -- and every year from 1900 on has
    # one, so the 1900s-2020s decade pages listed years with nothing under them and the
    # 21st-century page had no highlights at all while the 9th had eight.
    events = [c for c in picked if c["kind"] == "event"]
    if doc.get("highlights"):
        # The year's own editors already said what mattered, in the montage caption. Use
        # it to pick which three published entries stand for the year on the decade and
        # century pages: the highest-weighted three for 1969 are two John Lennon bed-ins,
        # while the caption names Apollo 11, Woodstock and Stonewall. Nothing is written
        # here -- the caption only reorders entries we already publish. Matching is
        # clause by clause (the same matcher the montage pins use), not one bag of words
        # over the whole caption: bagged, every candidate shares three-odd words with a
        # nine-image caption and the tie falls back to weight, whose genericness discount
        # ranked foot-and-mouth above September 11 on the 2001 page.
        ordered = caption_clause_matches(doc["highlights"], events, min_keys=2)
        by_id = {c["id"]: c for c in events}
        top = [by_id[i] for i in ordered if i in by_id][:3]
        if len(top) < 3:
            pool = sorted((c for c in events if c not in top), key=lambda c: -c["weight"])
            top += pool[:3 - len(top)]
        top.sort(key=sort_key)
        return doc["highlights"], doc["highlights_from"], [c["text"] for c in top]
    events = sorted(events, key=lambda c: -c["weight"])[:3]
    events.sort(key=sort_key)
    items = [c["text"] for c in events]
    if not events:
        return f"Sourced entries for {label}.", "index", []
    return (" ".join(as_sentence(c["body"]) for c in events),
            "highest-ranked entries", items)


# A handful of source lines open on a back-reference to the sentence above them in the
# article ("That same year, ...", "This was ..."). Quoted alone on a year page the
# reference points at nothing, so the bullet reads as a fragment. Only demonstratives
# are listed: "Meanwhile" or "Subsequently" still state a complete fact.
DANGLING = re.compile(r"^(that same year|that year|the same year|this was|these were|"
                      r"following this|thereafter)\b", re.I)


# ---------------------------------------------------------------- the editors' own picks --
# Every year article from 1900 on carries a montage whose caption names the handful of
# events that year's own editors chose to stand for it. build_lead already uses it to pick
# the three entries the decade and century pages show. It is also the only importance
# signal in the data that we did not invent -- so a caption event that we HARVESTED and
# then dropped to fit a section cap is a hole no case list would have named: 1940 lost
# Dunkirk and the Katyn massacre, 1944 the 20 July plot, 1945 Iwo Jima, 1961 the Bay of
# Pigs, 1971 the Pentagon Papers. Those rows are now pinned into their section on top of
# the cap, which is why a section can run a few entries long on a montage year.
CAPTION_STOP = set("the a an of and in on to for with at by from is are was were as its "
                   "his her their this that it after before during over under into".split())


def _caption_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']{4,}", text.lower()) if w not in CAPTION_STOP}


def caption_clause_matches(caption: str, claims: list[dict], floor: float = 0.25,
                           min_keys: int = 3) -> list[str]:
    """ids of the claims the caption's clauses are talking about, in caption order.

    `min_keys` guards against junk clauses. The montage pins keep 3; the lead picker
    passes 2, because a real clause can be nearly all short words \u2014 "The UK votes to
    leave the EU" carries only {votes, leave} \u2014 and a two-key clause still needs BOTH
    words in the matched row (shared >= 2), which is as specific as three-of-many.
    """
    picks: list[str] = []
    for clause in re.split(r"[;\u2013]|\s+\u2014\s+", caption):
        keys = _caption_words(clause)
        if len(keys) < min_keys:
            continue
        best, score, shared = None, 0.0, 0
        for c in claims:
            common = keys & _caption_words(c["text"])
            hit = len(common) / len(keys)
            if hit > score:
                best, score, shared = c, hit, len(common)
        # One word in common is a coincidence -- "Rudolph the Red-Nosed Reindeer premieres"
        # against "Rudolph Mate, Polish cinematographer" scores 0.25 on the name alone.
        if best is not None and score >= floor and shared >= 2 and best["id"] not in picks:
            picks.append(best["id"])
    return picks


def montage_picks(doc: dict, claims: list[dict], floor: float = 0.25) -> set[str]:
    """ids of the claims that the montage caption is talking about."""
    caption = doc.get("highlights")
    if not caption or doc.get("highlights_from") != "article image footer":
        return set()
    return set(caption_clause_matches(caption, claims, floor))


def place_picks(items: list[dict], cap: int, published: dict[str, int]) -> list[dict]:
    """The best country rows for one section, spread across countries.

    Two levers, and the second one is the point of the whole harvest. Within a section the
    pick is breadth-first: one country's best row, then the next country's, and only once
    every country present has had a turn does anyone get a second row. Across the corpus
    the order of those turns is by how little each country has been published SO FAR --
    `published` is a running count carried through the whole build.

    Without the running count, breadth-first inside one year is not enough. Wikipedia has
    a year article for 897 separate years of Ireland and 38 of Nigeria, and inside any one
    section the countries that win the ties are the ones whose sentences link the biggest
    English articles, which is the same bias measured in COVERAGE-AUDIT.md arriving by a
    different door. Ordering by scarcity means a country with a handful of rows in the
    whole corpus takes its slot ahead of one that has already had thousands.

    It makes the build order-dependent, which is fine because the order is deterministic:
    years are processed in ascending order, every time."""
    by_country: dict[str, list[dict]] = {}
    for c in items:
        by_country.setdefault(c.get("country") or "", []).append(c)
    for v in by_country.values():
        v.sort(key=lambda c: -c["weight"])
    order = sorted(by_country, key=lambda k: (published.get(k, 0), -by_country[k][0]["weight"]))
    out: list[dict] = []
    depth = 0
    while len(out) < cap and any(len(v) > depth for v in by_country.values()):
        for k in order:
            if len(out) >= cap:
                break
            if len(by_country[k]) > depth:
                out.append(by_country[k][depth])
                published[k] = published.get(k, 0) + 1
        depth += 1
    return out


def build_year(doc: dict, prom: dict[str, int], nota: dict[str, int],
               per_section: int, min_per_section: int = MIN_PER_SECTION,
               bd_cap: int | None = None, place_cap: int = 0,
               published: dict[str, int] | None = None) -> dict:
    claims = [c for c in doc["claims"]
              if not DANGLING.match(c["body"].strip()) and not UNPUBLISHABLE(c["text"])]
    for c in claims:
        c["weight"] = weigh(c, prom, nota)

    buckets: dict[str, list[dict]] = {}
    for c in claims:
        buckets.setdefault(c["theme"], []).append(c)

    picks = montage_picks(doc, claims)
    src = doc["source"]
    # A section needs a couple of entries to be worth a heading — except on a thin year
    # where every entry landed in a different theme (AD 122 has five entries across five
    # themes), which would otherwise render as a page with no content at all.
    def assemble(min_per: int):
        sections, used = [], []
        for name in SECTION_ORDER:
            items = buckets.get(name, [])
            # Country-year rows are ADDITIVE, never competitive. Ranked in the same pool
            # they would displace the world-year rows this site is built on -- 1969 has
            # more than 24 Japanese entries alone, and the Moon landing would have lost
            # its slot to them. So the world rows are chosen exactly as before, from the
            # same pool as before, and the country rows are appended under their own cap.
            world = [c for c in items if not c.get("from_place")]
            place = [c for c in items if c.get("from_place")]
            if len(world) < min_per and len(place) < min_per:
                continue
            cap = (per_section if name not in ("Births", "Deaths")
                   else min(per_section, bd_cap or 8))
            chosen = sorted(world, key=lambda c: -c["weight"])[:cap]
            have = {c["id"] for c in chosen}
            chosen += [c for c in items if c["id"] in picks and c["id"] not in have]
            # famous.py's canon is the same kind of signal as the montage caption: a
            # person whose absence from their own year is a defect rides on top of the
            # cap rather than competing under it. 2014 has 10,646 sourced deaths and a
            # cap of 14; García Márquez ranked 15th and fell off the page.
            if name in ("Births", "Deaths"):
                want = "b" if name == "Births" else "d"
                have = {c["id"] for c in chosen}
                for cy, ck, cname in CANON_PEOPLE:
                    if cy != doc["year"] or ck != want:
                        continue
                    if any(cname in c["text"] for c in chosen):
                        continue
                    cands = [c for c in items if cname in c["text"] and c["id"] not in have]
                    if cands:
                        chosen.append(max(cands, key=lambda c: c["weight"]))
            if place_cap:
                pcap = (place_cap if name not in ("Births", "Deaths")
                        else max(1, place_cap // 2))
                chosen += place_picks(place, pcap, published if published is not None else {})
            chosen.sort(key=sort_key)
            used += chosen
            sections.append((name, chosen))
        # A montage pick and a country pick can be the same row, and the same sentence can
        # reach two different themes through two different claims -- one quoted from the
        # world article and one from a country article. Either way the page prints it
        # twice, which reads as a mistake whatever the provenance says. The twins are not
        # always letter-identical: the year article writes "August 24 – Gaspard de
        # Coligny..." and "1572 in France" writes the same sentence with no date lead, so
        # the key folds the lead away — and of the twins we keep the longest text, which
        # is the one that carries the date.
        # Punctuation folds away too (same normalization integrity.py polices): the
        # claims can hold the same sentence from two revisions of the article that
        # differ by one comma, and both variants must not reach the page.
        def dedup_key(t: str) -> str:
            return re.sub(r"\W+", " ", DATE_LEAD.sub("", t).lower()).strip()

        best: dict[str, str] = {}
        for _n, chosen in sections:
            for c in chosen:
                k = dedup_key(c["text"])
                if k not in best or len(c["text"]) > len(best[k][1]):
                    best[k] = (c["id"], c["text"])
        seen_text: set[str] = set()
        deduped = []
        for name, chosen in sections:
            keep = []
            for c in chosen:
                key = dedup_key(c["text"])
                if key in seen_text or best[key][0] != c["id"]:
                    continue
                seen_text.add(key)
                keep.append(c)
            if keep:
                deduped.append((name, keep))
        used = [c for _n, ch in deduped for c in ch]
        return deduped, used

    raw_sections, used = assemble(min_per_section)
    if not raw_sections:
        raw_sections, used = assemble(1)

    # A bullet cites the revision IT came from, which is not always the year article:
    # from 1977 on the deaths live in "Deaths in <month> <year>", harvested by deaths.py
    # and merged into the same claims file carrying their own source.
    def cite_for(c: dict) -> dict:
        cs = c.get("source") or src
        # No anchor when the deepest heading is not a real heading on the source page:
        # deaths lists are re-filed, and a country article's ";February" month term has no
        # id to link to, so a fragment would be a link to somewhere that does not exist.
        anchor = ("" if c.get("from_deaths_list") or c.get("soft_month")
                  else anchor_for(c["section_trail"]))
        return {
            "url": f"{cs['permalink']}#{anchor}" if anchor else cs["permalink"],
            "title": cs["title"],
            "revid": cs["revid"],
            "section": " › ".join(c["section_trail"]),
        }

    sections = []
    for name, chosen in raw_sections:
        sections.append({
            "title": name,
            "items": [{
                "date": c["date"],
                "text": c["text"],
                "cite": cite_for(c),
                # Only country rows carry this. Writing "country": null onto the other
                # 86,000 rows would put a megabyte of nothing into the payload.
                **({"country": c["country"]} if c.get("country") else {}),
            } for c in chosen],
        })
    extra_sources = []
    for c in used:
        cs = c.get("source")
        if cs and cs["revid"] != src["revid"] and cs["revid"] not in [e["revid"] for e in extra_sources]:
            extra_sources.append(cs)

    lead, lead_from, lead_items = build_lead(doc, used, doc["label"])
    return {
        "year": doc["year"],
        "label": doc["label"],
        "lead": lead,
        "lead_from": lead_from,
        "lead_items": lead_items,
        "sections": sections,
        "counts": {"shown": len(used), "available": len(claims)},
        "source": src,
        "extra_sources": extra_sources,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--per-section", type=int, default=10,
                    help="maximum bullets shown per themed section")
    ap.add_argument("--births-deaths", type=int, default=8,
                    help="maximum bullets shown in the Births and Deaths sections")
    ap.add_argument("--min-per-section", type=int, default=MIN_PER_SECTION,
                    help="a section needs this many entries before it gets a heading")
    ap.add_argument("--per-section-place", type=int, default=8,
                    help="country-year bullets appended to each section, spread across "
                         "countries; 0 publishes none of them")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    files = sorted((f for f in os.listdir(a.claims) if f.endswith(".json")),
                   key=lambda f: int(f[:-5]))
    docs = [json.load(open(os.path.join(a.claims, f), encoding="utf-8")) for f in files]
    prom = prominence_table(docs)
    nota_path = os.path.join(ROOT, "data", "notability.json")
    nota = json.load(open(nota_path, encoding="utf-8")) if os.path.exists(nota_path) else {}
    print(f"notability table: {len(nota)} entities")
    print("biggest:", sorted(nota.items(), key=lambda kv: -kv[1])[:6])

    index, empty = [], []
    # The /data page is prose ABOUT this dataset and states its size in words. Those
    # numbers were hand-written once and were already wrong by 580 entries and 118 years
    # before this run: the page claiming every row can be checked is the last page on the
    # site that should carry a number nobody re-derives. They are counted here instead.
    totals = {"entries": 0, "events": 0, "people": 0, "country_entries": 0}
    countries: set[str] = set()
    # Carried across every year so that a country's turn depends on how little of it has
    # been published so far -- see place_picks().
    published_per_country: dict[str, int] = {}
    for f in os.listdir(a.out):            # stale pages from an earlier, smaller run
        if f.endswith(".json"):
            os.remove(os.path.join(a.out, f))
    for d in docs:
        page = build_year(d, prom, nota, a.per_section, a.min_per_section,
                          a.births_deaths, a.per_section_place, published_per_country)
        # A handful of the thinnest ancient years yield no usable entry at all. An empty
        # page is worse than no page: it is a heading with nothing under it, so the year
        # is left out of the site rather than published blank.
        if not page["sections"]:
            empty.append(d["year"])
            continue
        json.dump(page, open(os.path.join(a.out, f"{d['year']}.json"), "w",
                             encoding="utf-8"), ensure_ascii=False)
        index.append({"year": d["year"], "label": d["label"],
                      "sections": len(page["sections"]),
                      "entries": page["counts"]["shown"]})
        for sec in page["sections"]:
            for it in sec["items"]:
                totals["entries"] += 1
                totals["people" if sec["title"] in ("Births", "Deaths") else "events"] += 1
                if it.get("country"):
                    totals["country_entries"] += 1
                    countries.add(it["country"])

    index.sort(key=lambda r: -r["year"])
    totals["years"] = len(index)
    totals["countries"] = len(countries)
    json.dump({"years": index,
               "total": len(index),
               "totals": totals,
               "span": [index[0]["label"], index[-1]["label"]]},
              open(os.path.join(a.out, "index.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    # the 404 page reads this to point an undocumented year at the nearest documented one
    pub = os.path.join(ROOT, "site", "public", "years.json")
    if os.path.isdir(os.path.dirname(pub)):
        json.dump([{"year": r["year"], "label": r["label"]} for r in index],
                  open(pub, "w", encoding="utf-8"), ensure_ascii=False)

    shown = sum(r["entries"] for r in index)
    print(f"pages={len(index)} bullets={shown} avg={shown / len(index):.1f} empty={len(empty)}")
    print(f"  of those: {totals['events']:,} events, {totals['people']:,} births/deaths, "
          f"{totals['country_entries']:,} carry a country ({totals['countries']} countries)")
    if empty:
        print("  empty:", empty)
    return 0


if __name__ == "__main__":
    sys.exit(main())
