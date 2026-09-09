#!/usr/bin/env python3
"""trainfilter.py — run the REAL LLM pretraining-corpus filters over your own pages.

Answers one question with a measurement instead of an opinion: would this page
survive into FineWeb / RefinedWeb / DCLM, and if not, WHICH filter kills it?

It uses the upstream `datatrove` implementations HuggingFace actually ran to build
FineWeb, in FineWeb's own pipeline order, with the published default thresholds.
Nothing here is a heuristic of mine.

    URL/HTML -> trafilatura(favour_precision) -> URLFilter -> LanguageFilter(en,0.65)
             -> GopherRepetitionFilter -> GopherQualityFilter
             -> C4QualityFilter -> FineWebQualityFilter

Usage:
  trainfilter.py url https://slashyear.com/1523 [more urls...]
  trainfilter.py file out/1523.html --url https://slashyear.com/1523
  trainfilter.py dir  out/ --glob 'timeline/*.html' --sample 50
  trainfilter.py text notes.txt          # already-extracted plain text
  trainfilter.py --explain               # what each failure code means

Options:
  --json          machine-readable output, one object per page
  --sample N      random subset (dir mode)
  --seed N        sample seed (default 0)
  --show-text     print the extracted text of the first failure

Exit code is 0 if every page passed, 1 otherwise.

Requires: pip install "datatrove[processing]" trafilatura spacy nltk
          python -m spacy download en_core_web_sm
"""
import argparse, glob as globmod, json, os, random, sys
from pathlib import Path
import importlib.metadata  # datatrove touches importlib.metadata without importing it

CODES = {
 "extraction":  "trafilatura found no main content — the page is chrome, script or markup only.",
 "url":         "domain/path hit datatrove's blocklist.",
 "language":    "fastText did not call it English with p>=0.65 (dense numerals and names read as 'not English').",
 "dup_line_frac":            "GOPHER: >30% of the lines in THIS page are duplicates of each other.",
 "top_2_gram":  "GOPHER: one repeated 2-word phrase covers >20% of the page's characters.",
 "top_3_gram":  "GOPHER: one repeated 3-word phrase covers >18% of the page's characters.",
 "top_4_gram":  "GOPHER: one repeated 4-word phrase covers >16% of the page's characters.",
 "duplicated_5_n_grams":  "GOPHER: repeated 5-word runs cover >15% of the page. A boilerplate paragraph repeated inside ONE page does this.",
 "duplicated_6_n_grams":  "GOPHER: repeated 6-word runs cover >14% of the page.",
 "duplicated_7_n_grams":  "GOPHER: repeated 7-word runs cover >13% of the page.",
 "gopher_short_doc":       "GOPHER: fewer than 50 words.",
 "gopher_long_doc":        "GOPHER: more than 100,000 words.",
 "gopher_below_avg_threshold": "GOPHER: mean word length under 3 characters.",
 "gopher_above_avg_threshold": "GOPHER: mean word length over 10 characters.",
 "gopher_too_many_bullets":"GOPHER: >90% of lines start with '-' or a bullet. A page rendered as a list dies here.",
 "gopher_too_many_end_ellipsis": "GOPHER: >30% of lines end in an ellipsis (truncated teasers).",
 "gopher_below_alpha_threshold": "GOPHER: <80% of tokens contain a letter. Dates, counts, IDs and standalone punctuation all count against you.",
 "gopher_enough_stop_words":"GOPHER: fewer than 2 of the/be/to/of/and/that/have/with — the text is not sentences.",
 "gopher_too_many_hashes": "GOPHER: '#' to word ratio over 0.1.",
 "gopher_too_many_ellipsis":"GOPHER: '...' to word ratio over 0.1.",
 "line_punct_ratio": "FINEWEB: <12% of lines end in . ! ? or a quote. Bullet fragments without full stops die here.",
 "short_line_ratio": "FINEWEB: >67% of lines are 30 characters or shorter.",
 "char_dup_ratio":   "FINEWEB: duplicate lines cover >1% of the page's characters.",
 "list_ratio":       "FINEWEB: newlines-per-word over 0.3 — the page reads as a list, not prose.",
 "lorem_ipsum": "C4: contains 'lorem ipsum'.", "javascript": "C4: a line mentions javascript.",
 "curly_bracket": "C4: contains '{' (reads as source code).",
 "policy": "C4: a line matches a cookie/privacy/terms boilerplate string.",
 "too_few_sentences": "C4: fewer than 3 sentences survive line filtering.",
}

