#!/usr/bin/env python3
"""integrity.py -- the classes no other test names.

surface.py asks whether a row LOOKS wrong; verify.py asks whether the site can be
re-derived from the wikitext it says it came from. Neither asks whether a published
sentence is the WHOLE sentence, whether a page's own metadata describes itself, or
whether every link we print leads to a page that exists.

Every check here is written against an INDEPENDENT reading of the raw wikitext, not
against the cleaner, so it can disagree with the cleaner.

Classes:
  TRUNC   published sentence is materially shorter than an independent strip of its raw
  DANGLE  sentence stops on a connector or an unterminated clause
  PAIR    unbalanced quotes / square brackets / guillemets
  RESIDUE html entities, mojibake, ref or file markup, editorial notes
  DUP     the same sentence published twice on one page
  DATE    the row's date field disagrees with the date printed in its own text
  ERA     year -> label mapping (astronomical: -43 is 44 BCE)
  COUNT   counts.shown / available disagree with the rows actually on the page
  ANCHOR  cite section anchor is not a heading in the source revision
  DEAD    an internal link (related entity, decade, century, year) has no page
  META    entity page header (entries/years/span/topics) disagrees with its own rows

"""
from __future__ import annotations
import argparse, collections, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONTHS = ("January February March April May June July August September October "
          "November December").split()


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------- independent wikitext strip --
def strip_raw(raw: str) -> str:
    """A deliberately naive, independent renderer of one wikitext bullet to plain text.

    Independent of extract.clean_line on purpose: verify.py re-renders each row with the
    same cleaner that produced it, so it agrees with itself by construction. This one
    disagrees, which is the only way a cleaner bug shows up."""
    s = raw
    for _ in range(8):                                   # [[File:...]] with nested links
        s2 = re.sub(r"\[\[(?:File|Image):(?:[^\[\]]|\[\[[^\]]*\]\])*\]\]", "", s, flags=re.I)
        if s2 == s:
            break
        s = s2
    s = re.sub(r"</?(?:onlyinclude|includeonly|noinclude)>", "", s)
    # an editor's maintenance note about the article, not part of the statement
    s = re.sub(r"<(sup|small|em|i)\b[^>]*>[^<]*needed[^<]*</\1>", "", s, flags=re.I)
    for _ in range(6):                                   # nested templates / refs
        s2 = re.sub(r"<ref[^>]*/>", "", s)
        s2 = re.sub(r"<ref[^>]*>.*?</ref>", "", s2, flags=re.S)
        s2 = re.sub(r"\{\{[^{}]*\}\}", "", s2)
        s2 = re.sub(r"<!--.*?-->", "", s2, flags=re.S)
        if s2 == s:
            break
        s = s2
    s = re.sub(r"<ref[^>]*>.*$", "", s, flags=re.S)      # a ref that never closes
    s = re.sub(r"\{\{.*$", "", s, flags=re.S)            # a template that never closes
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]", r"\1", s)   # piped links
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)       # labelled external
    s = re.sub(r"\[https?://\S+\]", "", s)
    s = re.sub(r"</?(?:small|big|sup|sub|i|b|span|div|br\s*/?)[^>]*>", "", s)
    s = s.replace("'''", "").replace("''", "")
    s = s.replace("&nbsp;", " ").replace("&ndash;", "–").replace("&amp;", "&")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def unbalanced(t: str) -> bool:
    return bool(t.count('"') % 2 or t.count("[") != t.count("]")
                or t.count("\u201c") != t.count("\u201d"))


DANGLERS = {"and", "or", "the", "of", "in", "to", "a", "an", "with", "for", "from",
            "by", "at", "on", "as", "that", "which", "who", "his", "her", "its",
            "their", "into", "after", "before", "during", "under", "over", "but"}
