#!/usr/bin/env python3
"""Run the REAL FineWeb / C4 / Gopher filter stack over slashyear pages.

Pipeline mirrors what HuggingFace actually ran to build FineWeb (datatrove):
  raw HTML -> trafilatura extraction -> URLFilter -> LanguageFilter(en, 0.65)
           -> GopherRepetitionFilter -> GopherQualityFilter
           -> C4QualityFilter -> FineWebQualityFilter
Every filter is the upstream datatrove implementation with its default (published)
thresholds. Nothing here is my own heuristic.
"""
import sys, json, glob, os, random, argparse
from pathlib import Path
import trafilatura
from datatrove.data import Document
from datatrove.pipeline.filters import (
    GopherRepetitionFilter, GopherQualityFilter, C4QualityFilter,
    FineWebQualityFilter, LanguageFilter, URLFilter,
)

FILTERS = [
    ("url",        URLFilter()),
    ("language",   LanguageFilter(languages=("en",), language_threshold=0.65)),
    ("gopher_rep", GopherRepetitionFilter()),
    ("gopher_qual",GopherQualityFilter()),
    ("c4",         C4QualityFilter(filter_no_terminal_punct=False)),
    ("c4_strict",  C4QualityFilter(filter_no_terminal_punct=True)),
    ("fineweb",    FineWebQualityFilter()),
]

def extract(html, url):
    # FineWeb's exact trafilatura call (datatrove Trafilatura extractor defaults)
    return trafilatura.extract(html, favor_precision=True, include_comments=False,
                               deduplicate=True, url=url)

def judge(html, url):
    text = extract(html, url)
    if not text:
        return {"url": url, "extracted": False, "verdict": "DROP", "died_at": "extraction",
                "reason": "trafilatura returned nothing", "chars": 0, "words": 0}
    doc = Document(text=text, id=url, metadata={"url": url})
    out = {"url": url, "extracted": True, "chars": len(text), "words": len(text.split()),
           "text_head": text[:400]}
    died, reason = None, None
    for name, f in FILTERS:
        try:
            r = f.filter(doc)
        except Exception as e:
            r = (False, f"error:{e}")
        ok = r[0] if isinstance(r, tuple) else r
        why = r[1] if isinstance(r, tuple) and len(r) > 1 else ""
        out[name] = "PASS" if ok else f"DROP:{why}"
        if not ok and died is None and name != "c4_strict":
            died, reason = name, why
    out["verdict"] = "DROP" if died else "PASS"
    out["died_at"] = died
    out["reason"] = reason
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--base", default="https://slashyear.com")
    ap.add_argument("--root", default="")
    args = ap.parse_args()
    for p in args.paths:
        html = Path(p).read_text(encoding="utf-8", errors="replace")
        url = args.base + "/" + os.path.relpath(p, args.root).replace("/index.html","").replace(".html","") if args.root else args.base + "/" + Path(p).stem
        print(json.dumps(judge(html, url)))
