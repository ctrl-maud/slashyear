#!/usr/bin/env python3
"""hfpack -- turn the /dump NDJSON into a Hugging Face dataset repo, ready to push.

Why a separate shape from /dump: the dumps are built for a crawler that wants the
whole thing in one file. Hugging Face is built for someone who wants to
`load_dataset("...", "events")` and get a table, and its viewer only previews
Parquet. Same data, four flat tables, no nesting -- nesting is what makes a
dataset unusable from pandas, and unusable from pandas is unusable.

The subject timelines are the one thing that has to be reshaped. In the dump each
subject carries its entries inside it; here that becomes a `subject_events` join
table, so "every event mentioning Rome" is a filter and not a parse.

  hfpack.py --out hf/                 # build the folder
  hfpack.py --out hf/ --push <repo>   # build, then push with HF_TOKEN
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, "..", "site", "out", "dump")


def rows(name: str):
    with gzip.open(os.path.join(DUMP, name), "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def write(out: str, config: str, table: pa.Table) -> str:
    d = os.path.join(out, "data", config)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "train-00000-of-00001.parquet")
    pq.write_table(table, path, compression="zstd")
    return f"{config}: {table.num_rows:,} rows, {os.path.getsize(path)/1e6:.1f} MB"


def build(out: str) -> list[str]:
    log = []

    # events -- the main table. Already flat; only the nulls need a stable type.
    ev = list(rows("events.ndjson.gz"))
    log.append(write(out, "events", pa.table({
        "year":           pa.array([e["year"] for e in ev], pa.int32()),
        "year_label":     pa.array([e["year_label"] for e in ev], pa.string()),
        "date":           pa.array([e.get("date") for e in ev], pa.string()),
        "topic":          pa.array([e["section"] for e in ev], pa.string()),
        "text":           pa.array([e["text"] for e in ev], pa.string()),
        "source_title":   pa.array([e["source_title"] for e in ev], pa.string()),
        "source_revid":   pa.array([e["source_revid"] for e in ev], pa.int64()),
        "source_section": pa.array([e.get("source_section") for e in ev], pa.string()),
        "source_url":     pa.array([e["source_url"] for e in ev], pa.string()),
        "page":           pa.array([e["page"] for e in ev], pa.string()),
    })))

    # years -- one row per year, with the lead paragraph.
    yr = list(rows("years.ndjson.gz"))
    log.append(write(out, "years", pa.table({
        "year":        pa.array([y["year"] for y in yr], pa.int32()),
        "year_label":  pa.array([y["label"] for y in yr], pa.string()),
        "lead":        pa.array([y.get("lead") for y in yr], pa.string()),
        "entries":     pa.array([y["entries"] for y in yr], pa.int32()),
        "topics":      pa.array([y.get("sections") or [] for y in yr], pa.list_(pa.string())),
        "source_title": pa.array([(y.get("source") or {}).get("title") for y in yr], pa.string()),
        "source_revid": pa.array([(y.get("source") or {}).get("revid") for y in yr], pa.int64()),
        "source_url":  pa.array([(y.get("source") or {}).get("url") for y in yr], pa.string()),
        "page":        pa.array([y.get("page") for y in yr], pa.string()),
    })))

    # subjects + the join table that replaces the nesting.
    su = list(rows("entities.ndjson.gz"))
    log.append(write(out, "subjects", pa.table({
        "slug":        pa.array([s["slug"] for s in su], pa.string()),
        "label":       pa.array([s["label"] for s in su], pa.string()),
        "qid":         pa.array([s.get("qid") for s in su], pa.string()),
        "description": pa.array([s.get("description") for s in su], pa.string()),
        "entries":     pa.array([s["entries"] for s in su], pa.int32()),
        "years":       pa.array([s["years"] for s in su], pa.int32()),
        "first_year":  pa.array([(s.get("span") or [None, None])[0] for s in su], pa.int32()),
        "last_year":   pa.array([(s.get("span") or [None, None])[1] for s in su], pa.int32()),
        "wikipedia":   pa.array([s.get("wikipedia") for s in su], pa.string()),
        "wikidata":    pa.array([s.get("wikidata") for s in su], pa.string()),
        "page":        pa.array([s.get("page") for s in su], pa.string()),
    })))

    flat = [(s["slug"], s["label"], s.get("qid"), it) for s in su for it in s.get("items", [])]
    log.append(write(out, "subject_events", pa.table({
        "slug":         pa.array([f[0] for f in flat], pa.string()),
        "label":        pa.array([f[1] for f in flat], pa.string()),
        "qid":          pa.array([f[2] for f in flat], pa.string()),
        "year":         pa.array([f[3]["year"] for f in flat], pa.int32()),
        "year_label":   pa.array([f[3]["year_label"] for f in flat], pa.string()),
        "date":         pa.array([f[3].get("date") for f in flat], pa.string()),
        "topic":        pa.array([f[3].get("section") for f in flat], pa.string()),
        "text":         pa.array([f[3]["text"] for f in flat], pa.string()),
        "source_revid": pa.array([(f[3].get("cite") or {}).get("revid") for f in flat], pa.int64()),
        "source_url":   pa.array([(f[3].get("cite") or {}).get("url") for f in flat], pa.string()),
    })))
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a Hugging Face dataset repo from the dumps.")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "hf"))
    ap.add_argument("--push", metavar="REPO_ID",
                    help="also push to hf.co/datasets/REPO_ID (needs HF_TOKEN)")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    for line in build(out):
        print(" ", line)
    card = os.path.join(HERE, "..", "hf-card.md")
    if os.path.exists(card):
        with open(card, encoding="utf-8") as fh, open(os.path.join(out, "README.md"), "w", encoding="utf-8") as w:
            w.write(fh.read())
        print("  README.md (dataset card) copied in")
    print(f"  -> {out}")
    if a.push:
        if not os.environ.get("HF_TOKEN"):
            print("  HF_TOKEN not set; nothing pushed", file=sys.stderr)
            return 1
        subprocess.run([sys.executable, "-c",
                        "import sys;from huggingface_hub import HfApi;"
                        "api=HfApi();api.create_repo(sys.argv[1],repo_type='dataset',exist_ok=True);"
                        "api.upload_folder(folder_path=sys.argv[2],repo_id=sys.argv[1],repo_type='dataset')",
                        a.push, out], check=True)
        print(f"  pushed -> https://huggingface.co/datasets/{a.push}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
