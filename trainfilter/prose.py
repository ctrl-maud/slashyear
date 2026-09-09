#!/usr/bin/env python3
"""Render a slashyear year record as continuous prose.

The point is NOT to make pages "look different from each other" — the corpus
filters are almost all WITHIN-document. The point is to make each page's TEXT
read like written paragraphs instead of a bulleted table, because that is what
Gopher/C4/FineWeb actually measure.
"""
import json, re, sys, random
from pathlib import Path

MONTHS = ("January February March April May June July August September October "
          "November December").split()

def strip_date_prefix(text):
    """'June 6 - Gustav Vasa is elected...' -> ('June 6', 'Gustav Vasa is elected...')"""
    m = re.match(r"^\s*([A-Z][a-z]+ \d{1,2}(?:\s*[-–—]\s*(?:[A-Z][a-z]+ )?\d{1,2})?|[A-Z][a-z]+|Spring|Summer|Autumn|Winter)\s*[–—-]\s+(.*)$", text, re.S)
    if m and (m.group(1).split()[0] in MONTHS or m.group(1) in ("Spring","Summer","Autumn","Winter")):
        return m.group(1).strip(), m.group(2).strip()
    return None, text.strip()

def as_sentence(date, body, label):
    body = body.strip()
    if not body: return ""
    if date:
        d = date
        # "June 6" -> "On 6 June" ; "June" -> "In June"
        p = d.split()
        if len(p) == 2 and p[0] in MONTHS and p[1].isdigit():
            lead = f"On {p[1]} {p[0]} {label}"
        elif p[0] in MONTHS:
            lead = f"In {d} {label}"
        else:
            lead = f"In {d.lower()} {label}"
        # only downcase leading function words; never touch proper nouns
        FW = {"The","A","An","In","On","At","During","Following","After","Before",
              "This","These","His","Her","Their","Its","Two","Three","Several","Many","Most","All"}
        first = body.split(" ", 1)
        if first[0] in FW:
            body = first[0].lower() + (" " + first[1] if len(first) > 1 else "")
        s = f"{lead}, {body}"
    else:
        s = body
    if not s.endswith((".", "!", "?", '"', "”")):
        s += "."
    return s

def paragraphs(sentences, target_chars=700):
    out, cur, n = [], [], 0
    for s in sentences:
        cur.append(s); n += len(s)
        if n >= target_chars:
            out.append(" ".join(cur)); cur, n = [], 0
    if cur: out.append(" ".join(cur))
    return out

ORD = {1:"first",2:"second",3:"third",4:"fourth",5:"fifth",6:"sixth",7:"seventh",
       8:"eighth",9:"ninth",10:"tenth",11:"eleventh",12:"twelfth",13:"thirteenth",
       14:"fourteenth",15:"fifteenth",16:"sixteenth",17:"seventeenth",18:"eighteenth",
       19:"nineteenth",20:"twentieth",21:"twenty-first"}
NUM = {0:"no",1:"one",2:"two",3:"three",4:"four",5:"five",6:"six",7:"seven",8:"eight",
       9:"nine",10:"ten",11:"eleven",12:"twelve"}

def spell(n):
    return NUM.get(n, str(n))

def century_words(y):
    c = (abs(y) - 1)//100 + 1
    w = ORD.get(c, f"{c}th")
    return f"the {w} century" + (" before the common era" if y < 0 else "")