def build_filters():
    from datatrove.pipeline.filters import (GopherRepetitionFilter, GopherQualityFilter,
        C4QualityFilter, FineWebQualityFilter, LanguageFilter, URLFilter)
    return [("url", URLFilter()),
            ("language", LanguageFilter(languages=("en",), language_threshold=0.65)),
            ("gopher_rep", GopherRepetitionFilter()),
            ("gopher_qual", GopherQualityFilter()),
            ("c4", C4QualityFilter(filter_no_terminal_punct=False)),
            ("fineweb", FineWebQualityFilter())]

def extract(html, url):
    import trafilatura
    return trafilatura.extract(html, favor_precision=True, include_comments=False,
                               deduplicate=True, url=url)

def judge(text, url, filters):
    from datatrove.data import Document
    if not text or not text.strip():
        return {"url": url, "verdict": "DROP", "filter": "extraction",
                "code": "extraction", "words": 0, "text": ""}
    doc = Document(text=text, id=url, metadata={"url": url})
    for name, f in filters:
        r = f.filter(doc)
        ok = r[0] if isinstance(r, tuple) else r
        why = (r[1] if isinstance(r, tuple) and len(r) > 1 else "") if not ok else ""
        if not ok:
            return {"url": url, "verdict": "DROP", "filter": name, "code": why,
                    "words": len(text.split()), "text": text}
    return {"url": url, "verdict": "PASS", "filter": None, "code": None,
            "words": len(text.split()), "text": text}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", choices=["url", "file", "dir", "text"])
    ap.add_argument("targets", nargs="*")
    ap.add_argument("--url", default=None, help="url to report for a local file")
    ap.add_argument("--glob", default="**/*.html")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show-text", action="store_true")
    ap.add_argument("--explain", action="store_true")
    a = ap.parse_args()

    if a.explain:
        for k, v in CODES.items(): print(f"{k:32s} {v}")
        return 0
    if not a.mode:
        ap.print_help(); return 0

    filters = build_filters()
    jobs = []   # (text_or_html, url, is_html)
    if a.mode == "url":
        import urllib.request
        for u in a.targets:
            req = urllib.request.Request(u, headers={"User-Agent": "CCBot/2.0"})
            jobs.append((urllib.request.urlopen(req, timeout=30).read().decode("utf-8","replace"), u, True))
    elif a.mode == "file":
        for p in a.targets:
            jobs.append((Path(p).read_text(encoding="utf-8", errors="replace"),
                         a.url or f"https://example.com/{Path(p).stem}", True))
    elif a.mode == "text":
        for p in a.targets:
            jobs.append((Path(p).read_text(encoding="utf-8", errors="replace"),
                         a.url or f"https://example.com/{Path(p).stem}", False))
    else:
        root = a.targets[0]
        files = sorted(globmod.glob(os.path.join(root, a.glob), recursive=True))
        if a.sample and len(files) > a.sample:
            random.seed(a.seed); files = sorted(random.sample(files, a.sample))
        for p in files:
            rel = os.path.relpath(p, root)
            jobs.append((Path(p).read_text(encoding="utf-8", errors="replace"),
                         f"https://example.com/{rel[:-5] if rel.endswith('.html') else rel}", True))

    rows, shown = [], False
    for payload, url, is_html in jobs:
        text = extract(payload, url) if is_html else payload
        r = judge(text, url, filters)
        rows.append(r)
        if a.json:
            print(json.dumps({k: v for k, v in r.items() if k != "text"}))
        else:
            tag = "PASS" if r["verdict"] == "PASS" else f"DROP  {r['filter']}:{r['code']}"
            print(f"{tag:52s} {r['words']:6d}w  {url}")
        if a.show_text and r["verdict"] == "DROP" and not shown:
            shown = True
            print("\n--- extracted text ---\n" + (r["text"] or "")[:2000] + "\n----------------------\n")

    n = len(rows); p = sum(1 for r in rows if r["verdict"] == "PASS")
    if not a.json:
        print(f"\n{p}/{n} PASS  ({100*p/max(n,1):.1f}%)")
        from collections import Counter
        c = Counter(f"{r['filter']}:{r['code']}" for r in rows if r["verdict"] == "DROP")
        for k, v in c.most_common():
            print(f"  {v:5d}  {k}\n         {CODES.get(k.split(':')[-1], '')}")
    return 0 if p == n else 1

if __name__ == "__main__":
    sys.exit(main())
