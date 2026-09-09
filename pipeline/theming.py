#!/usr/bin/env python3
"""theming.py — test the one decision on this site that no source makes.

Every other gate in this pipeline asks whether we reproduced Wikipedia faithfully.
`classify.py` does not reproduce anything: it decides which themed section a sentence
files under, and that decision is ours. The site publishes 12 topic hubs and 303
topic-century pages built ENTIRELY from it -- cross.py calls the topic axis "the half
of the site that is genuinely ours" -- and until this file existed nothing measured it.
The pipeline's own defence was that a mis-filed sentence "looks untidy, it cannot make
the page say anything untrue"; round thirteen already disproved that reasoning for the
Deaths heading, where 910 rows were published as deaths that were accessions. A heading
IS a claim about the row underneath it.

Two independent ground truths, neither of them written by us:

  HEADING  Wikipedia's own "Events > By topic > Religion / Literature / Astronomy"
           headings in the year articles. 2,104 event claims carry one. Editor-written,
           and never used by classify.py, so it is a held-out test set.
  CATEGORY The category graph of the entities a row links, kept as a DIAGNOSTIC and
           deliberately NOT gated. It was built first and it does not work: an entity's
           categories describe that entity's whole existence, not what it is doing in
           this sentence. Corcyra is in "Corinthian colonies" whether the row is about
           founding a colony or about Sparta attacking it, and every Roman commander is
           in "Second Punic War commanders" whatever he does that year. Hand-checking 22
           of its disagreements found our filing right or defensible in most of them, so
           the instrument was measuring itself. Restricting it to non-person, non-place
           links raised agreement from 67% to 80% and it still fails, which is the
           lesson: run controls on a discriminator before you let it charge anyone.

The HEADING test is the gate. A row counts as evidence only where the heading has one
unambiguous reading, so the instrument measures where it is sure and stays quiet
elsewhere -- the same discipline lifedates.py needed.

`--pure` re-derives every theme from the cached similarity matrix and the rules while
IGNORING the source heading, which is the only honest way to test a classifier that now
reads that heading: the gate stays a held-out test of the guessing part.

Exits non-zero when disagreement rises above the accepted baseline (theming.baseline.json).

Usage:
  theming.py [--claims data/claims] [--site data/site] [--cats data/categories.json]
             [--json theming.json] [--baseline theming.baseline.json] [--accept]
             [--show N] [--quiet]
"""
from __future__ import annotations
import argparse, collections, glob, json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------- ground truth 1: headings --
# Only headings whose mapping to one of our themes is unambiguous. "Cities and towns",
# "Arts and sciences" and "Events" are left out on purpose: they span two themes, and a
# test that has to guess is not a test.
HEADING_MAP = {
    "religion": "Religion & Belief",
    "literature": "Culture & Society", "art": "Culture & Society",
    "arts": "Culture & Society", "architecture": "Culture & Society",
    "drama": "Culture & Society", "music": "Culture & Society",
    "culture": "Culture & Society", "philosophy": "Culture & Society",
    "education": "Culture & Society", "sports": "Culture & Society",
    "astronomy": "Science & Discovery", "science": "Science & Discovery",
    "mathematics": "Science & Discovery", "geology": "Science & Discovery",
    "volcanology": "Science & Discovery",
    "medicine": "Health & Medicine",
    "technology": "Technology & Infrastructure",
    "markets": "Economy & Finance", "commerce": "Economy & Finance",
    "economy": "Economy & Finance", "agriculture": "Economy & Finance",
    "exploration": "Exploration & Expansion",
}