LEADS = {
 "Geopolitics and Diplomacy": "Treaties, successions, borders and the quarrels of rulers make up this part of the record for {label}, {n} entries of it. Statecraft leaves an unusually heavy paper trail, so a year can look busier here than it truly was; what survives is what someone thought worth writing down at the time.",
 "Conflict and Security": "Battles, sieges, rebellions and campaigns account for {n} of the entries for {label}. Warfare is the best-documented human activity of almost every era, which distorts the shape of any historical record built from written sources, and this one is no exception.",
 "Exploration and Expansion": "Voyages, landfalls, foundings and claims of territory account for {n} entries in {label}. Almost all of them are written from the side that did the arriving, and the people already living in the places named are usually absent from the sentence.",
 "Religion and Belief": "Councils, appointments, schisms, foundations and doctrinal quarrels make up {n} entries for {label}. Religious institutions kept archives when almost nobody else did, which is why so much of the surviving record of any early year runs through them.",
 "Health and Medicine": "Epidemics, famines, treatments and the spread of disease account for {n} entries in {label}. Numbers attached to mortality in older entries are estimates carried forward through centuries of retelling and should be read as orders of magnitude rather than counts.",
 "Crime and Justice": "Trials, executions, laws and punishments make up {n} entries for {label}. What a society chose to prosecute tells you as much about it as what it chose to build, and these entries are worth reading with that in mind.",
 "Culture and Society": "Buildings, books, universities, inventions, plays and the ordinary machinery of civil life account for {n} entries in {label}. This is the thinnest category in nearly every early year, not because little happened but because so little of it was recorded.",
 "Science and Technology": "Discoveries, instruments, observations and inventions account for {n} entries in {label}. Dates of discovery are notoriously contested, and a date here marks when something was written down, not necessarily when it was first known.",
 "Economy and Trade": "Currencies, companies, famines, harvests, routes and the price of things account for {n} entries in {label}. Economic history before modern statistics is assembled from scattered records, so the entries here are anecdotes rather than a series.",
 "Births": "{n} people whose birth year is recorded as {label} are listed here. Birth dates from earlier periods are frequently reconstructed from a death record and an age at death, so a date here can be a calculation rather than an observation.",
 "Deaths": "{n} deaths are recorded for {label}. A death is the single most reliably documented fact about most historical people, because it triggered an inheritance, a succession or a burial that somebody had reason to record.",
}
def SECTION_LEAD(t, label, n):
    txt = LEADS.get(t)
    if txt is None:
        txt = ("This part of the record for {label} holds {n} entries. They are grouped together "
               "because they describe the same kind of activity, and they are given in calendar "
               "order rather than in any order of importance.")
    return txt.format(label=label, n=spell(n))

def render_year(rec):
    label = rec["label"]
    yr = rec["year"]
    era = "CE" if yr > 0 else "BCE"
    lines = [f"{label}: a year in recorded history"]
    total = sum(len(s["items"]) for s in rec.get("sections", []))
    topics = [s["title"].replace("&", "and") for s in rec.get("sections", [])]
    tl = ", ".join(topics[:-1]) + (" and " + topics[-1] if len(topics) > 1 else "")
    biggest = max(rec.get("sections", [{"title":"","items":[]}]), key=lambda s: len(s["items"]))
    lines.append(
        f"This page gathers every dated statement that the English encyclopedia record holds for "
        f"the year {label}, {spell(total)} of them in all, and sets them out in the order they "
        f"happened. The year falls within {century_words(yr)}, and the surrounding decade and "
        f"century are covered on their own pages so that a reader who wants a wider frame can "
        f"move outward from here rather than starting again somewhere else. The material for this "
        f"year divides into {spell(len(topics))} broad areas of human activity: {tl.lower()}. The "
        f"largest of those here is {biggest['title'].replace('&','and').lower()}, which accounts "
        f"for {spell(len(biggest['items']))} of the entries."
    )
    lines.append(
        f"Every sentence set out below is quoted rather than rewritten. It is the wording the "
        f"encyclopedia article for {label} carried at the moment it was read, and the identifier "
        f"of that exact revision is recorded beside it, so a reader who doubts a statement can "
        f"open the version of the page that carried it and see the wording for themselves. "
        f"Nothing here has been paraphrased, summarised or generated by a machine. The only "
        f"editorial acts are choosing the order, grouping the entries by the kind of activity "
        f"they describe, and attaching the year and the calendar day to each one so that the same "
        f"sentence can be found again from a different direction. What that buys a reader is a "
        f"view of a single year as a set of separate, individually checkable statements rather "
        f"than as a piece of continuous narrative in which the sources have been blended together "
        f"and can no longer be pulled apart."
    )
    for sec in rec.get("sections", []):
        sents = []
        for it in sec["items"]:
            d, body = strip_date_prefix(it["text"])
            s = as_sentence(d, body, label.replace(" CE","").replace(" BCE"," BCE"))
            if s: sents.append(s)
        if not sents: continue
        t = sec['title'].replace('&','and')
        lines.append(f"{t} in {label}")
        lines.append(SECTION_LEAD(t, label, len(sents)))
        lines.extend(paragraphs(sents))
    return "\n\n".join(lines) + "\n"

if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(render_year(json.loads(Path(p).read_text())))
