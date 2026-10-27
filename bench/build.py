#!/usr/bin/env python3
"""Build SlashYear-Bench items.jsonl from the slashyear.com static API export.

Reads (read-only) from the site export directory and writes items.jsonl next to
this script. Deterministic: all sampling uses random.Random(SEED).

Usage: python3 build.py [--api DIR]
"""
import argparse
import collections
import datetime
import json
import os
import random
import re
import unicodedata

SEED = 20261027
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_API = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "out", "api")

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MONTH_RE = "|".join(MONTHS)

# ---------------------------------------------------------------- helpers

def load(api, *parts):
    with open(os.path.join(api, *parts), encoding="utf-8") as f:
        return json.load(f)


_TRANS = str.maketrans({"đ": "d", "Đ": "D", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "ß": "ss",
                        "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "ı": "i", "þ": "th", "ð": "d",
                        "ʻ": "", "ʼ": "", "’": "'", "‘": "'"})


def strip_accents(s):
    s = s.translate(_TRANS)
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def norm_text(s):
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- event_year

DATE_PREFIX = re.compile(r"^\s*(%s)\s+(\d{1,2})\s*[–—\-:]\s*(.+)$" % MONTH_RE, re.S)
YEAR_HINT = re.compile(
    r"(?<!\d)\d{4}(?!\d)"              # any 4-digit number
    r"|\b\d+0s\b|'\d0s\b|’\d0s\b"  # decades: 1960s, 60s, '60s
    r"|\b\d+(?:st|nd|rd|th)\b"          # numeric ordinals: 20th, 37th
    r"|\bcentur(?:y|ies)\b|\bmillenni(?:um|a)\b|\bdecades?\b"
    r"|\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|"
    r"eighteenth|nineteenth|twentieth|twenty-first)[- ]century\b"
    r"|\b(?:nineteen|eighteen|seventeen|sixteen|twenty)[- ]?(?:hundred|twenties|thirties|forties|fifties|sixties|seventies|eighties|nineties)\b"
    r"|\bA\.?D\.?\b|\bB\.?C\.?E?\b|\bC\.?E\.?\b",
    re.I)
BAD_CITE_SECTION = re.compile(r"birth|death|holiday|incumbent|population|unknown|unspecified", re.I)
SKIP_CAPS = {"The", "A", "An", "In", "On", "At", "Of", "And", "After", "During",
             "With", "His", "Her", "It", "This", "That", "Following", "By", "For",
             "As", "From", "Some", "Several", "Many", "Two", "Three", "Four"}


def proper_noun_count(sentence):
    toks = re.findall(r"[A-Za-zÀ-ɏ][\wÀ-ɏ'\-]*", sentence)
    n = 0
    for i, t in enumerate(toks):
        if t[0].isupper() and t not in SKIP_CAPS and t not in MONTHS:
            n += 1
    return n


