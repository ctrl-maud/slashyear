#!/usr/bin/env python3
"""Score cached model responses for SlashYear-Bench.

Reads items.jsonl and results/raw/<model>.jsonl, writes results/<model>.jsonl
(id, type, response, correct, extra) and summary.json, and prints a table.

Usage: python3 score.py [--spotcheck N]
"""
import argparse
import collections
import datetime
import difflib
import json
import os
import random
import re
import statistics
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
TYPES = ["event_year", "number_one", "leader", "cpi"]

_TRANS = str.maketrans({"đ": "d", "Đ": "D", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "ß": "ss",
                        "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "ı": "i", "þ": "th", "ð": "d",
                        "ʻ": "", "ʼ": "", "’": "'", "‘": "'", "“": '"', "”": '"'})


def fold(s):
    s = (s or "").translate(_TRANS)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return s.lower()


# ---------------------------------------------------------------- event_year

def score_event(item, resp):
    m = re.search(r"(?<!\d)(\d{3,4})(?!\d)", resp or "")
    if not m:
        return False, {"pred": None, "abs_err": None, "within1": False}
    pred = int(m.group(1))
    if re.search(r"\b(?:BC|BCE)\b", resp or ""):
        pred = -pred
    err = abs(pred - item["answer"])
    return err == 0, {"pred": pred, "abs_err": err, "within1": err <= 1}


# ---------------------------------------------------------------- number_one

def norm_title(s):
    s = fold(s)
    s = re.sub(r"^medley:\s*", "", s)
    s = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", s)       # ignore parentheticals
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_candidates(resp):
    r = (resp or "").strip()
    first = r.splitlines()[0] if r else ""
    cands = {r, first}
    for q in re.findall(r'"([^"]+)"|“([^”]+)”|\*\*([^*]+)\*\*', r.translate({0x201C: '"', 0x201D: '"'})):
        cands.update(x for x in q if x)
    for c in list(cands):
        for sep in (r"\s+by\s+", r"\s+[–—-]\s+", r"\s*,\s*by\s+", r"\s*—\s*"):
            cands.add(re.split(sep, c, maxsplit=1)[0])
    return {norm_title(c) for c in cands if c}


def score_number_one(item, resp):
    accepts = {norm_title(a) for a in item["accept"]} - {""}
    cands = title_candidates(resp)
    ok = bool(accepts & cands)
    if not ok:   # phrase containment for longer titles (>= 3 words)
        nr = " " + norm_title(resp) + " "
        ok = any(len(a.split()) >= 3 and f" {a} " in nr for a in accepts)
    return ok, {"artist": item["source"]["record"]["artist"]}


# ---------------------------------------------------------------- leader

PARTICLES = {"de", "da", "do", "dos", "das", "del", "della", "di", "du", "des", "la", "le", "van", "von",
             "der", "den", "ten", "ter", "of", "the", "y", "e", "al", "el", "ibn", "bin", "bint", "ben",
             "ould", "abu", "ul", "ud", "ad", "as", "ar", "sir", "dr", "mr", "st", "jr", "sr", "king",
             "queen", "emperor", "sultan", "president", "prince", "shah", "pasha", "bey", "general"}
GENERIC_GIVEN = {"muhammad", "ahmad", "abd", "ali", "hasan", "husayn", "ibrahim", "umar", "john", "jose",
                 "juan", "maria", "carlos", "francisco", "manuel", "luis", "antonio", "william", "george",
                 "charles", "louis", "henry", "frederick", "peter", "alexander", "nicholas", "paul",
                 "joseph", "francis", "pedro", "said", "abdullah", "salim", "sultan", "shah"}