# --------------------------------------------------------------- ground truth 2: categories --
CATEGORY_LEXICON: dict[str, str] = {
    "Conflict & Security": r"\b(battles?|sieges?|wars?|warfare|conflicts?|military|"
        r"campaigns?|invasions?|rebellions?|revolts?|uprisings?|insurgen\w+|massacres?|"
        r"mutin\w+|coups? d'état|guerrilla|regiments?|armies|naval|troops)\b",
    "Geopolitics & Diplomacy": r"\b(treaties|treaty|diplomat\w+|elections?|constitutions?|"
        r"peace agreements?|annexations?|partitions?|referendums?|parliaments?|"
        r"legislation|political parties)\b",
    "Economy & Finance": r"\b(banks?|banking|trade|trading|commerce|merchants?|currenc\w+|"
        r"coins?|coinage|mints?|taxation|tariffs?|economic|economy|stock exchanges?|"
        r"guilds?|companies established|fairs)\b",
    "Technology & Infrastructure": r"\b(railways?|railroads?|canals?|bridges?|tunnels?|"
        r"dams?|inventions?|locomotives?|aircraft|engineering|telecommunications?|"
        r"power stations?|patents?|computers?|telegraph\w*|machinery|manufactur\w+)\b",
    "Science & Discovery": r"\b(astronom\w+|comets?|eclipses?|mathematic\w+|physic\w+|"
        r"chemistry|chemists?|scientific|scientists?|naturalists?|botanists?|"
        r"observator\w+|planets?|space ?flight|spacecraft|satellites?)\b",
    "Health & Medicine": r"\b(epidemics?|pandemics?|plagues?|cholera|smallpox|influenza|"
        r"medicine|medical|physicians?|hospitals?|vaccines?|diseases?|public health|"
        r"surgeons?|health care)\b",
    "Climate & Environment": r"\b(earthquakes?|volcan\w+|eruptions?|floods?|flooding|"
        r"hurricanes?|cyclones?|typhoons?|tsunamis?|droughts?|famines?|storms?|"
        r"blizzards?|wildfires|climate|environmental)\b",
    "Culture & Society": r"\b(plays?|novels?|poems?|poetry|operas?|paintings?|sculptures?|"
        r"films?|songs?|albums?|literature|literary|writers?|poets?|dramatists?|"
        r"playwrights?|composers?|artists?|painters?|musicians?|theatres?|theaters?|"
        r"museums?|universities|schools|sports?|football|olympic\w*|festivals?|"
        r"newspapers?|magazines?|architecture|monuments?|statues?)\b",
    "Exploration & Expansion": r"\b(explorers?|expeditions?|voyages?|colonies|colonial|"
        r"circumnavigat\w+|exploration|settlements? established|frontier)\b",
    "Disasters & Accidents": r"\b(disasters?|shipwrecks?|maritime incidents?|"
        r"aviation accidents?|air(?:line|craft)? (?:crashes|accidents)|"
        r"railway accidents?|mining accidents?|explosions?|fires|building collapses?|"
        r"accidents and incidents)\b",
    "Religion & Belief": r"\b(popes?|papacy|papal|bishops?|archbishops?|saints?|churches|"
        r"monasteries|monastic|abbeys|cathedrals?|mosques?|temples?|synagogues?|"
        r"religio\w+|christian\w*|islam\w*|buddhis\w+|hindu\w*|jud(?:aism|aic)|"
        r"catholic\w*|clergy|martyrs?|theolog\w+|missionar\w+)\b",
    "Crime & Justice": r"\b(murders?|murdered|assassinations?|crimes?|criminals?|"
        r"trials?|piracy|pirates?|robberies|kidnapp\w+|prisons?|executions?|"
        r"executed (?:people|criminals))\b",
}
CATEGORY_RX = {k: re.compile(v, re.I) for k, v in CATEGORY_LEXICON.items()}
DATEISH = re.compile(r"^(January|February|March|April|May|June|July|August|September|"
                     r"October|November|December)\s+\d{1,2}$|^-?\d{1,4}(\s*BCE?)?$")