def build_event_year(api, rng, n_target=400):
    seen_years = collections.defaultdict(set)  # normalized text -> years
    cands = []
    # scan every year page (all eras) so the cross-year duplicate check is global
    for fn in os.listdir(os.path.join(api, "year")):
        if not re.fullmatch(r"-?\d+\.json", fn):
            continue
        d = load(api, "year", fn)
        y = d["year"]
        for sec in d.get("sections", []):
            for it in sec.get("items", []):
                m = DATE_PREFIX.match(it.get("text") or "")
                body = m.group(3).strip() if m else (it.get("text") or "").strip()
                seen_years[norm_text(body)].add(y)
                if not (1500 <= y <= 2025) or not m:
                    continue
                if sec["title"] in ("Births", "Deaths"):
                    continue
                cite = it.get("cite") or {}
                if BAD_CITE_SECTION.search(cite.get("section") or ""):
                    continue
                cands.append((y, m.group(1), int(m.group(2)), body, it, sec["title"]))

    def ok(c):
        y, _, _, body, it, _ = c
        words = body.split()
        if len(words) < 8 or len(words) > 70:
            return False
        if YEAR_HINT.search(body):
            return False
        if re.match(r"(?:\d|(?:%s)\b)" % MONTH_RE, body):   # stacked date prefixes ("March 31 – April 1 – ...")
            return False
        if re.search(r"\((?:b|d|born|died)\.", body):
            return False
        if len(seen_years[norm_text(body)]) > 1:
            return False
        if proper_noun_count(body) < 2:   # require named, specific entities
            return False
        return True

    pool = [c for c in cands if ok(c)]
    # de-duplicate identical sentences within a year (same text from several pages)
    uniq = {}
    for c in pool:
        uniq.setdefault((c[0], norm_text(c[3])), c)
    pool = sorted(uniq.values(), key=lambda c: (c[0], norm_text(c[3])))

    # stratify by era so the set is not dominated by the 20th century
    strata = [(1500, 1599, 45), (1600, 1699, 45), (1700, 1799, 50), (1800, 1899, 65),
              (1900, 1949, 55), (1950, 1999, 75), (2000, 2025, 65)]
    assert sum(s[2] for s in strata) == n_target
    out = []
    for lo, hi, k in strata:
        bucket = [c for c in pool if lo <= c[0] <= hi]
        # prefer entries from the main "<year>" article (cleaner, more notable),
        # then cap at 2 items per year to spread across years
        rng.shuffle(bucket)
        bucket.sort(key=lambda c: 0 if c[4]["cite"].get("title") == str(c[0]) else 1)
        per_year = collections.Counter()
        chosen = []
        for cap in (2, 3, 5):   # spread across years; relax the cap only if a sparse era underfills
            for c in bucket:
                if len(chosen) == k:
                    break
                if id(c) in {id(x) for x in chosen} or per_year[c[0]] >= cap:
                    continue
                per_year[c[0]] += 1
                chosen.append(c)
        out.extend(chosen)
    items = []
    for c in out:
        y, mon, day, body, it, sec_title = c
        cite = it["cite"]
        items.append({
            "type": "event_year",
            "question": "In what year did this happen? " + body,
            "answer": y,
            "accept": [str(y)],
            "source": {"kind": "wikipedia_revision", "url": cite["url"], "revid": cite.get("revid"),
                       "page": cite.get("title"),
                       "record": {"year": y, "date": f"{mon} {day}", "text": it["text"],
                                  "section": cite.get("section"), "slashyear_category": sec_title,
                                  "slashyear_api": f"api/year/{y}.json"}},
            "meta": {"era": f"{(y // 100) * 100}s"},
        })
    return items, len(cands), len(pool)


# ---------------------------------------------------------------- number_one

def title_variants(title):
    v = {title}
    t = re.sub(r"^Medley:\s*", "", title, flags=re.I)
    v.add(t)
    no_paren = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", t).strip()
    v.add(no_paren)
    v.add(re.sub(r"\s+", " ", re.sub(r"[\(\)\[\]]", " ", t)).strip())   # "(I Can't Get No) Satisfaction"
    for inner in re.findall(r"[\(\[]([^\)\]]+)[\)\]]", t):              # alternate titles: "Volare (Nel blu dipinto di blu)"
        if len(inner.split()) >= 3 and not re.search(r"(?i)^(feat|from|theme|part|live|with)\b|\b(mix|remix|version|edit)$", inner):
            v.add(inner.strip())
    # double A-sides / medleys: "A" / "B"
    for part in re.split(r"\s*/\s*|\"\s*/\s*\"", no_paren):
        if len(part.strip()) >= 3 and part.strip() != no_paren:
            v.add(part.strip())
    return sorted(x for x in v if x)


def build_number_one(api, rng, n_target=200):
    h = load(api, "hot100.json")
    src = {s["revid"]: s for s in h["sources"]}
    weeks = [w for w in h["weeks"] if "1958-08-04" <= w["date"] <= "2025-12-31"]
    strata = [(1958, 1959, 20), (1960, 1969, 30), (1970, 1979, 30), (1980, 1989, 30),
              (1990, 1999, 30), (2000, 2009, 30), (2010, 2019, 20), (2020, 2025, 10)]
    assert sum(s[2] for s in strata) == n_target
    items = []
    used_songs = set()
    for lo, hi, k in strata:
        bucket = [w for w in weeks if lo <= int(w["date"][:4]) <= hi]
        rng.shuffle(bucket)
        n = 0
        for w in bucket:
            key = (norm_text(w["title"]), norm_text(w["artist"]))
            if key in used_songs:      # one question per song
                continue
            used_songs.add(key)
            dt = datetime.date.fromisoformat(w["date"])
            ds = f"{MONTHS[dt.month - 1]} {dt.day}, {dt.year}"
            s = src.get(w.get("revid"), {})
            items.append({
                "type": "number_one",
                "question": f"Which song was No. 1 on the Billboard Hot 100 chart dated {ds}?",
                "answer": w["title"],
                "accept": title_variants(w["title"]),
                "source": {"kind": "wikipedia_revision", "url": s.get("url"), "revid": w.get("revid"),
                           "page": s.get("title"),
                           "record": {"date": w["date"], "title": w["title"], "artist": w["artist"],
                                      "slashyear_api": "api/hot100.json"}},
                "meta": {"artist": w["artist"], "decade": f"{(dt.year // 10) * 10}s"},
            })
            n += 1
            if n == k:
                break
    return items