RESIDUE = [
    (re.compile(r"&(?:nbsp|amp|ndash|mdash|quot|lt|gt|#\d+);"), "html entity"),
    (re.compile(r"â€|Ã©|�"), "mojibake"),
    (re.compile(r"</?ref|</?small|</?sup|</?span|<!--|-->"), "html/ref markup"),
    (re.compile(r"\b(?:File|Image):\S+\.(?:jpg|png|svg|gif|jpeg)", re.I), "file markup"),
    (re.compile(r"\bthumb\|"), "thumb markup"),
    (re.compile(r"citation needed|clarification needed|\[when\?\]|\[who\?\]|\[sic\]",
                re.I), "editorial note"),
    (re.compile(r"\{\{|\}\}"), "template braces"),
]
DATE_RX = re.compile(r"^(?:c\.\s*)?([A-Z][a-z]+)\s+(\d{1,2})\b")
DATE_RX2 = re.compile(r"^(\d{1,2})\s+([A-Z][a-z]+)\b")


def printed_date(text: str):
    m = DATE_RX.match(text)
    if m and m.group(1) in MONTHS:
        return (m.group(1), int(m.group(2)))
    m = DATE_RX2.match(text)
    if m and m.group(2) in MONTHS:
        return (m.group(2), int(m.group(1)))
    return None


