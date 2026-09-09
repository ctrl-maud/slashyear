#!/usr/bin/env python3
"""extract.py — turn harvested wikitext into individual, provenanced claims.

The rule of the rebuild: a bullet on the site is the cleaned source sentence, not a
paraphrase. Cleaning is mechanical and reversible-by-inspection (strip markup, resolve
links, drop citation noise), so verify.py can re-derive every published bullet straight
from the stored revision and refuse anything that does not match.

Anything the cleaner cannot render confidently — a line left with dangling punctuation,
an unresolved template, no verb-bearing body — is dropped rather than guessed at.

Two structures in the source are easy to miss and expensive to miss. Where several
things happened on one date, Wikipedia writes a bare date bullet with the events nested
underneath it; skipping nested bullets silently dropped the Apollo 11 Moon landing from
1969. And most year articles carry an editor-written summary of the year's headline
events in the lead or the image footer, which is a far better page lead than anything
that can be assembled mechanically.

Usage:
  extract.py [--raw data/raw] [--out data/claims] [--report]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MONTHS = ("January February March April May June July August September October "
          "November December").split()
MONTH_RE = "|".join(MONTHS)

# Sections whose list items are NOT chronicle content: apparatus (how the article was
# written) and invention (what did not happen). Everything else on a year, decade or
# century article is the record -- see wanted_tops() for why this is a deny-list.
SKIP_TOP = {"references", "external links", "see also", "notes", "sources",
            "further reading", "bibliography", "gallery", "in fiction",
            "notes and references", "citations",
            # apparatus and invention, added 2026-09-08 when the section filter was
            # inverted from an allow-list to this deny-list (see wanted_tops).
            "in works of fiction", "fiction", "in legend", "in popular culture",
            "predictions and fictional events", "further reading and year books",
            "yearbooks", "works cited", "primary sources and year books",
            "new english words", "new english words and terms",
            # Award tables. Their lines are "Physics - James Watson Cronin, Val Logsdon
            # Fitch": true, sourced, and meaningless once the heading that says which
            # prize this is has been stripped, which is what happens when a claim is
            # re-filed under our own section taxonomy. Every bullet on this site has to
            # stand on its own, so these do not qualify.
            "nobel prizes", "fields medal", "templeton prize",
            "right livelihood award", "other academic awards"}

# ---------------------------------------------------------------- {{convert}} --------
# The input side of a convert call is "<number> [joiner <number>...] <unit>", optionally a
# compound like {{convert|5|ft|6|in|m}}. Everything after that first unit is the converted
# output, which we drop: printing it would need the arithmetic, and the source sentence is
# meant to survive verbatim.
CVT_JOIN = {"to", "-", "\u2013", "\u2014", "and", "or", "by", "x", "\u00d7", "\u00b1", "+/-", "+",
            "through"}
CVT_NUM = re.compile(r"^[-+]?[\d,]*\.?\d+(?:/\d+)?$")
CVT_UNIT = {
    "mi/h": "mph", "kph": "km/h", "acre": "acres", "carat": "carats", "oilbbl": "barrels",
    "C": "\u00b0C", "F": "\u00b0F", "sqmi": "sq mi", "sqft": "sq ft", "km2": "km\u00b2",
    "m2": "m\u00b2", "e6USgal": "million US gallons", "e9USgal": "billion US gallons",
    "USgal": "US gallons", "e6m3": "million m\u00b3", "e6m2": "million m\u00b2",
    "Moilbbl/d": "million barrels per day",
}


def render_convert(params: list[str]) -> str:
    parts = [x.strip() for x in params if "=" not in x and x.strip()]
    value: list[str] = []
    i = 0
    while i < len(parts) and (CVT_NUM.match(parts[i]) or parts[i].lower() in CVT_JOIN):
        value.append(parts[i])
        i += 1
    out = [_cvt_number(v) if CVT_NUM.match(v) else v for v in value]
    if i < len(parts):
        unit = parts[i]
        i += 1
        out.append(_cvt_unit(unit, value))
        # a compound measurement: {{convert|5|ft|6|in|m}} -> "5 ft 6 in"
        if i + 1 < len(parts) and CVT_NUM.match(parts[i]) and not CVT_NUM.match(parts[i + 1]):
            out.append(_cvt_number(parts[i]))
            out.append(_cvt_unit(parts[i + 1], [parts[i]]))
    return " ".join(out).strip()


def _cvt_number(v: str) -> str:
    if re.fullmatch(r"\d{4,}", v):
        return f"{int(v):,}"
    return v


def _cvt_unit(unit: str, value: list[str]) -> str:
    shown = CVT_UNIT.get(unit, unit)
    if shown.endswith("s") and value == ["1"]:
        shown = shown[:-1]
    return shown


# Templates that carry text we want to keep, mapped to how to render them.
KEEP_TEMPLATES = {
    "circa": lambda p: "c. " + (p[0] if p else ""),
    "c.": lambda p: "c. " + (p[0] if p else ""),
    "ca": lambda p: "c. " + (p[0] if p else ""),
    "nowrap": lambda p: p[0] if p else "",
    # Old Style / New Style dates: "{{OldStyleDateNY|March 31|March 20}}" is how the
    # 1727 article prints the day Isaac Newton died. Dropping the template left the line
    # opening on a dash, which the fragment guard then threw away, so Newton was missing
    # from the deaths of his own year. The first parameter is the modern date.
    "oldstyledate": lambda p: p[0] if p else "",
    "oldstyledateny": lambda p: p[0] if p else "",
    "oldstyledatedy": lambda p: p[0] if p else "",
    "nobr": lambda p: p[0] if p else "",
    "lang": lambda p: p[1] if len(p) > 1 else "",
    "ill": lambda p: p[0] if p else "",
    "interlanguage link": lambda p: p[0] if p else "",
    # {{convert|9000|km|mi}} prints "9,000 km (5,590 mi)" on Wikipedia. Joining the first
    # three parameters printed "9000 km mi" -- the number silently attached to two units at
    # once, and a range like {{convert|5|to|10|km|mi}} lost its unit altogether. We keep the
    # measurement as written and drop the conversion, which is the half we cannot compute.
    "convert": lambda p: render_convert(p),
    "cvt": lambda p: render_convert(p),
    "frac": lambda p: ("/".join(p[:2]) if len(p) == 2 else
                       (p[0] + " " + p[1] + "/" + p[2] if len(p) >= 3 else
                        ("1/" + p[0] if p else ""))),
    # chemical formulae: {{chem|CO|2}} -> CO2, {{CO2}} -> CO2
    "chem": lambda p: "".join(p),
    "co2": lambda p: "CO2",
    "overbar": lambda p: p[0] if p else "",
    "langx": lambda p: p[1] if len(p) > 1 else "",
    "nbsp": lambda p: " ",
    "en dash": lambda p: "–",
    "reign": lambda p: "r. " + "–".join(p[:2]),
    "abbr": lambda p: p[0] if p else "",
    "sic": lambda p: "",
    "spaced ndash": lambda p: "–",
    "snd": lambda p: "–",
    "ndash": lambda p: "–",
    "mdash": lambda p: "—",
    "'": lambda p: "'",
    "okina": lambda p: "ʻ",
    "transliteration": lambda p: p[1] if len(p) > 1 else "",
    "transl": lambda p: p[1] if len(p) > 1 else "",
    "script": lambda p: p[1] if len(p) > 1 else "",
    "yes": lambda p: "",
    "flag": lambda p: p[0] if p else "",
    "flagcountry": lambda p: p[0] if p else "",
    "flagicon": lambda p: "",
    # {{M|w}} is the moment-magnitude label in every modern earthquake line ("the 7.1
    # {{M|w}} El Asnam earthquake"); it renders as M with a subscript.
    "m": lambda p: "M" + (p[0] if p else ""),
    "-": lambda p: "",
}

# Ship-name templates. Wikipedia writes a named ship as {{HMS|Beagle}}, {{USS|New
# Jersey|BB-62}}, {{RMS|Olympic}} or the generic {{ship|Japanese submarine |I-177}}, and
# renders it as the ship's name. Dropping them deleted the SUBJECT of the sentence and
# published lines like "December 16 - Construction begins on the , at the Harland and
# Wolff Shipyard" (that is the RMS Olympic) and "Charles Darwin returns to England aboard
# ,". verify.py cannot see this class at all: it re-derives the published sentence with
# this same function, so a deletion here is reproduced identically and matches.
# Trailing parameters are the article disambiguator and a display switch, never prose.
SHIP_PREFIXES = {
    "hms", "uss", "rms", "ss", "sms", "hmas", "hmcs", "hmnzs", "hmsas", "usns", "uscgc",
    "usat", "usrc", "rfa", "mv", "ins", "orp", "hnlms", "knm", "ara", "kms", "ijn",
    "hmy", "hmt", "hswms", "nrp", "jds", "ms", "smu", "gs", "ps", "sy", "mt", "rv",
}


def render_ship(name: str, args: list[str]) -> str:
    """{{USS|New Jersey|BB-62}} -> "USS New Jersey"; {{ship|German ship|Petrella||2}} ->
    "German ship Petrella"; {{ship||Tango Maru}} -> "Tango Maru"."""
    parts = [a.strip() for a in args if a.strip()]
    if name == "ship":
        return " ".join(parts[:2])
    return " ".join([name.upper()] + parts[:1])


# Apparatus a reader never sees: citation, sourcing and maintenance templates. These are
# the only templates allowed to vanish without making the line unpublishable. Anything
# else that disappears took words out of a sentence, which is the bug above.
DROP_TEMPLATES = {
    "isbn", "issn", "oclc", "doi", "pmid", "jstor", "bibcode", "asin", "lccn",
    "citation", "citation needed", "full citation needed", "cn", "fact",
    "sfn", "sfnp", "sfnm", "harvnb", "harv", "harvtxt", "rp", "r", "page needed",
    "pn", "dead link", "webarchive", "cbignore", "subscription required",
    "registration required", "better source needed", "unreliable source?",
    "verify source", "dubious", "clarify", "when", "who", "why", "vague",
    "according to whom", "original research?", "self-published source",
    "primary source inline", "third-party inline", "medical citation needed",
    "date missing", "specify", "which", "where", "attribution needed",
    "not in citation given", "failed verification", "disputed inline", "efn", "refn",
    "notetag", "note", "nb", "ref", "reflist", "portal", "main", "see also",
    "further", "anchor", "sfnref", "cref", "toc limit", "in lang", "language icon",
    "pb", "clear", "-\"", "'\"",
    # found by the strict rule itself, 2026-09-08: every remaining template that was
    # vanishing out of a published sentence. These are the ones that are genuinely
    # apparatus; the rest became renderers above.
    "importance inline", "relevance inline", "self-published inline", "citati",
    "unreliable source", "fcn", "facts", "new archival link needed", "undue inline",
    "dubious inline", "nonspecific", "promotional source", "primary source",
    "better source", "cite quote", "request quotation", "page range too broad",
}


def droppable(name: str) -> bool:
    """True for the citation/maintenance families, which are apparatus rather than prose:
    {{cite ...}}, {{cite web}}, the *DNB/EB1911 short-citation shortcuts, and the list
    above. Everything else that renders to nothing marks the line unclean."""
    if name in DROP_TEMPLATES:
        return True
    if name.startswith(("cite ", "cite", "citeref", "cit ")):
        return True
    if name.endswith((" citation", "-citation")):
        return True
    # short-form reference shortcuts used inside <ref>: {{ODNB|...}}, {{EB1911|...}},
    # {{DBI}}, {{HDS}}, {{EI2}}, {{The Early Medieval Balkans|...}} -- a bare source name.
    if name in {"odnb", "dnb", "eb1911", "eb9", "dbi", "hds", "ei2", "ei3", "ei1",
                "adb", "anb", "dcb", "nie", "catholic encyclopedia", "cathence",
                "grove", "oxforddnb", "britannica", "dnb lifespan", "dnb cite"}:
        return True
    return False


def split_template(body: str) -> tuple[str, list[str]]:
    parts, depth, cur = [], 0, ""
    i = 0
    while i < len(body):
        ch = body[i]
        if body.startswith("{{", i) or body.startswith("[[", i):
            depth += 1
            cur += body[i:i + 2]
            i += 2
            continue
        if body.startswith("}}", i) or body.startswith("]]", i):
            depth -= 1
            cur += body[i:i + 2]
            i += 2
            continue
        if ch == "|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    parts.append(cur)
    name = parts[0].strip().lower()
    args = [p.strip() for p in parts[1:] if "=" not in p.split("|")[0][:24]]
    return name, args


def resolve_templates(text: str, depth: int = 0) -> tuple[str, bool]:
    """Replace {{...}} with rendered text. Returns (text, clean) — clean is False if an
    unknown template carrying prose had to be dropped."""
    if depth > 6 or "{{" not in text:
        return text, True
    clean = True
    out, i = "", 0
    while i < len(text):
        if text.startswith("{{", i):
            j, d = i + 2, 1
            while j < len(text) and d:
                if text.startswith("{{", j):
                    d += 1
                    j += 2
                elif text.startswith("}}", j):
                    d -= 1
                    j += 2
                else:
                    j += 1
            body = text[i + 2:j - 2]
            name, args = split_template(body)
            inner = [resolve_templates(a, depth + 1)[0] for a in args]
            if name in KEEP_TEMPLATES:
                out += KEEP_TEMPLATES[name](inner)
            elif name == "ship" or name in SHIP_PREFIXES:
                out += render_ship(name, inner)
            elif droppable(name):
                pass
            else:
                # Anything else renders to nothing, so the sentence just lost whatever it
                # held. The old rule only flagged templates carrying three words or more,
                # which is how {{RMS|Olympic}} and {{HMS|Beagle}} -- one word each, and the
                # subject of their sentences -- were deleted in silence.
                clean = False
            i = j
        else:
            out += text[i]
            i += 1
    return out, clean


LINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]")


def strip_media(text: str) -> str:
    """Remove [[File:...]] / [[Image:...]] blocks. They nest other links inside their
    caption, so a flat regex cannot do it — scan for the matching close."""
    out, i = "", 0
    low = text.lower()
    while i < len(text):
        if low.startswith("[[file:", i) or low.startswith("[[image:", i):
            j, d = i + 2, 1
            while j < len(text) and d:
                if text.startswith("[[", j):
                    d += 1
                    j += 2
                elif text.startswith("]]", j):
                    d -= 1
                    j += 2
                else:
                    j += 1
            i = j
            continue
        out += text[i]
        i += 1
    return out
EXTLINK_RE = re.compile(r"\[(?:https?:)//[^\s\]]+\s+([^\]]+)\]")
# The same thing with no label at all -- "[https://news.bbc.co.uk/...]" -- which used to
# survive into the published sentence as a raw bracketed URL.
BARELINK_RE = re.compile(r"\[(?:https?:)//[^\s\]]+\]")
REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
TAG_RE = re.compile(r"<[^>]+>")
ERA_LINK_RE = re.compile(r"^(\d{1,4})\s+(BCE?|AD)$")
# An editor's maintenance note written into the line itself rather than as a template:
# 76 published "First year of Jianchu era of the Chinese Han dynasty. (Clarification
# needed as to the meaning of this)" because the note sits in a <sup> and only the tag
# was being removed. The note is about the article, not about the year.
EDITOR_NOTE_RE = re.compile(
    r"<(sup|small|em|i)\b[^>]*>\s*\(?\s*(?:clarification|citation|verification|"
    r"clarify|dubious|source)[^<]*?needed[^<]*</\1>", re.I | re.S)


def clean_line(wt: str) -> tuple[str, list[str], bool]:
    """wikitext list item -> (plain sentence, link targets, is_clean)."""
    s = wt
    s = COMMENT_RE.sub("", s)
    s = EDITOR_NOTE_RE.sub("", s)
    s = REF_RE.sub("", s)
    s = strip_media(s)
    s, tmpl_clean = resolve_templates(s)
    links: list[str] = []
    era_fixups: list[tuple[str, str]] = []

    def _link(m):
        target, label = m.group(1), m.group(2)
        target = target.split("#")[0].strip()
        if target and not target.lower().startswith(("file:", "image:", "category:")):
            links.append(target)
        shown = (label if label is not None else m.group(1)).strip()
        # [[113 BC|113]] renders as a bare "113" on Wikipedia, where the LINK carries the
        # era. We publish plain sentences with no links in them, so on a BCE page that
        # becomes "Lady Gouyi, mother of Zhao of Han (b. 113)" -- two hundred years wrong
        # to a reader, from a line that is otherwise verbatim. Noted here and applied
        # below only when the finished sentence states no era at all: where the sentence
        # already says "136-132 BC", spelling out both halves reads worse than the source.
        era = ERA_LINK_RE.match(target)
        if era and shown == era.group(1):
            era_fixups.append((era.group(1), era.group(2)))
        return shown

    s = LINK_RE.sub(_link, s)
    s = EXTLINK_RE.sub(r"\1", s)
    s = BARELINK_RE.sub("", s)
    s = re.sub(r"'''''|'''|''", "", s)
    s = re.sub(r"__[A-Z]{3,}__", " ", s)   # __NOTOC__, __TOC__ and friends
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = s.replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^[*#:;\s]+", "", s)
    if era_fixups and not re.search(r"\b(?:BCE?|AD)\b", s):
        num, era = era_fixups[0]
        s = re.sub(rf"\b{num}\b(?!\s*(?:BCE?|AD)\b)", f"{num} {era}", s, count=1)
    # dangling punctuation left behind by a dropped template
    ok = tmpl_clean
    # Residual markup means a link or template the cleaner could not close — six bullets
    # shipped as "King [[Rudolf I of Germany|". Nothing with markup left in it is
    # publishable, and a line that now opens on a comma has lost its subject.
    if re.search(r"\[\[|\]\]|\{\{|\}\}|\|", s):
        ok = False
    if re.match(r"^[,;:.\u2013\u2014-]", s):
        ok = False
    # ...and the same test again with the printed date removed. "May 11 - , the ship that
    # will later take young Charles Darwin" passed the check above for three years because
    # the sentence starts on a month, not on the comma: the subject (HMS Beagle) had been
    # deleted by a dropped template two characters later.
    body_only = DATE_LEAD.sub("", s, count=1).strip()
    if re.match(r"^[,;:.\u2013\u2014-]", body_only) or len(body_only) < 12:
        ok = False
    if re.search(r"(^|\s)[,;:]|\(\s*\)|\[\s*\]|\s,|,\s*$|–\s*$|\bthe\s*$", s):
        if re.search(r"\(\s*\)|\[\s*\]|\s,\s*$|–\s*$", s):
            ok = False
    # An unbalanced "(" means the closing half was inside something the cleaner removed,
    # so the sentence is not whole. It used to be TRUNCATED at the bracket and published
    # anyway, which shipped 162 sentences that stop in the middle of themselves ("...on
    # his way toward Italy, in order to assert his claim to become King of Naples"). A
    # truncated sentence is not the source's sentence, so it is not publishable.
    if s.count("(") != s.count(")"):
        ok = False
    # A line that ends on a colon is a heading for the lines nested under it ("May 22
    # (killed at the First Battle of St Albans):"). Those children are extracted in their
    # own right and inherit the date; the header alone is a fragment.
    if re.search(r":\s*$", s):
        ok = False
    # An unbalanced quote mark left by italics markup the article never closed
    # ("...is incorporated as a city.'").
    if re.search(r"[.!?]'\s*$", s) and s.count("'") % 2 == 1:
        ok = False
    return s, links, ok


DATE_LEAD = re.compile(
    rf"^(?:(?P<m>{MONTH_RE})\s+(?P<d>\d{{1,2}})|(?P<d2>\d{{1,2}})\s+(?P<m2>{MONTH_RE})|"
    rf"(?P<mo>{MONTH_RE}))\b\s*(?:[-–—:]\s*)?"
)


def parse_date(sentence: str, heading_trail: list[str]) -> tuple[str | None, int | None, int | None]:
    m = DATE_LEAD.match(sentence)
    if m:
        mon = m.group("m") or m.group("m2") or m.group("mo")
        day = m.group("d") or m.group("d2")
        return (f"{mon} {day}" if day else mon), MONTHS.index(mon) + 1, int(day) if day else None
    for h in heading_trail:
        if h in MONTHS:
            return h, MONTHS.index(h) + 1, None
    return None, None, None


def strip_date_lead(sentence: str) -> str:
    return DATE_LEAD.sub("", sentence, count=1).strip()


DATE_ONLY = re.compile(rf"^(?:{MONTH_RE})\s+\d{{1,2}}$|^\d{{1,2}}\s+(?:{MONTH_RE})$")


def strip_boilerplate(text: str) -> str:
    """Drop the calendar sentence every year article opens with ("1969 (MCMLXIX) was a
    common year starting on Wednesday of the Gregorian calendar...") — true, and of no
    interest to anyone."""
    keep = []
    for sent in re.split(r"(?<=\.)\s+", text):
        if re.search(r"(common|leap) year starting|of the Gregorian calendar|"
                     r"Anno Domini|Julian calendar|designations?, the \d+|"
                     r"Year of the Consulship|Ab urbe condita|calendar era|"
                     r"At the time, it was known as|denomination .{0,20}for this year|"
                     r"the (?:early|latter) part of|was a year of the", sent, re.I):
            continue
        keep.append(sent)
    return " ".join(keep).strip()


def article_highlights(wikitext: str) -> tuple[str, str] | None:
    """The year's headline events as an editor wrote them: first the image footer that
    captions the year's montage, otherwise the lead prose. Returns (text, where)."""
    m = re.search(r"\{\{\s*Multiple image(.*?)\n\}\}", wikitext, re.S | re.I)
    if m:
        cap = re.search(r"\|\s*(?:footer|caption)\s*=\s*(.+?)(?=\n\s*\||\n\}\}|$)",
                        m.group(1), re.S)
        if cap:
            txt, _links, ok = clean_line(cap.group(1))
            # Montage footers open with a reading order for the picture grid —
            # "From top to bottom:", "From left to right, top to bottom:",
            # "Clockwise from top to bottom left-right:" — which is an instruction
            # about the images, not a statement about the year, and the images are
            # not on our page at all.
            txt = re.sub(r"^(?:from\s+)?(?:top|bottom|left|right|clockwise|counter-?\s?clockwise|anti-?\s?clockwise)\b[^:]{0,60}:\s*",
                         "", txt, flags=re.I)
            txt = re.sub(r"^[;,\s]+", "", txt)
            txt = re.sub(r"\s*[;,]?\s*\*\s*", lambda m: "; " if m.start() else "", txt)
            txt = re.sub(r"\s*;\s*$", ".", txt).strip()
            if ok and len(txt) > 80:
                return txt[0].upper() + txt[1:], "article image footer"

    head = re.split(r"^==[^=]", wikitext, maxsplit=1, flags=re.M)[0]
    head = re.sub(r"\{\{[^{}]*\}\}", "", re.sub(r"\{\{.*?\n\}\}", "", head, flags=re.S))
    paras = [p.strip() for p in head.split("\n\n") if p.strip()]
    for p in paras:
        txt, _links, ok = clean_line(p)
        txt = strip_boilerplate(txt)
        txt = re.sub(r"\s*\*\s*", lambda m: "; " if m.start() else "", txt).strip()
        txt = re.sub(r"[;:]\s*;", ";", txt)
        if ok and len(txt) > 80:
            return txt, "article lead"
    return None


def wanted_tops(wikitext: str) -> set[str]:
    """Every top-level section that is not apparatus.

    This used to be an allow-list of nine heading names, with a fallback to everything
    else when none of them appeared. That inverted rule is what kept the founding of Rome off
    the record: the "750s BC" article carries "Significant people", which IS in
    WANTED_TOP, so the strict branch fired and threw away "Events and trends" -- the
    section holding the actual events -- and 753 BC ended up with no page at all.
    Measured over the whole corpus, the allow-list was silently discarding 6,700 source
    bullets: 6,137 under "Events and trends", 2,395 under "Inventions, discoveries,
    introductions", 672 Nobel prizes, 200 under "Architecture", plus the month-range
    headings ("January - March") some year articles use instead of "Events".

    An allow-list of section names cannot be completed by thinking, because Wikipedia
    keeps inventing headings; a deny-list can, because there are only 62 distinct
    top-level headings in 5,026 harvested articles and the ones to refuse are the ones
    that are not the record -- apparatus (references, sources, further reading) and
    invention (fiction, legend, popular culture, predicted events)."""
    tops = {m.group(1).strip().lower()
            for m in re.finditer(r"^==\s*(.+?)\s*==\s*$", wikitext, re.M)}
    tops = {re.sub(r"\s+", " ", LINK_RE.sub(lambda m: (m.group(2) or m.group(1)), t).strip())
            for t in tops}
    return {t for t in tops if t not in SKIP_TOP}


# Not DATE_LEAD: that one is defined above with named groups and parse_date depends on it.
DAY_LEAD = re.compile(rf"^((?:{MONTH_RE})\s+\d{{1,2}}|\d{{1,2}}\s+(?:{MONTH_RE}))\b")


def date_header(bare: str) -> str | None:
    """The day for a run of nested bullets, or None when the parent is an event itself.

    Wikipedia does not always write the parent as a bare date. Through the war years it
    writes "December 7 (December 8 - 3:18 a.m., Japan Standard Time) - WWII:" and hangs
    the day's events underneath. Matching only a bare date left those children with no
    day at all, so the attack on Pearl Harbor was filed under "December" and never
    reached the December 7 calendar page. A parenthetical and a short topic prefix
    ending in a colon are heading furniture, not a sentence, so they are allowed here.
    """
    s = bare.strip(" \u2013-\u2014:")
    if DATE_ONLY.match(s):
        return s
    s = bare.strip()
    m = DAY_LEAD.match(s)
    if not m:
        return None
    rest = re.sub(r"^\([^)]*\)\s*[\u2013\u2014-]?\s*", "",
                  s[m.end():].strip(" \u2013\u2014-")).strip()
    if rest and not (rest.endswith(":") and len(rest.split()) <= 4):
        return None
    return m.group(1)


def iter_sections(wikitext: str):
    """Yield (heading_trail, line) for every top-level list item under a wanted section."""
    wanted = wanted_tops(wikitext)
    trail: list[str] = []
    top = None
    pending_date = None
    for raw in wikitext.split("\n"):
        line = raw.rstrip()
        hm = re.match(r"^(={2,6})\s*(.+?)\s*\1\s*$", line)
        if hm:
            level, name = len(hm.group(1)), hm.group(2)
            name = LINK_RE.sub(lambda m: (m.group(2) or m.group(1)), name).strip()
            name = re.sub(r"\s+", " ", name)
            trail = trail[: level - 2] + [name]
            top = trail[0].lower() if trail else None
            continue
        if not top or top in SKIP_TOP or top not in wanted:
            continue
        # Colon-indented bullets (":*", "::*") are the same nesting written another way,
        # used through the Roman-republic years: "*[[Second Punic War]]" with ":* Hannibal
        # crosses the Alps" underneath. Reading only "*" lines left 218 BC -- Hannibal,
        # the elephants, the Alps, Saguntum -- as a one-line page about a siege in Asia
        # Minor. 112 such lines across 30 articles.
        if re.match(r"^:+\*", line):
            body = re.sub(r"^:+\**", "", line).strip()
            if len(body) >= 40:
                yield trail[:], body, pending_date
            continue
        if not line.startswith("*"):
            continue
        if line.startswith("**"):
            # Nested under a bare date bullet ("* [[July 20]]") these are full events
            # for that date; nested under a described event they are its continuation.
            body = line.lstrip("*").strip()
            if len(body) < 40:
                continue
            yield trail[:], body, pending_date
            continue
        body = line[1:].strip()
        bare, _, _ = clean_line(body)
        pending_date = date_header(bare)
        if len(body) < 25:
            continue
        yield trail[:], body, None


# --- year scoping -------------------------------------------------------------------
# Not every year has its own Wikipedia article. AD 4 redirects to "0s", 2900 BC lives
# inside "29th century BC". Those articles are perfectly good sources, but they cover ten
# or a hundred years at once, so publishing them wholesale under one year puts claims on
# a page that are not about that year at all — the old build had Ramesses II's reign on
# the 1274 BCE page and a 771 BC birth on the 776 BCE page.
#
# When the source article is not the year itself, a claim is kept only if the article
# itself attributes it to this year: either the section it sits under is that year's
# heading, or the line opens by naming the year. Everything else is dropped, and a year
# left with nothing simply does not get a page.

def year_titles(year: int) -> set[str]:
    # "<year> events" is the companion article Wikipedia splits a prose-converted year
    # into; it is about that one year and nothing else, so it scopes exactly like the
    # year's own article. See events_companion() in harvest.py.
    if year > 0:
        return {str(year), f"AD {year}", f"{year} AD", f"{year} events"}
    b = abs(year) + 1
    return {f"{b} BC", f"{b} BCE", f"{b} BC events"}


def is_year_scoped(title: str, year: int) -> bool:
    """True when the source article is about this one year and nothing else."""
    return title.strip() in year_titles(year)


def _year_lead_re(year: int) -> "re.Pattern[str]":
    n = year if year > 0 else abs(year) + 1
    era = r"\s*(?:BCE?)" if year <= 0 else r"(?:\s*(?:AD|CE))?"
    # "c. 3000 BC: Camels are domesticated" keeps; "c. 3300 BC – 2600 BC: ..." does not,
    # because the separator is followed by a second, different year.
    return re.compile(rf"^(?:c\.|circa|ca\.)?\s*(?:AD\s+)?{n}{era}\s*[:–—-]\s*(?!\d{{1,4}}\s*(?:BCE?|AD)?\s*[:–—-])",
                      re.I)


def claim_is_about(year: int, trail: list[str], sentence: str) -> bool:
    toks = {t.lower() for t in year_titles(year)}
    if any(h.strip().lower() in toks for h in trail):
        return True
    return bool(_year_lead_re(year).match(sentence))


def ordinal(n: int) -> str:
    suf = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def plausible_sources(year: int) -> set[str]:
    """Every article title it is legitimate to build this year's page from: the year's own
    article, or the decade, century or millennium article the year falls inside. Anything
    else means the harvester followed a redirect somewhere it should not have — "2" is the
    article about the number two, "100" likewise — and the page must not be published."""
    n = year if year > 0 else abs(year) + 1
    era = "" if year > 0 else " BC"
    out = set(year_titles(year))
    out.add(f"{n} (year)")
    out.add(f"{(n // 10) * 10}s{era}")
    # Wikipedia disambiguates some decade titles: "1600s BC (decade)" vs "1600s BC",
    # which is the century-spanning article.
    out.add(f"{(n // 10) * 10}s{era} (decade)")
    out.add(f"{ordinal((n - 1) // 100 + 1)} century{era}")
    out.add(f"{ordinal((n - 1) // 1000 + 1)} millennium{era}")
    return out


def kind_of(trail: list[str]) -> str:
    top = trail[0].lower() if trail else ""
    if top.startswith("birth"):
        return "birth"
    if top.startswith("death"):
        return "death"
    return "event"


def extract(rec: dict) -> list[dict]:
    scoped = is_year_scoped(rec["source"]["title"], rec["year"])
    out, seen = [], set()
    for trail, body, inherited_date in iter_sections(rec["wikitext"]):
        sentence, links, ok = clean_line(body)
        # A nested bullet's own line carries no date; the date is the parent bullet.
        # Prefix it for display but keep `raw` the untouched source line, so verify.py
        # can still find it verbatim in the revision.
        if inherited_date and sentence:
            sentence = f"{inherited_date} – {sentence}"
        # The cap exists to reject a runaway parse, not to edit history. At 600 it cut the
        # September 11 attacks out of 2001 (631 characters) because Wikipedia writes the
        # biggest event of a year at the greatest length -- the ceiling was selecting
        # against importance. 1200 still catches a genuine parse blow-up.
        if not ok or len(sentence) < 30 or len(sentence) > 1200:
            continue
        if not re.search(r"[a-zA-Z]{3}", sentence):
            continue
        if not scoped and not claim_is_about(rec["year"], trail, sentence):
            continue
        key = sentence.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        date_label, mon, day = parse_date(sentence, trail)
        kind = kind_of(trail)
        body_txt = strip_date_lead(sentence) if date_label else sentence
        if len(body_txt) < 20:
            continue
        out.append({
            "id": f"{rec['year']}:{hashlib.sha1(sentence.encode()).hexdigest()[:12]}",
            "kind": kind,
            "date": date_label,
            "month": mon,
            "day": day,
            "section_trail": trail,
            "text": sentence,       # cleaned source sentence, date lead included
            "body": body_txt,       # same sentence with the date lead removed
            "links": links[:12],
            "raw": body,            # the exact wikitext line, for verify.py
            "date_prefix": inherited_date,  # added for display, not present in `raw`
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    files = sorted(
        (f for f in os.listdir(a.raw) if f.endswith(".json") and not f.startswith("_")),
        key=lambda f: int(f[:-5]),
    )
    totals, thin = 0, []
    for fn in files:
        rec = json.load(open(os.path.join(a.raw, fn), encoding="utf-8"))
        claims = extract(rec)
        # A decade or century article's lead summarises the decade, not this year, so it
        # is not this page's summary and the page falls back to its own top entries.
        hi = (article_highlights(rec["wikitext"])
              if is_year_scoped(rec["source"]["title"], rec["year"]) else None)
        totals += len(claims)
        if len(claims) < 3:
            thin.append((rec["year"], rec["source"]["title"], len(claims)))
        json.dump({"year": rec["year"], "label": rec["label"], "source": rec["source"],
                   "highlights": hi[0] if hi else None,
                   "highlights_from": hi[1] if hi else None,
                   "claims": claims},
                  open(os.path.join(a.out, fn), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"years={len(files)} claims={totals} avg={totals / max(1, len(files)):.1f}")
    if thin:
        print(f"thin years ({len(thin)}):", thin[:25])
    return 0


if __name__ == "__main__":
    sys.exit(main())
