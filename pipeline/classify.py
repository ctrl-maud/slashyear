#!/usr/bin/env python3
"""classify.py — sort every extracted claim into a thematic section and score it.

Two jobs:

  theme  Each event claim is embedded with BAAI/bge-m3 (the same model the semantic
         index uses) and matched against prototype descriptions per theme, then a
         layer of high-precision lexical rules overrides the embedding where the
         wording is unambiguous (an earthquake is Climate, a papal election is
         Religion). Births and deaths are not themed at all — a one-line person
         descriptor carries too little signal and used to land Jennifer Aniston in
         Economy & Finance — they get their own sections. Theming is a presentation
         decision only: it never changes a claim's wording. It is, however, the only
         decision on this site that no source makes, and round fifteen measured it for
         the first time against the "Events > By topic > Religion / Literature /
         Astronomy" headings the year articles carry: on the 1,921 claims that sit under
         one, the classifier disagreed with the editors on 464. So this file now works
         in three tiers -- the source's own heading where the article states one, a
         layer of priority rules for the two failure modes that measurement exposed,
         then the embedding. See theming.py and SELF-REVIEW-2026-09-08-round15.md.

  weight A year like 1969 yields 300+ sourced claims and the page shows ~10 per
         section, so the rest have to be ranked. Prominence is measured from the
         corpus itself: an entity linked from many different year articles (Rome,
         Napoleon, the Nile) is historically load-bearing, an entity appearing once
         is incidental. That plus a resolved calendar date and a readable length is
         the whole score — no editorial judgement, no model opinion.

Embeddings are cached to data/sims.npz, keyed by claim id. Rule and prototype tuning
is the part that actually gets iterated on, and re-running it should not cost 25 minutes
of GPU each time; pass --recompute when the claim set or the prototypes change.

Usage:
  classify.py [--claims data/claims] [--batch 64] [--recompute]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

THEMES: dict[str, list[str]] = {
    "Geopolitics & Diplomacy": [
        "A head of state takes office, is elected, resigns or is deposed.",
        "Two countries sign a treaty, form an alliance, or open diplomatic relations.",
        "A colony gains independence; a new state is proclaimed; borders are redrawn.",
        "A parliament passes a constitution or a government is formed.",
    ],
    "Conflict & Security": [
        "A war, battle, siege or military invasion takes place.",
        "An army defeats another army; a city falls to besieging forces.",
        "A rebellion, coup, assassination or terrorist attack occurs.",
        "Troops are deployed and fighting causes casualties.",
    ],
    "Economy & Finance": [
        "A stock market crashes; a currency is devalued; a bank fails.",
        "Trade, tariffs, taxation, inflation or unemployment change.",
        "A company is founded, merges, or is nationalised.",
        "A famine of grain prices, coinage or public debt affects an economy.",
    ],
    "Technology & Infrastructure": [
        "A railway, canal, bridge, tunnel or dam opens.",
        "A machine, engine, aircraft or computer is built or first operated.",
        "A telegraph, telephone, radio or broadcast network begins service.",
        "A factory, power station or city water system is constructed.",
    ],
    "Science & Discovery": [
        "A scientist publishes a theory or makes a discovery.",
        "A new element, planet, species or physical law is identified.",
        "A spacecraft is launched or reaches another world.",
        "A mathematical or astronomical observation is recorded.",
    ],
    "Health & Medicine": [
        "An epidemic, plague or pandemic spreads and kills people.",
        "A vaccine, drug, surgical technique or hospital is introduced.",
        "A public health measure such as quarantine or sanitation is imposed.",
        "A disease outbreak affects a population.",
    ],
    "Climate & Environment": [
        "An earthquake, volcanic eruption, flood, hurricane or tsunami strikes.",
        "A drought, harvest failure, cold winter or extreme weather is recorded.",
        "A species goes extinct; a forest, river or reserve is protected or destroyed.",
        "A famine follows crop failure caused by weather.",
    ],
    "Culture & Society": [
        "A book, painting, opera, film, song or building is completed or first performed.",
        "A university, museum, newspaper or sporting competition is founded or held.",
        "A social movement, protest, strike or reform changes daily life.",
        "A festival, marriage, coronation or public ceremony takes place.",
    ],
    "Exploration & Expansion": [
        "An expedition sails, maps a coastline or reaches an unknown land.",
        "Settlers found a colony or a new town in distant territory.",
        "An explorer crosses a desert, mountain range, pole or ocean.",
        "A trade route or passage is opened between distant regions.",
    ],
    "Disasters & Accidents": [
        "A ship sinks, an aircraft crashes, or a train derails, killing passengers.",
        "A mine, factory or building collapses or explodes and kills workers.",
        "A fire destroys a city district, theatre or church.",
        "An industrial accident, oil spill or structural failure causes deaths.",
    ],
    "Religion & Belief": [
        "A pope, caliph, patriarch or other religious leader is appointed or dies.",
        "A church, mosque, temple or monastery is founded or consecrated.",
        "A church council or synod meets; a religious order is founded; a schism divides "
        "a church.",
        "A sacred text is written, translated or canonised; a saint is proclaimed.",
    ],
    "Crime & Justice": [
        "A person is murdered, kidnapped or shot dead by a criminal.",
        "A robbery, burglary or art theft is carried out.",
        "A suspect is arrested, goes on trial, is convicted or is sentenced.",
        "A serial killer, gang or criminal organisation is active or is caught.",
    ],
}
THEME_NAMES = list(THEMES)


# High-precision overrides. Embeddings handle the long tail; these handle the cases
# where one word settles the question and zero-shot similarity does not.
import re as _re

RULES: list[tuple[str, str]] = [
    ("Crime & Justice",
     r"\b(murder\w*|killed by|shoots? and kills|serial killers?|"
     r"robber(?:y|ies)|burglar\w+|is stolen|thefts?|kidnap\w+|hijack\w+|"
     r"is arrested|are arrested|goes? on trial|is sentenced|is convicted|"
     r"is acquitted|death sentence)\b"),
    ("Disasters & Accidents",
     r"\b(crashe[sd]|crash(?:es|ed)?\s+(?:into|near|on|shortly)|derail\w+|"
     r"sinks?|sank|capsiz\w+|shipwreck\w+|collides?|collisions?|"
     r"mine disasters?|collier\w+|blowouts?|oil spills?|stampedes?|"
     r"(?:building|bridge|dam|stand|roof)\s+collapses?|"
     r"Flight\s+\d+|air disasters?|fires? (?:destroys?|breaks? out|sweeps?))\b"),
    ("Climate & Environment",
     r"\b(earthquakes?|volcan\w+|erupt\w+|tsunami|hurricanes?|typhoons?|cyclones?|"
     r"floods?|flooding|droughts?|famines?|wildfires?|blizzards?|tornado(?:es)?|"
     r"landslides?|avalanches?)\b"),
    ("Health & Medicine",
     r"\b(epidemics?|pandemics?|plagues?|choleras?|smallpox|influenza|malaria|typhus|"
     r"vaccines?|vaccinat\w+|outbreaks?|quarantines?|hospitals?)\b"),
    ("Religion & Belief",
     r"\b(Popes?|papal|papacy|antipope|bishops?|archbishops?|patriarchs?|caliphs?|"
     r"monaster\w+|abbeys?|cathedrals?|synods?|canoni[sz]\w+|beatif\w+|"
     r"Councils? of|Ecumenical Council|encyclical|excommunicat\w+)\b"),
    ("Conflict & Security",
     r"\b(Battles? of|sieges? of|invad\w+|invasions?|mutin\w+|massacres?|"
     r"assassinat\w+|coup d'état|rebellions?|uprisings?|declares? war|"
     r"surrenders?|armistice|ceasefire)\b"),
    ("Culture & Society",
     r"\b(premieres?|premiered|television series|feature film|novels?|albums?|"
     r"Olympic Games|Summer Olympics|Winter Olympics|World Series|Super Bowl|"
     r"World Cup|championships?|festivals?|museums?|operas?|symphon\w+|"
     r"first performed|is published|publishes his|publishes her|debuts?)\b"),
    ("Technology & Infrastructure",
     r"\b(railways?|railroads?|canals?|bridges?|tunnels?|dams?|power stations?|"
     r"telegraphs?|patents?|opens to traffic|assembly line|pipelines?)\b"),
    ("Science & Discovery",
     r"\b(spacecraft|space probe|satellites?|orbits?|astronom\w+|comets?|"
     r"solar eclipse|lunar eclipse|telescopes?|periodic table|new species|"
     r"chemical element)\b"),
    ("Economy & Finance",
     r"\b(stock markets?|stock exchanges?|central bank|devalu\w+|inflation|"
     r"tariffs?|bankrupt\w+|recessions?|depressions?|currenc\w+|coinage|"
     r"trade agreements?)\b"),
    ("Exploration & Expansion",
     r"\b(expeditions?|circumnavigat\w+|sets? sail|explorers?|first to reach|"
     r"maps? the coast|founds? the colony|colonis\w+|coloniz\w+)\b"),
    ("Geopolitics & Diplomacy",
     r"\b(treaty of|treaties|signs? a treaty|is inaugurated|is sworn in|"
     r"declares? independence|diplomatic relations|is elected president|"
     r"becomes? Prime Minister|abdicat\w+)\b"),
]
RULES_C = [(name, _re.compile(pat, _re.I)) for name, pat in RULES]

# ---------------------------------------------------------------- the source's heading --
# Wikipedia's year articles file part of their Events section under "By topic" headings
# the editors chose: Religion, Literature, Astronomy, Commerce. Where the article states
# the topic, guessing it is strictly worse than reading it -- and it makes the section a
# sourced fact rather than our opinion, which is the whole premise of the site. Only
# headings with one unambiguous reading are mapped; "Arts and sciences", "Cities and
# towns" and "Events" span two themes and are left to the classifier.
SOURCE_HEADINGS = {
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


def heading_theme(section_trail) -> str | None:
    trail = section_trail or []
    if not any(t.strip().lower().startswith("by topic") for t in trail):
        return None
    return SOURCE_HEADINGS.get(trail[-1].strip().lower())


# ------------------------------------------------------------------- priority rules --
# Two failure modes, both found by measuring against the source headings.
#
# THE WORK, NOT ITS PLOT. An embedding of "Sophocles' play Electra is performed" is an
# embedding of a revenge killing, so it filed under Crime & Justice; "Aeschylus writes
# Seven Against Thebes" filed under Religion, and a bronze statue of a Gaul killing his
# wife filed under Crime as well. What the row reports is that a work was made. Scripture
# is excluded, because a sacred text being compiled really is a religious event.
#
# THE MONEY, NOT THE BUILDING. "The Sienese bankers of the Gran Tavola become the main
# financiers of the Papacy" and "Henry II uses the safes of the Temple Church" both filed
# under Religion: the sentence names a religious institution and the embedding follows
# the noun rather than the transaction.
_SCRIPTURE = _re.compile(
    r"\b(bible|biblical|quran|koran|torah|talmud|vedas?|sutra|gospels?|psalter|"
    r"missal|breviary|scriptures?|hagiograph\w+|liturg\w+|canon law|"
    r"monks?|monastic|monaster\w+|abbeys?|abbots?|priory|priories|nuns?|"
    r"popes?|papal|bishops?|saints?|theolog\w+|sermons?|prayers?)\b", _re.I)
_WORK = (r"play|poem|epic|treatise|book|novel|chronicle|histor(?:y|ies)|essay|"
         r"dictionary|encyclopa?edia|manuscript|codex|opera|symphony|song|hymn|"
         r"painting|fresco|mosaic|statue|sculpture|portrait|romance|saga|comedy|"
         r"tragedy|drama|ballet|poetry|memoir|ode|elegy|satire|fable|dialogue|"
         r"oration|lyric|almanac|atlas|grammar|lexicon")
PRIORITY_RULES: list[tuple[str, str]] = [
    ("Culture & Society",
     rf"\b(?:writes|composes|compiles|translates|paints|sculpts|carves)\b[^.]{{0,70}}"
     rf"\b(?:{_WORK})\b"
     rf"|\b(?:{_WORK})\b[^.]{{0,50}}\bis (?:first )?(?:performed|premiered|staged|"
     rf"produced|published|written|completed|made|created|erected|carved|cast)\b"
     rf"|\b(?:poet|playwright|dramatist|novelist|writer|author|composer|painter|"
     rf"sculptor|historian|chronicler|essayist)s?\b[^.]{{0,70}}"
     rf"\b(?:writes|composes|completes|publishes|paints|sculpts|produces)\b"),
    ("Economy & Finance",
     r"\b(bankers?|financiers?|money-?lenders?|banking|cashiers?|"
     r"(?:is|are) minted|coinage|letters? of credit|bills? of exchange)\b"),
]
PRIORITY_C = [(name, _re.compile(pat, _re.I)) for name, pat in PRIORITY_RULES]

# "Aeschylus writes Seven Against Thebes" names no work noun at all -- the object is a
# title. Wikipedia's own categories say what a title is ("Plays by Aeschylus", "Lost
# sculptures"), so a creation verb whose object is a linked WORK counts too. The category
# file is optional: without it this branch simply does not fire.
_CREATES = _re.compile(r"\b(writes|composes|compiles|translates|paints|sculpts|carves|"
                       r"completes|publishes|produces)\b", _re.I)
WORK_CATEGORY = _re.compile(
    r"\b(plays|novels|poems|poetry|operas|paintings|sculptures|statues|frescoes|mosaics|"
    r"literature|literary works|books|treatises|manuscripts|epic poems|songs|symphonies|"
    r"compositions|dramas|tragedies|comedies|works by|writings|chronicles|"
    r"non-fiction books|history books)\b", _re.I)


def workish(categories) -> bool:
    return any(WORK_CATEGORY.search(c) for c in (categories or ()))


def priority_theme(text: str, links=(), works=frozenset()) -> str | None:
    for name, rx in PRIORITY_C:
        if rx.search(text):
            if name == "Culture & Society" and _SCRIPTURE.search(text):
                return None
            return name
    if works and _CREATES.search(text) and not _SCRIPTURE.search(text):
        if any(l in works for l in (links or ())):
            return "Culture & Society"
    return None

# Year articles record plenty of deaths inside the Events section ("Death of Egyptian
# pharaoh Djet", "Elizabeth Woodville dies in England"); themed by embedding they
# scatter into Conflict or Health, and they belong with the deaths. But "death" is a
# word that appears far more often in sentences about what happened NEXT than in
# sentences about someone dying -- succession is the commonest genre in the whole
# corpus -- so a bare keyword test files accessions, battles and even a birth under
# Deaths. It did: 910 of the 21,721 published death rows were sentences like "Ludovico
# Sforza becomes Duke of Milan upon the death of his nephew", "Jagiellonian University
# is re-established in Krakow" and "Michael Jackson announces his This Is It concert
# residency" (the row's second sentence mentioned his death). A row only reports a
# death when its OWN dated clause does.
_DATE_PREFIX = _re.compile(
    r"^\s*(?:c\.\s*)?(?:[A-Z][a-z]+\s+\d{1,2}(?:\s*[\u2013\u2014-]\s*(?:[A-Z][a-z]+\s+)?\d{1,2})?"
    r"|\d{3,4}(?:\s*BC)?|[A-Z][a-z]+)\s*[\u2013\u2014:-]\s*")
_SENT = _re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")
_DEATH_PRED = _re.compile(
    r"\b(?:is|are|was|were)\s+(?:killed|assassinated|executed|murdered|beheaded|"
    r"put to death|burned at the stake)\b"
    r"|\bcommits? suicide\b"
    r"|\b(?:dies|died)\b(?!\s+(?:in|during)\s+(?:the\s+)?"
    r"(?:battle|siege|fighting|war|earthquake|fire|crash|explosion))", _re.I)
_DEATH_OF = _re.compile(r"\bdeaths? of\b", _re.I)
# "upon/after/following the death of X" is the hinge of a succession sentence: the
# death is the circumstance, someone else's accession is the claim.
_DEATH_SUB = _re.compile(
    r"\b(?:upon|after|on|following|since|before|despite|with|at|by|in|because of|"
    r"due to|amid|during)\s+(?:the\s+)?deaths?\s+of\b", _re.I)


def dated_clause(text: str) -> str:
    """The sentence the row's date is actually about, without its date prefix. Short
    fragments are joined on, so "Pope St. John dies" is not cut at "Pope St."."""
    parts = _SENT.split(_DATE_PREFIX.sub("", text.strip()))
    out = parts[0]
    i = 1
    while len(out) < 40 and i < len(parts):
        out += " " + parts[i]
        i += 1
    return out


def reports_a_death(text: str) -> bool:
    first = dated_clause(text)
    if _DEATH_PRED.search(first):
        return True
    return bool(_DEATH_OF.search(first)) and not _DEATH_SUB.search(first)


def rule_themes(text: str) -> list[str]:
    hits = [name for name, rx in RULES_C if rx.search(text)]
    return (["Deaths"] if reports_a_death(text) else []) + hits


def embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("BAAI/bge-m3", device="cuda", model_kwargs={"torch_dtype": "float16"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--recompute", action="store_true",
                    help="ignore the cached similarity matrix and re-embed on the GPU")
    a = ap.parse_args()

    files = sorted((f for f in os.listdir(a.claims) if f.endswith(".json")),
                   key=lambda f: int(f[:-5]))
    docs = [json.load(open(os.path.join(a.claims, f), encoding="utf-8")) for f in files]

    # ---- corpus-wide entity prominence -------------------------------------------
    link_years: dict[str, set[int]] = {}
    for d in docs:
        for c in d["claims"]:
            for l in c["links"]:
                link_years.setdefault(l, set()).add(d["year"])
    prominence = {k: len(v) for k, v in link_years.items()}
    top = Counter(prominence).most_common(15)
    print("most load-bearing entities:", [f"{k}({v})" for k, v in top])

    # ---- theme assignment ---------------------------------------------------------
    # Embedding the corpus is the only GPU cost in the pipeline and it grows with the
    # site, so the similarity matrix is cached per claim id and only claims the cache
    # has never seen are sent to the GPU. Adding 1,800 year pages therefore embeds the
    # new claims and reuses the rest instead of re-running the whole corpus.
    import numpy as np
    cat_path = os.path.join(ROOT, "data", "categories.json")
    works: set = set()
    if os.path.exists(cat_path):
        cats = json.load(open(cat_path, encoding="utf-8"))
        works = {t for t, cs in cats.items() if workish(cs)}
        print(f"{len(works)} linked titles are works of art or letters per Wikipedia")
    cache_path = os.path.join(ROOT, "data", "sims.npz")
    cache: dict[str, "np.ndarray"] = {}
    if os.path.exists(cache_path) and not a.recompute:
        z = np.load(cache_path, allow_pickle=True)
        if list(z["themes"]) == THEME_NAMES:
            cache = {cid: z["sims"][i] for i, cid in enumerate(z["ids"])}
            print(f"cached similarities available for {len(cache)} claims")
        else:
            print("prototype set changed; recomputing everything")

    texts, index = [], []
    for di, d in enumerate(docs):
        for ci, c in enumerate(d["claims"]):
            if c["kind"] != "event":     # births and deaths get their own sections
                c["theme"] = "Births" if c["kind"] == "birth" else "Deaths"
                c["theme_score"] = None
                continue
            texts.append(c["text"][:400])
            index.append((di, ci))
    ids_all = [docs[di]["claims"][ci]["id"] for di, ci in index]
    need = [k for k, cid in enumerate(ids_all) if cid not in cache]
    print(f"{len(texts)} event claims "
          f"({sum(len(d['claims']) for d in docs) - len(texts)} births/deaths skipped); "
          f"{len(need)} need embedding", flush=True)

    if need:
        m = embedder()
        # Prototypes stay individual: averaging four sentences into one vector washes
        # out the distinctive wording that makes each prototype useful.
        proto_vecs, proto_theme = [], []
        for ti, name in enumerate(THEME_NAMES):
            v = np.asarray(m.encode(THEMES[name], normalize_embeddings=True, batch_size=8))
            proto_vecs.append(v)
            proto_theme += [ti] * len(THEMES[name])
        proto = np.concatenate(proto_vecs, axis=0)
        proto_theme = np.asarray(proto_theme)
        step = 4096
        for start in range(0, len(need), step):
            sub = need[start:start + step]
            emb = m.encode([texts[k] for k in sub], batch_size=a.batch,
                           normalize_embeddings=True, show_progress_bar=False)
            raw = np.asarray(emb) @ proto.T
            sims = np.full((len(sub), len(THEME_NAMES)), -1.0, dtype=np.float32)
            for ti in range(len(THEME_NAMES)):
                sims[:, ti] = raw[:, proto_theme == ti].max(axis=1)
            for j, k in enumerate(sub):
                cache[ids_all[k]] = sims[j]
            print(f"  embedded {min(start + step, len(need))}/{len(need)}", flush=True)

    ruled = 0
    from collections import Counter as _C
    origin = _C()
    for k, (di, ci) in enumerate(index):
        c = docs[di]["claims"][ci]
        sk = cache[ids_all[k]]
        hits = rule_themes(c["text"])
        head = heading_theme(c.get("section_trail"))
        prio = priority_theme(c["text"], c.get("links"), works)
        if "Deaths" in hits:                       # round 13: the row reports a death
            c["theme"], c["theme_rule"], c["theme_from"] = "Deaths", True, "death-rule"
            origin["death-rule"] += 1
        elif head:                                 # round 15: the article says the topic
            c["theme"], c["theme_rule"], c["theme_from"] = head, True, "source"
            origin["source"] += 1
        elif prio:
            c["theme"], c["theme_rule"], c["theme_from"] = prio, True, "priority-rule"
            origin["priority-rule"] += 1
        elif hits:
            # several rules can fire; let the embedding break the tie between them.
            # Rule-only sections (Deaths) have no prototype, so they win outright.
            pick = max(hits, key=lambda h: sk[THEME_NAMES.index(h)])
            if pick != THEME_NAMES[int(sk.argmax())]:
                ruled += 1
            c["theme"], c["theme_rule"], c["theme_from"] = pick, True, "rule"
            origin["rule"] += 1
        else:
            c["theme"] = THEME_NAMES[int(sk.argmax())]
            c["theme_rule"] = False
            c["theme_from"] = "embedding"
            origin["embedding"] += 1
        c["theme_score"] = (round(float(sk[THEME_NAMES.index(c["theme"])]), 4)
                            if c["theme"] in THEME_NAMES else None)
    print(f"lexical rules overrode the embedding on {ruled} claims")
    print("theme decided by: " + ", ".join(f"{k} {v}" for k, v in origin.most_common()))
    if need:
        keys = list(cache)
        np.savez_compressed(cache_path, ids=np.array(keys),
                            sims=np.stack([cache[k] for k in keys]),
                            themes=np.array(THEME_NAMES))
        print(f"cached similarities -> {cache_path} ({len(keys)} claims)")

    # ---- weight -------------------------------------------------------------------
    for d in docs:
        for c in d["claims"]:
            prom = max([prominence.get(l, 1) for l in c["links"]] or [1])
            n = len(c["text"])
            length_fit = 1.0 if 70 <= n <= 260 else (0.6 if n <= 400 else 0.35)
            c["prominence"] = prom
            c["weight"] = round(
                0.55 * math.log1p(prom) / math.log1p(400)
                + 0.25 * (1.0 if c["date"] else 0.0)
                + 0.20 * length_fit, 4)

    for f, d in zip(files, docs):
        json.dump(d, open(os.path.join(a.claims, f), "w", encoding="utf-8"), ensure_ascii=False)

    counts = Counter(c["theme"] for d in docs for c in d["claims"])
    for t in THEME_NAMES + ["Births", "Deaths"]:
        print(f"  {t:28} {counts[t]:6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