# ---------------------------------------------------------------- leader

TITLE_EXCLUDE = re.compile(r"acting|provisional|interim|co-prince|captains regent|regent|"
                           r"president of the confederation|minister of state|^ruler$|vacant|council|junta",
                           re.I)
NAME_EXCLUDE = re.compile(r"vacant|council|junta|committee|directory|regency|triumvirate|none|\?|\bvarious\b", re.I)
GENERIC_NAMES = {"ali", "ahmad", "ahmed", "muhammad", "mohammed", "mahmud", "hassan", "hussein",
                 "abdullah", "ibrahim", "omar", "umar", "said", "salim", "khalid", "faisal", "saud", "hamad"}
THE_FIRST = {"Kingdom", "Republic", "Empire", "Sultanate", "Emirate", "Duchy", "Grand", "Principality",
             "Khanate", "Beylik", "Union", "Federal", "Democratic", "People's", "Islamic", "State",
             "Commonwealth", "Socialist", "United", "Second", "First", "Third", "Fourth", "Fifth", "Free",
             "Federation", "Confederation", "Electorate", "Margraviate", "Landgraviate", "Caliphate",
             "Imamate", "Regency", "Sheikhdom", "Province", "Dominion", "Territory", "Holy", "Ottoman",
             "Orange", "Netherlands", "Philippines", "Bahamas", "Gambia", "Maldives", "Comoros"}
THE_LAST = {"Kingdom", "Empire", "Sultanate", "dynasty", "Republic", "Confederation", "Emirate",
            "Khanate", "shogunate", "Union", "Federation", "Caliphate", "Imamate", "Shogunate",
            "Confederacy", "Protectorate", "Raj", "Commonwealth", "Directorate", "Regency"}


def state_phrase(state):
    s = re.sub(r"\s*\([^()]*\d{3,4}[^()]*\)", "", state).strip()   # drop "(1945–1976)"-style ranges
    parts = [p.strip() for p in s.split(":")]
    if len(parts) == 2:
        s = f"{parts[0]} ({parts[1]})"
    elif len(parts) > 2:
        s = parts[0]
    words = re.sub(r"\(.*?\)", "", s).split()
    if words and (words[0] in THE_FIRST or words[-1] in THE_LAST) and not s.startswith("The "):
        s = "the " + s
    return s


def parse_ranges(quote):
    """Return list of (start, end) tenure ranges from a quote like 'X, King (1810–1828)'."""
    m = re.search(r"\(([^()]*\d{3,4}[^()]*)\)\s*$", quote or "")
    if not m:
        return []
    out = []
    for seg in m.group(1).split(","):
        nums = re.findall(r"\d{3,4}", seg)
        if not nums:
            continue
        a = int(nums[0])
        if len(nums) >= 2:
            b = int(nums[1])
        elif re.search(r"[–\-]\s*$", seg.strip()) or "present" in seg:
            b = 9999
        else:
            b = a
        out.append((a, b))
    return out


