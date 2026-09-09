# Round thirteen — the placement, not the words

Twelve rounds of checking have all asked the same question in different ways: *does the
sentence we published really say what its source says?* `verify.py` proves the text is in
the cited revision, `integrity.py` re-renders it with a second implementation,
`surface.py` checks its shape, `coverage.py`, `famous.py` and `montage.py` ask whether the
famous thing is present at all. Every one of them is about the words.

None of them can see a defect in the **placement** — the sentence is quoted perfectly, from
the right revision, in the right shape, and it is filed under the wrong heading or on the
wrong page. That class passes the whole suite, and this round is about it.

## What found it: a database we did not write

The round-twelve lesson was that a test built on a list I wrote can only find holes I
already thought of, so look for a signal already in the data. This time the signal came
from outside the corpus entirely: **Wikidata**, where every person has a structured date of
birth (P569) and death (P570) that no year-article editor touches by hand.

`pipeline/lifedates.py` takes every published Births/Deaths row that links its subject —
34,067 of them across 24,193 distinct people — asks Wikidata for that person's dates
through the article title the row itself links, and requires that the page's year is a year
Wikidata records and that a day-precision row prints a day Wikidata records. A row is only
flagged when **no** statement on the item agrees, so people with two competing recorded
dates never fire.

### The first run was wrong, and the way it was wrong is the point

It reported 6,390 day mismatches out of 18,002 — 35%, which is not a defect rate, it is a
broken instrument. The offsets clustered: six days around 500 BC, nine days in the 1490s,
ten days in the 1500s. That is the Julian drift.

Wikidata **stores** every timestamp in the proleptic Gregorian calendar and records
separately, in the calendar-model field, which calendar the date was actually given in.
Wikipedia's year articles print the Julian date for everything before 1582. So Caesar's
death is `-0043-03-13` in the store, `15 March 44 BC` on the page, and the two are the same
day. `to_julian()` converts back before comparing; the false mismatches fell from 6,390 to
1,067 and the residue stopped being a straight line.

## The defect: 910 rows published as deaths that are not deaths

`classify.py` files an event sentence under Deaths on a lexical rule, because year articles
record plenty of real deaths inside the Events section ("Death of Egyptian pharaoh Djet").
The rule was `\bDeaths? of\b` or `\b(dies|died)\b`, and it wins outright over the embedding.

But *death* is a word that appears far more often in sentences about what happened **next**
than in sentences about someone dying. Succession is the single commonest genre in the
corpus. So the site published, under the heading **Deaths**:

| year | published under "Deaths" |
|---|---|
| 1945 | April 12 – Vice President Harry S. Truman becomes the 33rd president of the United States, upon the death of Franklin D. Roosevelt |
| 1934 | August 2 – Adolf Hitler becomes Führer of Germany … following the death of Paul von Hindenburg |
| 1837 | June 20 – Queen Victoria, 18, accedes to the throne of the United Kingdom, on the death of her uncle |
| 2009 | March 5 – Michael Jackson announces his This Is It concert residency in London |
| 1943 | January 12 – WWII: Landing at Amchitka: American forces make an unopposed landing |
| 1400 | Jagiellonian University is re-established in Kraków by order of King Władysław II |
| 1368 | December 3 – Joanna of Bourbon … gives birth to his first child, the Dauphin Charles |
| 1804 | July 11 – Aaron Burr … shoots former U.S. Secretary of the Treasury Alexander Hamilton |

910 of the 21,721 rows in the site's Deaths sections — 4.2% — were sentences of that kind:
accessions, battles, an announcement, a university's refounding, a birth. Two of them
(Truman, Hitler) are among the most-read rows on the site. The error propagates: the 366
calendar pages group their rows into Events / Births / **Deaths** from the same heading, so
5 March carried Michael Jackson's concert announcement under Deaths, and every entity
timeline counts them in its Deaths topic.

Note what could not have caught this. The sentence is a perfect quotation; the revision is
right; the shape is right; the famous event *is* present. The only thing wrong is the
heading above it, and no gate had an opinion about headings.

### The fix

A row reports a death when **its own dated clause** does. `classify.reports_a_death()`:

1. strips the date prefix and takes the sentence the row's date is about (short fragments
   are joined on, so "Pope St. John dies" is not cut at "Pope St.");
2. fires on a death **predicate** — *dies*, *died*, *is/are/was/were killed, assassinated,
   executed, murdered, beheaded, put to death*, *commits suicide* — keeping the old
   exclusion for "dies in the battle of …", which belongs under Conflict;
3. otherwise fires on a sentence-level "Death of X", but **not** when the only mention is
   the hinge of a succession: *upon / after / on / following / since / with / at / because
   of the death of*.

Eleven hand-picked cases, including every row in the table above, decide correctly. After
the rebuild: **0 non-death event rows remain under Deaths**, and the rows that do report a
death (Skandagupta, Leonidas, Pope Gregory I) are still there — 2,642 of them, up from
2,387, because the cap seats they were losing to accession sentences are now theirs.

## The residue, and what it is not

After the fix and the calendar correction, 29,965 birth/death years and 17,071 day dates
were compared against Wikidata: **1,903 year disagreements (6.4%) and 943 day
disagreements (5.5%)** remain. These are not defects and are not ours to fix:

- **Old Style / New Style.** After 1582 the two databases often carry different calendars
  for the same event — Yuri Andropov is 15 June 1914 on the year page and 2 June (Julian)
  in Wikidata; Qi Jiguang, Toyotomi Hideyori and Shah Jahan are lunisolar-to-Gregorian
  conversions that nobody agrees on.
- **Wikipedia disagreeing with itself.** Chun Doo-hwan is listed on the 1931 page under
  6 March; his own article says 18 January. We publish the year page's line verbatim.
- **Badly attested lives.** 1,000 of the 1,903 year disagreements are before 1000 CE, where
  a one-year difference between the year article and Wikidata is the normal state.

We quote, we do not correct — the same verdict round twelve reached on the 19 impossible
birth/death pairs. So the gate ships as a **ratchet, not a zero**: `lifedates.baseline.json`
records the accepted counts and the gate fails a build that pushes either one higher,
which is exactly what a row moved onto the wrong page or the wrong day would do.

## State after the round

| gate | result |
|---|---|
| verify | 86,899 bullets, 0 failures; 3,360 cited revisions re-downloaded byte-identical |
| coverage | 51/51 |
| famous | 333/333 |
| surface | all page kinds clean, 195,145 cross-cut rows traced |
| integrity | clean, 86,899 year + 87,898 timeline + 58,017 calendar rows |
| montage | every caption event the article lists is published |
| lifedates | 29,965 years and 17,071 day dates checked against Wikidata; at baseline |
| audit | clean |

3,078 year pages · 86,899 entries · 366 calendar pages · 4,660 entity timelines.

## Also probed, and clean

- **Citation anchors.** Every published row's `#section` fragment was checked against the
  headings that really exist in the cited revision and against the section the line really
  sits in: 86,554 correct, 0 anchors pointing at a heading the article does not have.
- **Date parsing.** Every row whose text opens with a date was re-parsed and compared with
  the stored month/day: 0 mismatches. The seven rows whose month disagrees with the
  *heading* they were harvested under are Wikipedia's own misfilings (Zane Grey, who died
  23 October 1939, is listed under September) and we follow the line, not the heading.
- **Calendar pages.** No row appears on a day its own date does not cover, spans included.
- **Duplication.** 0 exact duplicate rows and 0 bag-of-words duplicates within a page.
- **Era arithmetic.** Every page label matches its astronomical key (year 0 is "1 BCE"),
  and every decade page holds exactly the ten years its label names on both sides of the
  BC/AD boundary. The site groups centuries by shared digits (1900–1999 is the 20th
  century, 499–400 BC the 5th BC), which is common usage rather than Wikipedia's strict
  1901–2000 — a convention, applied consistently, not a defect.

## Lesson

**Every gate we had was about the words; a whole class of defect lives in the placement.**
A perfectly quoted sentence under the wrong heading is invisible to text verification,
shape checking and coverage lists alike. Finding it took a structured database outside the
corpus — and the first thing that database taught was that 35% of its own findings were an
artefact of a calendar convention, which is the real cost of an external signal: you have
to calibrate the instrument before you believe a single reading.