# canonical forms for common transliteration / exonym variants of given names
EQUIV = {}
for group in [
    "muhammad mohammed mohammad mohamed muhammed mohamad mehmed mehmet",
    "ahmad ahmed ahmet", "hasan hassan", "husayn hussein hussain husain huseyin", "umar omar",
    "abd abdul abdel abdu", "abdullah abdallah abdulla", "said sa'id saeed sayyid", "yusuf yousef youssef joseph josef jose giuseppe",
    "william wilhelm guillaume guillermo willem guglielmo", "louis ludwig luis luiz lodewijk luigi",
    "charles karl carlos carl carol carlo", "frederick friedrich frederik federico fredrik",
    "henry heinrich henri enrique henrique hendrik", "john johann johannes jean juan joao jan ioan giovanni ivan",
    "peter pedro pierre pyotr pietro petar", "alexander aleksandr alexandre alessandro alejandro",
    "nicholas nikolai nicolas nicola nikola", "francis franz francois francisco francesco",
    "george georg georgios jorge georgy", "ferdinand fernando", "victor vittorio", "emmanuel emanuele manuel",
    "gustav gustaf gustavus", "oscar oskar", "philip philippe felipe filipe filippo", "paul pavel paolo pablo",
    "constantine konstantinos konstantin", "alfonso afonso alphonse", "umberto humbert", "michael mikhail mihai miguel",
    "catherine ekaterina", "mary maria marie", "isabella isabel", "otto otho", "abbas abas", "mahmud mahmut", "mustafa mostafa moustafa mustapha",
    "sulayman slimane suleiman suleyman sulaiman soliman",
    "abdulmejid abdulmecid", "abdulaziz abdul-aziz", "selim selim", "murad murat",
]:
    ws = group.split()
    for w in ws:
        EQUIV[w] = ws[0]
ROMAN_RE = re.compile(r"^(?=[xvi]+$)x{0,3}(ix|iv|v?i{0,3})$")   # regnal numerals I..XXXIX