def build_leader(api, rng, n_target=250):
    cands = []
    for y in range(1800, 2026):
        d = load(api, "facts", f"{y}.json")
        L = d.get("leaders")
        if not L:
            continue
        for st in L["states"]:
            groups = collections.defaultdict(list)
            for hd in st["holders"]:
                groups[(hd.get("title") or "").strip()].append(hd)
            for title, hs in groups.items():
                if len(hs) != 1 or not title or TITLE_EXCLUDE.search(title):
                    continue
                hd = hs[0]
                name = (hd.get("name") or "").strip()
                if not name or NAME_EXCLUDE.search(name) or len(name) > 45 or not hd.get("qid"):
                    continue
                if "/" in st["state"]:   # composite state labels read badly as questions
                    continue
                toks = [t for t in re.split(r"[\s\-]+", strip_accents(name).lower()) if t]
                if len(toks) == 1 and (len(toks[0]) <= 3 or toks[0] in GENERIC_NAMES):
                    continue          # e.g. "Ali": too generic to grade by string match
                rs = parse_ranges(hd.get("quote"))
                # unambiguous: held the office for the whole year (term neither starts nor ends in y)
                if not any(a < y < b for a, b in rs):
                    continue
                cands.append({"year": y, "state": st["state"], "region": st.get("region"), "title": title, "holder": hd,
                              "src": L.get("source") or {}})
    strata = [(1800, 1849, 45), (1850, 1899, 45), (1900, 1949, 55), (1950, 1999, 60), (2000, 2025, 45)]
    assert sum(s[2] for s in strata) == n_target
    items = []
    used_person = collections.Counter()
    used_state = collections.Counter()
    for lo, hi, k in strata:
        bucket = [c for c in cands if lo <= c["year"] <= hi]
        rng.shuffle(bucket)
        n = 0
        for c in bucket:
            q = c["holder"]["qid"]
            if used_person[q] >= 1 or used_state[c["state"]] >= 2:
                continue
            used_person[q] += 1
            used_state[c["state"]] += 1
            hd = c["holder"]
            title = c["title"]
            sp = state_phrase(c["state"])
            items.append({
                "type": "leader",
                "question": f"Who was the {title} of {sp} in {c['year']}? Answer with the name only.",
                "answer": hd["name"],
                "accept": sorted({hd["name"], hd.get("person") or hd["name"]}),
                "source": {"kind": "wikipedia_revision", "url": c["src"].get("url"), "revid": c["src"].get("revid"),
                           "page": c["src"].get("title"),
                           "record": {"year": c["year"], "state": c["state"], "title": title,
                                      "name": hd["name"], "person": hd.get("person"), "qid": hd["qid"],
                                      "quote": hd.get("quote"), "slashyear_api": f"api/facts/{c['year']}.json"}},
                "meta": {"region": c["region"]},
            })
            n += 1
            if n == k:
                break
    return items, len(cands)


# ---------------------------------------------------------------- cpi

def build_cpi(api, rng, n_target=150):
    p = load(api, "prices.json")
    cpi = {int(k): float(v) for k, v in p["cpi"]["years"].items()}
    years = sorted(y for y in cpi if 1913 <= y <= 2025)
    items = []
    seen = set()
    while len(items) < n_target:
        y1, y2 = rng.sample(years, 2)
        if abs(y2 - y1) < 5 or (y1, y2) in seen:
            continue
        # mostly forward conversions (past -> later), ~20% backward
        if y1 > y2 and rng.random() > 0.2:
            y1, y2 = y2, y1
        if (y1, y2) in seen:
            continue
        seen.add((y1, y2))
        gold = 100.0 * cpi[y2] / cpi[y1]
        items.append({
            "type": "cpi",
            "question": (f"Using the U.S. BLS CPI-U annual average, $100 in {y1} is equivalent to how many "
                         f"dollars in {y2}? Answer with a number."),
            "answer": round(gold, 2),
            "accept": [f"{gold:.2f}"],
            "source": {"kind": "fred_series", "url": p["cpi"]["source"]["url"], "revid": None,
                       "page": p["cpi"]["source"]["name"],
                       "record": {"y1": y1, "y2": y2, "cpi_y1": cpi[y1], "cpi_y2": cpi[y2],
                                  "series": p["cpi"]["source"]["series"], "tolerance": 0.03,
                                  "slashyear_api": "api/prices.json"}},
            "meta": {"direction": "forward" if y2 > y1 else "backward"},
        })
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--out", default=os.path.join(HERE, "items.jsonl"))
    args = ap.parse_args()

    ev, n_ev_cand, n_ev_pool = build_event_year(args.api, random.Random(SEED + 1))
    no1 = build_number_one(args.api, random.Random(SEED + 2))
    ld, n_ld_cand = build_leader(args.api, random.Random(SEED + 3))
    cp = build_cpi(args.api, random.Random(SEED + 4))

    items = []
    for prefix, block in (("ev", ev), ("no1", no1), ("ld", ld), ("cpi", cp)):
        for i, it in enumerate(block):
            it = {"id": f"{prefix}-{i:04d}", **it}
            items.append(it)
    with open(args.out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    stats = {"event_year": {"dated_candidates": n_ev_cand, "after_filters": n_ev_pool, "selected": len(ev)},
             "number_one": {"selected": len(no1)},
             "leader": {"unambiguous_candidates": n_ld_cand, "selected": len(ld)},
             "cpi": {"selected": len(cp)},
             "total": len(items), "seed": SEED}
    with open(os.path.join(HERE, "build_stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
