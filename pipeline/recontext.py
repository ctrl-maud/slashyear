#!/usr/bin/env python3
"""recontext.py -- apply the 2026-09-10 grouping-header fix to data/claims in place.

extract.py no longer publishes a date header as a claim and now carries the header's
context onto its children (issue #1: "September 9 (killed at the Battle of Flodden)"
shipped as a standalone bullet while the eleven people under it lost the cause of
death). A full re-extract would erase every theme classify.py wrote back, plus the
deaths.py and places.py rows merged into the same files -- so, like reclean.py, this
touches only the claims the fix actually changes:

  - deletes a claim whose raw line is a recognized date header (the fragments);
  - where the new extractor renders the same raw line to a different text (the context
    suffix), updates id/text/body/date/context_suffix and keeps every other field.

Everything else in every file is left byte-identical. Prints each change; --apply writes.

  python3 pipeline/recontext.py            # dry run
  python3 pipeline/recontext.py --apply
"""
from __future__ import annotations
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import extract, clean_line, date_header  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    files = sorted((f for f in os.listdir(a.raw)
                    if f.endswith(".json") and not f.startswith("_")
                    and os.path.isfile(os.path.join(a.raw, f))),
                   key=lambda f: int(f[:-5]))
    deleted = updated = 0
    for fn in files:
        cpath = os.path.join(a.claims, fn)
        if not os.path.exists(cpath):
            continue
        rec = json.load(open(os.path.join(a.raw, fn), encoding="utf-8"))
        page = json.load(open(cpath, encoding="utf-8"))
        # The new extractor's view of the year article, keyed by the stored source line.
        # A raw line can repeat across source articles but not within one, and only
        # claims from THIS article (same revid) are matched against it.
        new_by_raw = {}
        for n in extract(rec):
            new_by_raw.setdefault((n["raw"], n.get("date_prefix")), n)
        revid = rec["source"]["revid"]
        keep, changed = [], False
        for c in page["claims"]:
            if (c.get("source") or page["source"])["revid"] != revid:
                keep.append(c)          # deaths.py / places.py / companion-article rows
                continue
            n = new_by_raw.get((c["raw"], c.get("date_prefix")))
            if n is None:
                bare, _, _ = clean_line(c["raw"])
                if date_header(bare) is not None:
                    print(f"DELETE  {fn:>10}  {c['text'][:100]!r}")
                    deleted += 1
                    changed = True
                    continue
                keep.append(c)          # dropped for some other reason; not ours to touch
                continue
            suffix = n.get("context_suffix")
            if suffix and n["text"] == f"{c['text']} — {suffix}":
                # The one change this migration ships: the header's context, appended.
                # Any other drift between the stored text and what today's extractor
                # renders (e.g. the OWN_DAY doubled-date fix) is a separate migration
                # with its own verify semantics — logged, not applied.
                print(f"UPDATE  {fn:>10}  {c['text'][:70]!r}")
                print(f"    ->  {n['text'][:120]!r}")
                out = dict(c)
                out.update({k: n[k] for k in ("id", "text", "body", "context_suffix")})
                keep.append(out)
                updated += 1
                changed = True
            else:
                if n["text"] != c["text"]:
                    print(f"skip drift  {fn:>10}  {c['text'][:60]!r} -> {n['text'][:60]!r}")
                keep.append(c)
        if changed and a.apply:
            page["claims"] = keep
            json.dump(page, open(cpath, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n{deleted} deleted, {updated} updated"
          + ("" if a.apply else "  (dry run — nothing written)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