# A person's categories describe a life and a place's categories describe a map; neither
# describes the event the row reports. Corcyra is in "Corinthian colonies" whether the
# sentence is about a colony or about Sparta attacking it, and every Roman commander is
# in "Second Punic War commanders" whatever he is doing in this particular sentence.
# Only the links that ARE the thing that happened -- battles, treaties, plays, sculptures,
# eruptions, aircraft, councils -- carry evidence about the sentence.
PERSONISH = re.compile(r"(?:^|\b)(\d{3,4}s? (?:births|deaths)|Living people|"
                       r"Year of birth|Year of death|People from|"
                       r"\d+(?:st|nd|rd|th)-century .*(?:people|men|women|monarchs|clergy|"
                       r"writers|poets|philosophers|generals))", re.I)
PLACEISH = re.compile(r"(?:^|\b)(Populated places|Cities in|Towns in|Villages in|"
                      r"Geography of|Regions of|Provinces of|Districts of|Capitals|"
                      r"Former capitals|Archaeological sites|colonies|Rivers of|"
                      r"Mountains of|Islands of|Countries|Former countries|"
                      r"States and territories|Subdivisions of)", re.I)


def is_subject_link(cs) -> bool:
    return bool(cs) and not any(PERSONISH.search(c) or PLACEISH.search(c) for c in cs)


def isyear(n: str) -> bool:
    try:
        int(n); return True
    except ValueError:
        return False


def load_claims(claims_dir: str):
    for f in sorted(glob.glob(os.path.join(claims_dir, "*.json"))):
        if not isyear(os.path.basename(f)[:-5]):
            continue
        yield json.load(open(f, encoding="utf-8"))


def heading_of(trail: list[str]) -> str | None:
    if not any(t.strip().lower().startswith("by topic") for t in trail):
        return None
    last = trail[-1].strip().lower()
    return HEADING_MAP.get(last)