def to_roman(n):
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
            (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def name_tokens(s):
    s = fold(s)
    s = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", s)
    toks = [t for t in re.split(r"[^a-z0-9']+", s) if t]
    out = []
    for t in toks:
        t = t.strip("'")
        if t.isdigit() and 0 < int(t) < 40:
            t = to_roman(int(t))
        out.append(EQUIV.get(t, t))
    return out


def is_roman(t):
    return bool(t) and bool(ROMAN_RE.match(t))


def match_name(gold, resp):
    g = name_tokens(gold)
    r = name_tokens(resp)
    rs = set(r)
    numerals = [t for i, t in enumerate(g) if i > 0 and is_roman(t) and t not in PARTICLES]
    sig = [t for t in g if t not in PARTICLES and not (t in numerals) and len(t) >= 2]
    if not sig:
        return False, "no-significant-tokens"
    if numerals:
        # regnal name: first name token AND the numeral (after it) must appear, e.g. "Louis XVIII"
        base = sig[0]
        if base in r:
            i = r.index(base)
            if any(n in r[i + 1:] for n in numerals):
                return True, "regnal"
        if len(sig) < 2 or any(is_roman(t) and t not in numerals and t != "i" for t in r):
            return False, "regnal-miss"   # no family name to fall back on, or a different numeral given
        # regnal name that also carries a family name ("Alexandru II Ghica", "Ahmad I Al-Jaber Al-Sabah"):
        # fall through to the surname rules below
    if sig[-1] in rs and (len(sig) > 1 or len(sig[-1]) >= 4):
        # guard against relatives sharing a surname ("Heydar Aliyev" for "Ilham Aliyev"):
        # if the word right before the surname is a different given name, reject
        i = r.index(sig[-1])
        prev = r[i - 1] if i > 0 else None
        gset = set(g)
        if (len(sig) > 1 and sig[0] not in rs and prev and prev.isalpha() and len(prev) >= 2
                and prev not in PARTICLES and prev not in gset and not is_roman(prev)):
            return False, "different-given-name"
        return True, "last-token"
    # transliteration variants of the surname ("Roshdy"/"Rushdi", "Fahmy"/"Fahmi")
    if len(sig[-1]) >= 5 and any(t[0] == sig[-1][0] and len(t) >= 4 and
                                 difflib.SequenceMatcher(None, t, sig[-1]).ratio() >= 0.8 for t in rs):
        return True, "fuzzy-surname"
    hits = [t for t in sig if t in rs]
    if len(hits) >= 2 and any(t not in GENERIC_GIVEN for t in hits):
        return True, "two-tokens"
    if len(sig) >= 3 and sig[0] in rs and sig[0] not in GENERIC_GIVEN and len(sig[0]) >= 4:
        return True, "first-of-long"   # e.g. "Mobutu Sese Seko" -> "Mobutu"
    return False, "miss"


def score_leader(item, resp):
    variants = []
    for a in item["accept"]:
        a2 = re.sub(r"\s+of\s+.+$", "", a)   # "Umberto I of Italy" -> "Umberto I"
        variants.append(a2)
    best = (False, "miss")
    for v in dict.fromkeys(variants):
        ok, why = match_name(v, resp)
        if ok:
            best = (True, why)
            break
    return best[0], {"rule": best[1]}


# ---------------------------------------------------------------- cpi

def score_cpi(item, resp):
    rec = item["source"]["record"]
    txt = (resp or "").replace(" ", "").replace(" ", "")
    nums = []
    for m in re.finditer(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?", txt):
        v = float(m.group(1).replace(",", "") + (m.group(2) or ""))
        nums.append(v)
    skip = {float(rec["y1"]), float(rec["y2"]), 100.0}
    cands = [v for v in nums if v not in skip] or nums
    if not cands:
        return False, {"pred": None, "rel_err": None}
    pred = cands[0]
    rel = abs(pred - item["answer"]) / item["answer"]
    return rel <= rec["tolerance"], {"pred": pred, "rel_err": round(rel, 4)}


SCORERS = {"event_year": score_event, "number_one": score_number_one, "leader": score_leader, "cpi": score_cpi}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spotcheck", type=int, default=0, help="print N random graded leader items")
    args = ap.parse_args()
    with open(os.path.join(HERE, "items.jsonl")) as f:
        items = [json.loads(l) for l in f]
    raw_dir = os.path.join(HERE, "results", "raw")
    models = sorted(fn[:-6] for fn in os.listdir(raw_dir) if fn.endswith(".jsonl"))
    summary = {"benchmark": "SlashYear-Bench", "generated": datetime.date.today().isoformat(),
               "n_items": len(items), "n_by_type": dict(collections.Counter(i["type"] for i in items)),
               "models": {}, "notes": {
                   "prompting": "Closed book, single turn, no tools. Azure OpenAI Responses API with instructions "
                                "'Answer from memory. Be concise; give only the answer.' and max_output_tokens=4000 "
                                "(retried at 16000 if a reasoning model returned no text).",
                   "accuracy": "Errors / empty responses count as incorrect; n is the full item count.",
                   "event_year": "Exact year; within_1 = |pred-gold| <= 1. Prediction = first 3-4 digit integer.",
                   "number_one": "Normalized title match (accents, case, punctuation, parentheticals ignored); "
                                 "artist not required.",
                   "leader": "Name matcher: last significant token, or two significant tokens, or regnal "
                             "name + numeral; accent-folded with a small given-name exonym table.",
                   "cpi": "First number in the response (excluding the two years and 100), within 3% of "
                          "100*CPI[Y2]/CPI[Y1].",
                   "leader_unambiguity": "Leader items are unambiguous within slashyear's checked leader record: "
                                         "exactly one holder of the title is recorded for that state and year, "
                                         "with a tenure spanning the whole year. A year where a second holder was "
                                         "dropped by slashyear's cross-check could still show one recorded holder.",
                   "leader_matcher_check": "Manual read of 30 randomly sampled graded leader items (all 3 models, "
                                           "seed 7): 30/30 grades agreed with a human reading. All leader items graded "
                                           "wrong were also read (11 across the 3 models): 4 are matcher false negatives "
                                           "(Roshdy/Rushdi transliteration x3, 'Mahmud Bey' for Mahmud ibn Muhammad x1), "
                                           "3 are a numbering convention in the gold (gold 'Francis II' [HRE numbering], "
                                           "models said 'Francis I of Austria', same person), 4 are genuine errors. "
                                           "Leader accuracy is therefore understated by up to ~1-1.2 points per model.",
                   "errors": "2 items (ev-0078, ev-0367) were rejected by the Azure content filter (HTTP 400) for all "
                             "three models; they count as wrong. No other API errors after retries.",
               }}
    leader_graded = []
    for m in models:
        raw = {}
        with open(os.path.join(raw_dir, f"{m}.jsonl")) as f:
            for line in f:
                r = json.loads(line)
                if r["id"] not in raw or (r.get("ok") and not raw[r["id"]].get("ok")):
                    raw[r["id"]] = r
                elif r.get("ok"):
                    raw[r["id"]] = r   # latest successful response wins
        out_rows = []
        for it in items:
            r = raw.get(it["id"])
            if r is None or not r.get("ok"):
                row = {"id": it["id"], "type": it["type"], "response": None, "correct": False,
                       "extra": {"error": (r or {}).get("error", "not run")}}
            else:
                resp = r.get("output_text") or ""
                ok, extra = SCORERS[it["type"]](it, resp)
                if not resp.strip():
                    extra["empty"] = True
                    extra["incomplete"] = r.get("incomplete")
                row = {"id": it["id"], "type": it["type"], "response": resp, "correct": bool(ok), "extra": extra}
                if it["type"] == "leader":
                    leader_graded.append((m, it, row))
            out_rows.append(row)
        with open(os.path.join(HERE, "results", f"{m}.jsonl"), "w") as f:
            for row in out_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        per = {}
        for t in TYPES:
            rows = [r for r in out_rows if r["type"] == t]
            per[t] = round(sum(r["correct"] for r in rows) / len(rows), 4) if rows else None
        ev = [r for r in out_rows if r["type"] == "event_year"]
        errs = [r["extra"]["abs_err"] for r in ev if r["extra"].get("abs_err") is not None]
        n_err = sum(1 for r in out_rows if r["response"] is None)
        summary["models"][m] = {
            "n": len(out_rows),
            "n_answered": len(out_rows) - n_err,
            "n_errors": n_err,
            "accuracy": round(sum(r["correct"] for r in out_rows) / len(out_rows), 4),
            "macro_accuracy": round(sum(per.values()) / len(per), 4),
            "per_type": per,
            "event_year_within_1": round(sum(r["extra"].get("within1", False) for r in ev) / len(ev), 4),
            "event_year_median_abs_err": statistics.median(errs) if errs else None,
            "event_year_mean_abs_err": round(statistics.mean(errs), 2) if errs else None,
        }
    with open(os.path.join(HERE, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)

    hdr = f"{'model':<14}{'n':>6}{'overall':>9}{'macro':>8}{'event':>8}{'ev±1':>8}{'no1':>8}{'leader':>8}{'cpi':>8}{'err':>5}"
    print(hdr)
    for m, s in summary["models"].items():
        p = s["per_type"]
        print(f"{m:<14}{s['n']:>6}{s['accuracy']:>9.3f}{s['macro_accuracy']:>8.3f}{p['event_year']:>8.3f}"
              f"{s['event_year_within_1']:>8.3f}{p['number_one']:>8.3f}{p['leader']:>8.3f}{p['cpi']:>8.3f}{s['n_errors']:>5}")

    if args.spotcheck:
        rng = random.Random(7)
        for m, it, row in rng.sample(leader_graded, min(args.spotcheck, len(leader_graded))):
            print(f"{it['id']}\t{m}\tgold={it['answer']!r}\tresp={row['response']!r}\t"
                  f"correct={row['correct']}\t{row['extra']['rule']}")


if __name__ == "__main__":
    main()
