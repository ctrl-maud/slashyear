#!/usr/bin/env python3
"""surface.py -- test every KIND of page, not just the year pages.

coverage.py and famous.py ask "is this famous event on its year page?" and between them
they name 384 cases. Both look at exactly two of the site's seven page kinds: year pages
and calendar-day pages. The site also publishes 12 topic hubs, 303 topic-century pages,
284 decade pages, 39 century pages and 4,670 entity timelines -- more than half of
everything we ship -- and until this file existed no test named a single row on any of
them. That is how the 20th-century page came to carry three highlights while the 9th
carried eight, and how every decade page from the 1900s to the 2020s listed its years
with nothing underneath them: the data was empty, the build was green, and no test looked.

Five checks, each mechanical, each exiting non-zero on failure:

  KIND      a case list per page kind -- topic hubs, decades, centuries, countries, entity
            timelines -- of the sort of row a reader would expect to find there.
  SHAPE     no published sentence, on any page kind, may open on punctuation, on a bare
            "30 - ", or be shorter than a clause. This is the class verify.py structurally
            cannot see: it re-derives the published text with the same cleaner, so a
            sentence whose subject was deleted by a dropped template matches perfectly.
  TRACE     every row on a cross-cut page (topic, calendar day, entity timeline) must
            exist on its own year page, citing the same revision id. A cross-cut is a
            re-filing, so a row that appears in one and not the other is invented.
  FILL      structural minimums: every century page carries highlights, every decade
            page shows entries under its years, no calendar day is empty.
  BUDGET    (--out) Cloudflare Pages refuses a deployment over 20,000 files, and entity
            pages cost two files each, so the file count is a shipping constraint that
            has to fail here rather than at the deploy.

Usage:
  surface.py [--site data/site] [--out site/out] [--json report.json] [--quiet]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------- cases --

# topic hub slug -> phrases that must appear somewhere under that topic. A miss means
# either the row is missing entirely or it was filed under a topic where nobody would
# look for it, and on a topic page the filing IS the content.
TOPIC_CASES: dict[str, list[str]] = {
    "science-and-discovery": ["Darwin", "penicillin|Fleming", "Moon"],
    "technology-and-infrastructure": ["telephone", "railway|railroad", "telegraph"],
    "conflict-and-security": ["Waterloo", "Hastings", "Stalingrad|Normandy"],
    "disasters-and-accidents": ["Titanic", "earthquake", "Chernobyl|Bhopal"],
    "health-and-medicine": ["plague|Black Death", "vaccine|vaccination", "cholera"],
    "religion-and-belief": ["Luther|Reformation", "pope|Pope", "Mecca|Muhammad"],
    "exploration-and-expansion": ["Columbus", "Magellan|circumnavigat", "Antarctic|Arctic"],
    "economy-and-finance": ["Wall Street|stock market", "bank|Bank"],
    "crime-and-justice": ["trial", "assassinat"],
    "culture-and-society": ["Shakespeare", "Olympic"],
    "climate-and-environment": ["flood", "drought|famine"],
    "geopolitics-and-diplomacy": ["Treaty of Versailles|Versailles", "United Nations"],
}

# decade slug -> a phrase from the decade's defining event, which must appear either in a
# year's lead items on the decade page or in the decade's own year pages.
DECADE_CASES: dict[str, str] = {
    "1960s": "Moon|Apollo 11",
    "1940s": "Hiroshima|atomic bomb",
    "1930s": "Hitler|Great Depression",
    "1910s": "World War I|Great War|Armistice",
    "1860s": "Gettysburg|Lincoln|American Civil War",
    "1780s": "Bastille|French Revolution|Constitution",
    "1490s": "Columbus",
    "2000s": "September 11|terrorist attacks",
    "2010s": "Arab Spring|Brexit|Crimea",
    "1970s": "Watergate|Vietnam",
}

# century slug -> phrase that must appear on that century page (its highlights) or in the
# century's topic pages.
CENTURY_CASES: dict[str, str] = {
    "20th-century": "war|World War",
    "19th-century": "railway|railroad|steam|slavery",
    "15th-century": "Constantinople|Columbus|printing",
    "1st-century": "Rome|Roman|Jerusalem",
    "5th-century-bc": "Athens|Greek|Persian",
}

# entity timeline slug -> a phrase that must appear on that timeline. These are the
# subjects an ordinary person would type into a search box; an entity page that exists
# but does not carry the event the subject is famous for is worse than no page.
ENTITY_CASES: dict[str, str] = {
    "rome": "Rome",
    "constantinople": "Constantinople",
    "napoleon": "Napoleon",
    "roman-empire": "Roman",
    "ottoman-empire": "Ottoman",
    "byzantine-empire": "Byzantine",
    "japan": "Japan",
    "china": "China",
    "india": "India",
    "egypt": "Egypt",
    "russia": "Russia",
    "brazil": "Brazil",
    "mexico": "Mexico",
    "nigeria|west-africa|africa": "Africa|Nigeria",
    "world-war-ii": "WWII|World War II",
    "french-revolution": "France|French",
    "apollo-program": "Apollo",
    "united-nations": "United Nations",
    "black-death": "plague|Black Death",
    "vincent-van-gogh": "Gogh",
    "berlin-wall": "Berlin",
    "anne-frank": "Frank",
    "johannes-gutenberg": "Gutenberg",
}

# country slug -> a phrase that must appear somewhere on that country's page. Deliberately
# broad: each century on a country page shows a sample spread across it, so pinning the
# test to one specific event would fail on the sampling rather than on a defect. What this
# catches is the page being empty, being built from the wrong articles, or a country whose
# harvest silently stopped -- and the list is chosen to span the regions the corpus was
# measured thin in, not the ones it was already fat in.
PLACE_CASES: dict[str, str] = {
    "japan": "Japan|Tokyo|Japanese",
    "india": "India|Indian|Delhi",
    "china": "China|Chinese|Beijing|Peking",
    "brazil": "Brazil|Brazilian",
    "nigeria": "Nigeria|Nigerian|Lagos",
    "south-africa": "South Africa|African",
    "mexico": "Mexico|Mexican",
    "egypt": "Egypt|Egyptian|Cairo",
    "south-korea": "Korea|Korean|Seoul",
    "indonesia": "Indonesia|Indonesian|Jakarta",
    "canada": "Canada|Canadian",
    "france": "France|French|Paris",
}

# ---------------------------------------------------------------------------- shape --

_MONTH = ("January|February|March|April|May|June|July|August|September|October|"
          "November|December")
BARE_NUMBER = re.compile(r"^\d{1,2}\s*[–—-]\s+[A-Z]")   # "30 - Second Battle..."
OPENS_PUNCT = re.compile(r"^[,;:.–—-]")
# "May 11 - , the ship that will later take young Charles Darwin": a printed date, then
# the sentence opening on a comma because its subject was deleted. A colon after the date
# is how many articles separate the date from the sentence, so it is not a symptom.
LOST_SUBJECT = re.compile(rf"^(?:(?:{_MONTH}) \d{{1,2}}|\d{{1,2}} (?:{_MONTH}))\s*[–—-]?\s*[,;]")
MARKUP = re.compile(r"\[\[|\{\{|\]\]|\}\}|__[A-Z]{3,}__")
RAW_LINK = re.compile(r"\[https?://")
ENDS_COLON = re.compile(r":\s*$")
# {{convert|9000|km|mi}} used to render "9000 km mi" -- the number silently attached to
# two units at once, and the reader cannot tell which one it belongs to. 154 rows carried
# it. The second unit is never "in", which is a preposition far more often than an inch.
UNITS = r"km2|sqmi|mph|km/h|km|mi|ft|yd|cm|mm|kg|lb|oz|ha|acres?|kn|AU|m"
UNITS_SPELLED = r"foot|feet|metres|meters|miles|kilometres|kilometers|inches|yards|tonnes|tons|pounds|"
TWO_UNITS = re.compile(rf"\b\d[\d,.]*\s*(?:{UNITS_SPELLED}{UNITS})\s+(?:{UNITS})\b(?![a-z])")
# An editor's note about the ARTICLE, printed as though it were part of the statement.
EDITOR_NOTE = re.compile(r"\b(?:clarification|citation|verification|dubious)\s+needed", re.I)
# An editor commented a line OUT of the article and we published it, sometimes still
# carrying the "-->" that closed the comment. The cleaner strips a comment that opens and
# closes on one line, which is precisely why a multi-line one was invisible for 250 rows.
COMMENTED = re.compile(r"<!--|-->")
# "September 18– – The island of Møn is divided into estates": a nested bullet whose parent
# printed the date with a trailing dash, joined to the child with another one.
DOUBLE_SEP = re.compile(r"^[^–—-]{0,30}[–—-]\s*[–—-]")


def shape_problem(text: str) -> str | None:
    if MARKUP.search(text):
        return "wiki markup left in the sentence"
    if OPENS_PUNCT.match(text):
        return "opens on punctuation"
    if LOST_SUBJECT.match(text):
        return "opens on punctuation after its date -- subject deleted"
    if BARE_NUMBER.match(text):
        return "opens on a bare day number -- a span prefix was cut in half"
    if RAW_LINK.search(text):
        return "a raw external link survived into the sentence"
    if ENDS_COLON.search(text):
        return "ends on a colon -- this is a heading for nested lines, not a statement"
    if text.count("(") != text.count(")"):
        return "unbalanced bracket -- the sentence was truncated where a template was cut"
    if TWO_UNITS.search(text):
        return "a measurement printed with two units -- a convert template lost its number"
    if EDITOR_NOTE.search(text):
        return "an editor's maintenance note published as part of the sentence"
    if COMMENTED.search(text):
        return "an HTML comment marker -- this line was commented OUT of the article"
    if DOUBLE_SEP.match(text):
        return "two separators after the date -- a parent bullet's dash was joined twice"
    if len(text) < 12:
        return "shorter than a clause"
    return None


# ----------------------------------------------------------------------------- data --

def load(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def year_rows(site: str) -> dict[int, dict[str, int | None]]:
    """year -> {published sentence: revision id}."""
    out: dict[int, dict[str, int | None]] = {}
    for path in glob.glob(os.path.join(site, "[0-9-]*.json")):
        doc = load(path)
        rows: dict[str, int | None] = {}
        for section in doc.get("sections", []):
            for item in section["items"]:
                rows[item["text"]] = (item.get("cite") or {}).get("revid")
        out[doc["year"]] = rows
    return out


def hit(haystack: str, phrase: str) -> bool:
    low = haystack.lower()
    return any(p.strip().lower() in low for p in phrase.split("|"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--out", default=os.path.join(ROOT, "site", "out"),
                    help="the exported site, for the file-count budget")
    ap.add_argument("--json", dest="report")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    fails: list[str] = []
    stats: dict[str, int] = {}

    # ---- KIND: topic hubs -------------------------------------------------------
    checked = 0
    for slug, phrases in TOPIC_CASES.items():
        blob = ""
        for path in sorted(glob.glob(os.path.join(a.site, "cross", "topic", slug, "*.json"))):
            blob += " ".join(i["text"] for i in load(path)["items"])
        for phrase in phrases:
            checked += 1
            if not hit(blob, phrase):
                fails.append(f"TOPIC /topic/{slug} has nothing matching {phrase!r}")
    stats["topic_cases"] = checked

    # ---- KIND: decades ----------------------------------------------------------
    for slug, phrase in DECADE_CASES.items():
        path = os.path.join(a.site, "cross", "decade", f"{slug}.json")
        if not os.path.exists(path):
            fails.append(f"DECADE /decade/{slug} does not exist")
            continue
        page = load(path)
        blob = " ".join(t for y in page["years"] for t in y["lead_items"])
        if not hit(blob, phrase):
            fails.append(f"DECADE /decade/{slug} shows no line matching {phrase!r} "
                         f"({sum(len(y['lead_items']) for y in page['years'])} lines shown)")
    stats["decade_cases"] = len(DECADE_CASES)

    # ---- KIND: centuries --------------------------------------------------------
    for slug, phrase in CENTURY_CASES.items():
        path = os.path.join(a.site, "cross", "century", f"{slug}.json")
        if not os.path.exists(path):
            fails.append(f"CENTURY /century/{slug} does not exist")
            continue
        page = load(path)
        blob = " ".join(h["text"] for h in page.get("highlights", []))
        for tpath in glob.glob(os.path.join(a.site, "cross", "topic", "*", f"{slug}.json")):
            blob += " " + " ".join(i["text"] for i in load(tpath)["items"])
        if not hit(blob, phrase):
            fails.append(f"CENTURY /century/{slug} carries nothing matching {phrase!r}")
    stats["century_cases"] = len(CENTURY_CASES)

    # ---- KIND: entity timelines -------------------------------------------------
    for slugs, phrase in ENTITY_CASES.items():
        found = None
        for slug in slugs.split("|"):
            path = os.path.join(a.site, "entities", f"{slug}.json")
            if os.path.exists(path):
                found = load(path)
                break
        if found is None:
            fails.append(f"TIMELINE /timeline/{slugs.split('|')[0]} does not exist")
            continue
        blob = " ".join(i["text"] for i in found["items"])
        if not hit(blob, phrase):
            fails.append(f"TIMELINE /timeline/{found['slug']} carries no row matching {phrase!r}")
    stats["entity_cases"] = len(ENTITY_CASES)

    # ---- KIND: country pages ----------------------------------------------------
    # This page kind did not exist before the country-year harvest, and the lesson this
    # file was written for is that a page kind no test names is exactly where the next
    # defect sits.
    misfiled = 0
    for slug, phrase in PLACE_CASES.items():
        path = os.path.join(a.site, "cross", "place", f"{slug}.json")
        if not os.path.exists(path):
            fails.append(f"PLACE /in/{slug} does not exist")
            continue
        page = load(path)
        blob = " ".join(i["text"] for c in page["centuries"] for i in c["items"])
        if not hit(blob, phrase):
            fails.append(f"PLACE /in/{slug} carries no row matching {phrase!r}")
    for path in sorted(glob.glob(os.path.join(a.site, "cross", "place", "*.json"))):
        page = load(path)
        for c in page["centuries"]:
            for i in c["items"]:
                # A row filed under the wrong country is invisible to every other test:
                # it is correctly quoted, correctly cited, and on a page about a nation it
                # has nothing to do with.
                if i.get("country") != page["label"]:
                    misfiled += 1
    if misfiled:
        fails.append(f"PLACE {misfiled} rows sit on a country page that is not their own country")
    stats["place_cases"] = len(PLACE_CASES)
    stats["place_pages"] = len(glob.glob(os.path.join(a.site, "cross", "place", "*.json")))

    # ---- SHAPE + TRACE ----------------------------------------------------------
    years = year_rows(a.site)
    stats["year_rows"] = sum(len(v) for v in years.values())
    shape = collections.Counter()
    shape_examples: list[str] = []
    orphans = collections.Counter()
    orphan_examples: list[str] = []
    cross_rows = 0

    def check_rows(kind: str, where: str, items: list[dict]) -> None:
        nonlocal cross_rows
        for item in items:
            text = item["text"]
            problem = shape_problem(text)
            if problem:
                shape[f"{kind}: {problem}"] += 1
                if len(shape_examples) < 25:
                    shape_examples.append(f"{kind} {where}: {problem} -- {text[:100]!r}")
            if kind == "year":
                continue
            cross_rows += 1
            rows = years.get(item["year"])
            if rows is None:
                orphans["no year page"] += 1
                continue
            revid = (item.get("cite") or {}).get("revid")
            exact = rows.get(text)
            if text in rows:
                if exact != revid:
                    orphans["revision id differs from the year page"] += 1
                continue
            # a calendar page prints the sentence with its date prefix removed
            suffix = [r for r, rv in rows.items() if text and r.endswith(text)]
            if not suffix:
                orphans["row is on no year page"] += 1
                if len(orphan_examples) < 15:
                    orphan_examples.append(f"{kind} {where} {item['year']}: {text[:90]!r}")
            elif revid not in {rows[r] for r in suffix}:
                orphans["revision id differs from the year page"] += 1

    for path in glob.glob(os.path.join(a.site, "[0-9-]*.json")):
        doc = load(path)
        for section in doc.get("sections", []):
            check_rows("year", str(doc["year"]), section["items"])
    for path in sorted(glob.glob(os.path.join(a.site, "dates", "*.json"))):
        doc = load(path)
        if "groups" not in doc:
            continue
        for group in doc["groups"]:
            check_rows("date", doc["slug"], group["items"])
    for path in sorted(glob.glob(os.path.join(a.site, "cross", "topic", "*", "*.json"))):
        doc = load(path)
        check_rows("topic", doc["topic"]["slug"], doc["items"])
    for path in sorted(glob.glob(os.path.join(a.site, "entities", "*.json"))):
        doc = load(path)
        if "items" in doc:
            check_rows("timeline", doc["slug"], doc["items"])
    for path in sorted(glob.glob(os.path.join(a.site, "cross", "place", "*.json"))):
        doc = load(path)
        for c in doc["centuries"]:
            check_rows("place", doc["slug"], c["items"])

    stats["cross_rows"] = cross_rows
    for label, n in shape.items():
        fails.append(f"SHAPE {n} rows -- {label}")
    for label, n in orphans.items():
        fails.append(f"TRACE {n} cross-cut rows -- {label}")

    # ---- ORDER: an entity timeline reads down the page, so it must be chronological --
    months = ("January February March April May June July August September October "
              "November December").split()

    def month_day(date: str | None) -> tuple[int, int]:
        if not date:
            return (0, 0)
        m = re.match(r"^(?:c\.\s*)?([A-Z][a-z]+)(?:\s+(\d{1,2}))?", date)
        if not m or m.group(1) not in months:
            return (0, 0)
        return (months.index(m.group(1)) + 1, int(m.group(2) or 0))

    out_of_order = []
    for path in sorted(glob.glob(os.path.join(a.site, "entities", "*.json"))):
        doc = load(path)
        if "items" not in doc:
            continue
        keys = [(i["year"], month_day(i.get("date"))) for i in doc["items"]]
        if keys != sorted(keys):
            out_of_order.append(doc["slug"])
    if out_of_order:
        fails.append(f"ORDER {len(out_of_order)} entity timelines are not in chronological "
                     f"order, e.g. {', '.join(out_of_order[:5])}")
    stats["timelines"] = len(glob.glob(os.path.join(a.site, "entities", "*.json"))) - 1

    # ---- ERA: a year's decade and century must be on the same side of the era boundary --
    index_path = os.path.join(a.site, "cross", "years.json")
    if os.path.exists(index_path):
        era_bad = []
        for year, where in load(index_path).items():
            # A thin decade or century is not published at all, so the field is null and
            # there is nothing to disagree with.
            if not where.get("decade") or not where.get("century"):
                continue
            d_bc = where["decade"]["slug"].endswith("-bc")
            c_bc = where["century"]["slug"].endswith("-bc")
            if d_bc != c_bc:
                era_bad.append(year)
        if era_bad:
            fails.append(f"ERA {len(era_bad)} years sit in a BC decade and an AD century "
                         f"or the reverse: {', '.join(era_bad[:6])}")

    # ---- SPAN: a calendar row printing a range must contain the day of the page it is on --
    span_bad = 0
    # (?!\d|st|nd|rd|th) so that "February 10 — 17th Congress of the All-Union Communist
    # Party" is not read as the range 10-17: an ordinal is a count, not a day.
    span_rx = re.compile(r"^([A-Z][a-z]+) (\d{1,2})\s*[–—-]\s*(?:([A-Z][a-z]+) )?(\d{1,2})(?!\d|,|st|nd|rd|th)")
    for path in sorted(glob.glob(os.path.join(a.site, "dates", "*.json"))):
        doc = load(path)
        if "groups" not in doc:
            continue
        for group in doc["groups"]:
            for item in group["items"]:
                m = span_rx.match(item["text"])
                if not m:
                    continue
                m1, d1, m2, d2 = m.group(1), int(m.group(2)), m.group(3) or m.group(1), int(m.group(4))
                if m1 not in months or m2 not in months:
                    continue
                lo = (months.index(m1), d1)
                hi = (months.index(m2), d2)
                if hi <= lo:
                    # Not a range: "August 20 - 15 year old Greta Thunberg starts to stay
                    # out of school", or a range written the other way round ("April 27-6
                    # May"). dates.py applies the same ordering guard before filing.
                    continue
                here = (months.index(doc["month"]), doc["day"])
                if not (lo <= here <= hi):
                    span_bad += 1
    if span_bad:
        fails.append(f"SPAN {span_bad} calendar rows print a date range that does not "
                     f"contain the day of the page they are filed on")

    # ---- FILL -------------------------------------------------------------------
    thin_centuries = []
    for path in glob.glob(os.path.join(a.site, "cross", "century", "*.json")):
        page = load(path)
        if len(page.get("highlights", [])) < 3:
            thin_centuries.append(f"{page['slug']} ({len(page.get('highlights', []))})")
    if thin_centuries:
        fails.append("FILL century pages with fewer than 3 highlights: " + ", ".join(sorted(thin_centuries)))

    thin_decades = []
    for path in glob.glob(os.path.join(a.site, "cross", "decade", "*.json")):
        page = load(path)
        shown = sum(1 for y in page["years"] if y["lead_items"])
        if page["years"] and shown / len(page["years"]) < 0.5:
            thin_decades.append(f"{page['slug']} ({shown}/{len(page['years'])})")
    if thin_decades:
        fails.append("FILL decade pages showing lines for under half their years: "
                     + ", ".join(sorted(thin_decades)))

    empty_days = [os.path.basename(p)[:-5]
                  for p in glob.glob(os.path.join(a.site, "dates", "*.json"))
                  if load(p).get("count") == 0]
    if empty_days:
        fails.append("FILL calendar days with no entries: " + ", ".join(sorted(empty_days)))

    # ---- IDENTITY ---------------------------------------------------------------
    # An entity page asserts that its subject is ONE thing. A link target is only a
    # string, so without this check the same subject ships as several half-timelines:
    # editors write Persia and Iran, Macedon and Macedonia (ancient kingdom), Sassanid
    # Empire and Sasanian Empire, USSR and Soviet Union. Measured 2026-09-08: 136
    # subjects were split across 284 pages, the Byzantine Empire's own timeline was
    # missing the rows filed under "Byzantine", and 383 pages carried no Wikidata id at
    # all because a redirect title has no item of its own. Wikipedia's redirect graph is
    # the authority; entities.py resolves against it and this proves it stayed resolved.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from entities import wanted  # noqa: E402  -- the same rule that decides what to publish
    redir_path = os.path.join(os.path.dirname(os.path.normpath(a.site)), "redirects.json")
    ent_index = os.path.join(a.site, "entities", "index.json")
    if os.path.exists(redir_path) and os.path.exists(ent_index):
        canon = load(redir_path)
        groups: dict[str, list[str]] = collections.defaultdict(list)
        noncanon = []
        entities = load(ent_index)["entities"]
        for e in entities:
            target = canon.get(e["label"], e["label"])
            if target != e["label"] and wanted(target):
                # A page may legitimately be titled with a redirect when the article it
                # redirects to is one entities.py never publishes ("Byzantine emperor" ->
                # "List of Byzantine emperors"). What is never legitimate is two pages
                # for one target, which the grouping below still catches.
                noncanon.append(f"{e['slug']} ({e['label']} -> {target})")
            groups[target].append(e["slug"])
        split = sorted((k, v) for k, v in groups.items() if len(v) > 1)
        stats["entity_pages"] = len(entities)
        stats["entity_no_qid"] = sum(1 for e in entities if not e["qid"])
        if noncanon:
            fails.append(f"IDENTITY {len(noncanon)} entity pages are titled with a "
                         f"redirect rather than the article Wikipedia serves: "
                         + ", ".join(noncanon[:8]))
        if split:
            fails.append(f"IDENTITY {len(split)} subjects are split across "
                         f"{sum(len(v) for _k, v in split)} timelines: "
                         + "; ".join(f"{k} <- {v}" for k, v in split[:6]))

    # ---- BUDGET -----------------------------------------------------------------
    if a.out and os.path.isdir(a.out):
        files = sum(len(fs) for _r, _d, fs in os.walk(a.out))
        stats["files"] = files
        if files > 19_400:
            fails.append(f"BUDGET {files:,} files in {a.out} -- Cloudflare Pages refuses "
                         f"a deployment over 20,000")

    # ---- report -----------------------------------------------------------------
    if not a.quiet:
        for line in shape_examples:
            print("  ." + line)
        for line in orphan_examples:
            print("  ." + line)
        print(f"surface: {stats.get('year_rows', 0):,} year rows and "
              f"{stats.get('cross_rows', 0):,} cross-cut rows checked; "
              f"{stats.get('topic_cases', 0) + stats.get('decade_cases', 0) + stats.get('century_cases', 0) + stats.get('entity_cases', 0) + stats.get('place_cases', 0)} "
              f"page-kind cases", flush=True)
    if a.report:
        json.dump({"stats": stats, "failures": fails},
                  open(a.report, "w", encoding="utf-8"), indent=1)
    if fails:
        print(f"surface: {len(fails)} FAILURES")
        for f in fails:
            print("  x " + f)
        return 1
    print("surface: all page kinds clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