def era_label(year: int) -> str:
    return f"{year} CE" if year > 0 else f"{1 - year} BCE"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--json", dest="report", default=os.path.join(ROOT, "integrity.json"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    hits = collections.Counter()
    examples = collections.defaultdict(list)
    stats = collections.Counter()

    def flag(cls, msg):
        hits[cls] += 1
        if len(examples[cls]) < 12:
            examples[cls].append(msg)

    year_paths = sorted(glob.glob(os.path.join(a.site, "[0-9-]*.json")))
    if a.limit:
        year_paths = year_paths[:a.limit]
    year_set = set()

    for path in year_paths:
        doc = load(path)
        y = doc["year"]
        year_set.add(y)
        where = os.path.basename(path)[:-5]

        # -- ERA: the printed label must be the astronomical year rendered correctly
        if doc.get("label") != era_label(y):
            flag("ERA", f"{where}: label {doc.get('label')!r} for year {y}")

        # -- claims for this page, keyed by their published sentence
        cpath = os.path.join(a.claims, f"{y}.json")
        by_text = {}
        if os.path.exists(cpath):
            for c in load(cpath)["claims"]:
                by_text.setdefault(c["text"], c)
                if c.get("body"):
                    by_text.setdefault(c["body"], c)

        seen = {}
        shown = 0
        for section in doc.get("sections", []):
            for item in section["items"]:
                text = item["text"]
                shown += 1
                stats["rows"] += 1

                # -- DUP
                key = re.sub(r"\W+", " ", text.lower()).strip()
                if key in seen:
                    flag("DUP", f"{where}: {text[:90]!r} in both "
                                f"{seen[key]!r} and {section['title']!r}")
                seen[key] = section["title"]

                # -- RESIDUE
                for rx, label in RESIDUE:
                    if rx.search(text):
                        flag("RESIDUE", f"{where}: {label} -- {text[:100]!r}")
                        break

                c = by_text.get(text) or by_text.get(re.sub(r"^.*?–\s*", "", text, count=1))
                full = strip_raw(c["raw"]) if c and c.get("raw") else None

                # -- PAIR. Wikipedia's own sentences carry stray quotes ("Louis IV the
                # Bavarian\"" is written that way in the 1313 article), and a row is meant
                # to be verbatim -- so this is only a defect when the SOURCE was balanced.
                if unbalanced(text):
                    if full is not None and not unbalanced(full):
                        flag("PAIR", f"{where}: we unbalanced a quote/bracket -- {text[:100]!r}")
                    else:
                        stats["pair_in_source"] += 1

                # -- DANGLE
                tail = text.rstrip()
                last = words(tail)[-1] if words(tail) else ""
                if not re.search(r"[.!?\"'”)]$", tail):
                    if last in DANGLERS or tail.endswith((",", "–", "-", ";", "&", "/")):
                        flag("DANGLE", f"{where}: stops on {last or tail[-1]!r} -- {text[:110]!r}")
                    else:
                        stats["no_terminal_punct"] += 1

                # -- DATE: the row's own date field vs the date printed in its text
                pd = printed_date(text)
                if pd and item.get("date"):
                    fd = printed_date(item["date"] + " 1") or printed_date(item["date"])
                    fm = re.match(r"^(?:c\.\s*)?([A-Z][a-z]+)(?:\s+(\d{1,2}))?", item["date"])
                    if fm and fm.group(1) in MONTHS:
                        fmonth, fday = fm.group(1), int(fm.group(2) or 0)
                        if fday and (fmonth, fday) != pd:
                            flag("DATE", f"{where}: filed {item['date']!r} but text prints "
                                         f"{pd[0]} {pd[1]} -- {text[:90]!r}")

                # -- TRUNC: independent strip of the claim's raw wikitext
                if full is not None:
                    pw, fw = words(text), words(full)
                    if len(fw) - len(pw) >= 4 and " ".join(pw) and \
                            " ".join(fw).startswith(" ".join(pw)[:max(20, len(" ".join(pw)) // 2)]):
                        flag("TRUNC", f"{where}: published {len(pw)}w vs raw {len(fw)}w -- "
                                      f"{text[-70:]!r} || raw tail {full[-90:]!r}")

        cnt = doc.get("counts") or {}
        if cnt.get("shown") is not None and cnt["shown"] != shown:
            flag("COUNT", f"{where}: counts.shown {cnt['shown']} vs {shown} rows on the page")
        if cnt.get("available") is not None and cnt["available"] < shown:
            flag("COUNT", f"{where}: available {cnt['available']} < shown {shown}")
        if shown < 3:
            flag("THIN", f"{where}: {shown} rows published")

        # -- LEAD: the muted line under the year heading is the source article's own
        # summary -- its montage caption or its lead paragraph. verify.py only checks the
        # lead when it was assembled from published rows, so on the 182 pages that quote
        # the article's own prose the most prominent text on the page is tested by
        # nothing else. Wikipedia keeps the caption inside a {{multiple image}} template,
        # so this reads the wikitext with links flattened and templates left alone.
        if doc.get("lead_from") in ("article image footer", "article lead"):
            rp = os.path.join(a.raw, f"{y}.json")
            if os.path.exists(rp):
                wt = load(rp).get("wikitext", "")
                wt = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<!--.*?-->", "", wt, flags=re.S)
                wt = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]", r"\1", wt)
                wt = wt.replace(chr(39) * 3, "").replace(chr(39) * 2, "")
                # Two haystacks, and the clause only has to be in one of them: the montage
                # caption lives INSIDE a template, while an article's lead sentence is
                # interrupted by {{efn}} footnotes the cleaner removed.
                keep = re.sub(r"\s+", " ", wt).lower()
                stripped = wt
                for _ in range(6):
                    nxt = re.sub(r"\{\{[^{}]*\}\}", "", stripped)
                    if nxt == stripped:
                        break
                    stripped = nxt
                stripped = re.sub(r"\s+", " ", stripped).lower()
                flat = keep + " || " + stripped
                for clause in re.split(r"[;.]", doc.get("lead", "")):
                    clause = re.sub(r"\s+", " ", clause).strip().lower()
                    if len(clause) < 30:
                        continue
                    if clause[:60] not in flat:
                        flag("LEAD", f"{where}: lead text is not in the cited revision -- "
                                     f"{clause[:90]!r}")

        # -- ANCHOR: the cite anchor must be a heading in the source revision
        rpath = os.path.join(a.raw, f"{y}.json")
        if os.path.exists(rpath):
            wt = load(rpath).get("wikitext", "")
            heads = {re.sub(r"\s+", " ", h.strip()).replace(" ", "_")
                     for h in re.findall(r"^=+\s*(.+?)\s*=+\s*$", wt, flags=re.M)}
            heads = {re.sub(r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]", r"\1", h) for h in heads}
            for section in doc.get("sections", []):
                for item in section["items"]:
                    url = (item.get("cite") or {}).get("url", "")
                    if "#" not in url:
                        continue
                    anchor = url.split("#", 1)[1]
                    if anchor and anchor not in heads:
                        flag("ANCHOR", f"{where}: #{anchor} is not a heading in the revision")

    stats["year_pages"] = len(year_paths)

    # ---------------------------------------------------------------- entity pages --
    ent_paths = sorted(glob.glob(os.path.join(a.site, "entities", "*.json")))
    ent_slugs = {os.path.basename(p)[:-5] for p in ent_paths}
    for path in ent_paths:
        doc = load(path)
        if "items" not in doc:
            continue
        slug = doc["slug"]
        items = doc["items"]
        ys = [i["year"] for i in items]
        if doc.get("entries") != len(items):
            flag("META", f"timeline/{slug}: entries {doc.get('entries')} vs {len(items)} rows")
        if doc.get("years") != len(set(ys)):
            flag("META", f"timeline/{slug}: years {doc.get('years')} vs {len(set(ys))} distinct")
        if ys and doc.get("span") != [min(ys), max(ys)]:
            flag("META", f"timeline/{slug}: span {doc.get('span')} vs {[min(ys), max(ys)]}")
        tsum = sum(t["count"] for t in doc.get("topics", []))
        if doc.get("topics") and tsum != len(items):
            flag("META", f"timeline/{slug}: topic counts sum to {tsum}, {len(items)} rows")
        if doc.get("span_label") and ys:
            want = [era_label(min(ys)), era_label(max(ys))]
            if doc["span_label"] != want:
                flag("ERA", f"timeline/{slug}: span_label {doc['span_label']} vs {want}")
        for rel in doc.get("related", []):
            if rel["slug"] not in ent_slugs:
                flag("DEAD", f"timeline/{slug} -> /timeline/{rel['slug']} does not exist")
        for i in items:
            if i["year"] not in year_set:
                flag("DEAD", f"timeline/{slug} row cites year {i['year']} with no page")
        stats["timeline_rows"] += len(items)
    stats["timelines"] = len(ent_paths)

    # ---------------------------------------------------------------- cross links --
    idx = os.path.join(a.site, "cross", "years.json")
    if os.path.exists(idx):
        for year, where in load(idx).items():
            for kind in ("decade", "century"):
                w = where.get(kind)
                if not w:
                    continue
                p = os.path.join(a.site, "cross", kind, f"{w['slug']}.json")
                if not os.path.exists(p):
                    flag("DEAD", f"year {year} -> /{kind}/{w['slug']} does not exist")
    for path in sorted(glob.glob(os.path.join(a.site, "dates", "*.json"))):
        doc = load(path)
        for g in doc.get("groups", []):
            for i in g["items"]:
                if i["year"] not in year_set:
                    flag("DEAD", f"date/{doc['slug']} row cites year {i['year']} with no page")
            stats["date_rows"] += len(g["items"])

    # ---------------------------------------------------------------- report --
    NOTES = {"THIN", "DANGLE"}
    total = sum(n for c, n in hits.items() if c not in NOTES)
    for cls in sorted(hits):
        print(f"  {'.' if cls in NOTES else 'x'} {cls} {hits[cls]:,}")
        for e in examples[cls][:6]:
            print(f"      . {e}")
    print(f"integrity: {stats['rows']:,} year rows, {stats['timeline_rows']:,} timeline rows, "
          f"{stats['date_rows']:,} calendar rows across {stats['year_pages']:,} year pages "
          f"and {stats['timelines']:,} timelines")
    if a.report:
        json.dump({"stats": dict(stats), "counts": dict(hits),
                   "examples": {k: v for k, v in examples.items()}},
                  open(a.report, "w", encoding="utf-8"), indent=1)
    if total:
        print(f"integrity: {total:,} FAILURES")
        return 1
    print(f"integrity: clean ({stats['pair_in_source']} rows carry an unbalanced quote "
          f"that is unbalanced in Wikipedia too, {hits['THIN']} pages have under 3 rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