def category_vote(links, cats, idf, min_evidence=2.0, ratio=2.0):
    """Expected theme from the categories of the row's entities, or None when the
    evidence is not decisive. Each link votes once per theme (its best-weighted matching
    category) so one over-categorised article cannot outvote the rest of the sentence."""
    score = collections.Counter(); hits = collections.Counter(); ev = collections.defaultdict(list)
    for l in links:
        if DATEISH.match(l or ""):
            continue
        cs = cats.get(l, ())
        if not is_subject_link(cs):
            continue
        best = {}
        for c in cs:
            for theme, rx in CATEGORY_RX.items():
                if rx.search(c):
                    w = idf.get(c, 6.0)
                    if w > best.get(theme, (0, ""))[0]:
                        best[theme] = (w, c)
        for theme, (w, c) in best.items():
            score[theme] += w; hits[theme] += 1; ev[theme].append(c)
    if not score:
        return None
    ranked = score.most_common()
    top, tv = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    if hits[top] < 2 or tv < min_evidence or (second and tv < ratio * second):
        return None
    return top, round(tv, 2), ev[top][:3]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--cats", default=os.path.join(ROOT, "data", "categories.json"))
    ap.add_argument("--json", default=os.path.join(ROOT, "theming.json"))
    ap.add_argument("--baseline", default=os.path.join(ROOT, "theming.baseline.json"))
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--published-only", action="store_true")
    ap.add_argument("--pure", action="store_true",
                    help="re-derive themes from rules+embedding, ignoring the source "
                         "heading, and test that")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    cats = json.load(open(a.cats, encoding="utf-8"))
    df = collections.Counter()
    for v in cats.values():
        df.update(set(v))
    n = max(len(cats), 1)
    idf = {c: math.log(n / (1 + d)) for c, d in df.items()}

    published = set()
    for f in glob.glob(os.path.join(a.site, "*.json")):
        if not isyear(os.path.basename(f)[:-5]):
            continue
        for s in json.load(open(f, encoding="utf-8"))["sections"]:
            for it in s["items"]:
                published.add(it["text"])

    pure = None
    if a.pure:
        import numpy as np
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import classify
        z = np.load(os.path.join(ROOT, "data", "sims.npz"), allow_pickle=True)
        names = list(z["themes"])
        _sims = z["sims"]          # hoisted: indexing the npz re-inflates it every time
        sims = {cid: _sims[i] for i, cid in enumerate(z["ids"])}
        works = {t for t, cs in cats.items() if classify.workish(cs)}

        def pure(c):
            hits = classify.rule_themes(c["text"])
            if "Deaths" in hits:
                return "Deaths"
            p = classify.priority_theme(c["text"], c.get("links"), works)
            if p:
                return p
            sk = sims.get(c["id"])
            if sk is None:
                return c.get("theme")
            hits = [h for h in hits if h in names]
            if hits:
                return max(hits, key=lambda h: sk[names.index(h)])
            return names[int(sk.argmax())]

    res = {"heading": {"n": 0, "agree": 0}, "category": {"n": 0, "agree": 0}}
    conf = {"heading": collections.Counter(), "category": collections.Counter()}
    misses = {"heading": [], "category": []}
    both_bad = []
    for doc in load_claims(a.claims):
        for c in doc["claims"]:
            if c.get("kind") != "event" or c.get("theme") in ("Births", "Deaths"):
                continue
            pub = c["text"] in published
            if a.published_only and not pub:
                continue
            got = pure(c) if pure else c.get("theme")
            if got in ("Births", "Deaths"):
                continue
            h = heading_of(c.get("section_trail") or [])
            v = category_vote(c.get("links") or [], cats, idf)
            for key, exp, why in (("heading", h, None),
                                  ("category", v[0] if v else None, v[2] if v else None)):
                if not exp:
                    continue
                res[key]["n"] += 1
                if exp == got:
                    res[key]["agree"] += 1
                else:
                    conf[key][(exp, got)] += 1
                    misses[key].append({"year": doc["year"], "expected": exp, "got": got,
                                        "text": c["text"][:160], "why": why,
                                        "published": pub})
            if h and v and h == v[0] and h != got:
                both_bad.append({"year": doc["year"], "expected": h, "got": got,
                                 "text": c["text"][:160], "published": pub})

    out = {"heading": res["heading"], "category": res["category"],
           "both_agree_we_differ": len(both_bad),
           "confusion": {k: [[list(p), n] for p, n in v.most_common(25)]
                         for k, v in conf.items()},
           "examples": {k: v[:200] for k, v in misses.items()},
           "both": both_bad[:100]}
    json.dump(out, open(a.json, "w", encoding="utf-8"), indent=1)

    def rate(d):
        return d["agree"] / d["n"] if d["n"] else 1.0
    if not a.quiet:
        for k in ("heading", "category"):
            d = res[k]
            print(f"{k.upper():9s} {d['n']:6d} rows judged   agree {d['agree']:6d} "
                  f"({rate(d):.1%})   disagree {d['n']-d['agree']}")
        print(f"BOTH ground truths agree and we differ: {len(both_bad)}")
        for k in ("heading", "category"):
            print(f"\n  top {k} confusions:")
            for (exp, got), c in conf[k].most_common(8):
                print(f"    {c:5d}  source {exp!r} -> we filed {got!r}")
        for m in misses["category"][:a.show]:
            print(f"\n  {m['year']} exp {m['expected']} got {m['got']}\n    {m['text']}\n    {m['why']}")

    base = {}
    if os.path.exists(a.baseline):
        base = json.load(open(a.baseline, encoding="utf-8"))
    if a.accept:
        json.dump({"heading_disagree": res["heading"]["n"] - res["heading"]["agree"],
                   "category_disagree": res["category"]["n"] - res["category"]["agree"],
                   "both": len(both_bad)}, open(a.baseline, "w"), indent=1)
        print("baseline accepted")
        return 0
    if base:
        bad = False
        for key, now in (("heading_disagree", res["heading"]["n"] - res["heading"]["agree"]),
                         ("category_disagree", res["category"]["n"] - res["category"]["agree"]),
                         ("both", len(both_bad))):
            if now > base.get(key, 10 ** 9):
                print(f"FAIL {key}: {now} > accepted {base[key]}")
                bad = True
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
