# Round eleven — my own check, after luna's

Round ten used a second model as a hypothesis generator. This round is the opposite move:
instead of asking anything to *look* at the rows, I asked what class of defect **no test
in the repo names**, and wrote the test for it.

The gap was structural. `verify.py` re-renders every published row with `clean_line()` —
the same function that produced it — so it agrees with itself by construction and can
never fail on a cleaner bug. `surface.py` asks whether a row *looks* wrong against a list
of shapes we already know about. Nothing anywhere re-read the wikitext with a *different*
renderer and compared.

## The new test: `pipeline/integrity.py`

An independent, deliberately naive wikitext stripper (its own regexes, no import from
`extract.py`), plus twelve classes of page-level self-consistency:

| class | question |
|---|---|
| TRUNC | is the published sentence the WHOLE sentence, measured against an independent strip of its own raw? |
| PAIR | did *we* unbalance a quote or bracket that the source had balanced? |
| RESIDUE | html entities, mojibake, ref/file markup, editor's maintenance notes |
| DUP | is the same sentence published twice on one page? |
| DATE | does the row's date field agree with the date printed in its own text? |
| ERA | year → label, astronomical (−43 is 44 BCE), on every page and every timeline span |
| COUNT | does `counts.shown` / `available` describe the rows actually on the page? |
| ANCHOR | is the cited section anchor really a heading in that revision? |
| DEAD | does every internal link (related timeline, decade, century, cited year) have a page? |
| META | does a timeline's header (entries / years / span / topics) match its own rows? |
| THIN | an indexable page with almost nothing on it |
| DANGLE | a sentence that stops on a connector |

DUP, DATE, ERA, COUNT, ANCHOR, DEAD and META came back **zero on the first run** — 87,122
year rows, 87,849 timeline rows, 58,215 calendar rows, 4,660 timelines. Those are now
proven, not assumed.

## What it found

**1. `{{convert}}` printed a number attached to two units at once — 154 published rows.**
`KEEP_TEMPLATES["convert"]` joined the first three parameters, so
`{{convert|9000|km|mi}}` became **"9,000 km mi"**, `{{convert|40|mi|km}}` became "40 mi
km", and `{{convert|50|km|0}}` became "50 km 0". Worse, a range —
`{{convert|5|to|10|km|mi}}` — dropped the unit entirely and printed "5 – 10", which is how
1208 published *"destroying 58,097 houses over an area of m"*.

The reader cannot tell which unit the number belongs to, and on a site whose whole claim is
that the sentence is the source's own sentence, that is the same failure as the truncation
class: the row is wrong in a way that looks like the source's fault.

Fixed by rendering the input side of the call properly (value, joiners, unit, and compound
forms like `{{convert|5|ft|6|in|m}}` → "5 ft 6 in") and dropping the converted half, which
is the half we cannot compute. 306 claims re-rendered, 251 changed.

**2. An editor's maintenance note published as a historical statement — 1 row.**
76 read *"First year of Jianchu era of the Chinese Han dynasty. (Clarification needed as to
the meaning of this)"* — a note about the article, inside a `<sup>`, where only the tag was
being stripped.

## How the fix shipped without a re-extract

`extract.py` rewrites `data/claims` from scratch and **erases the themes `classify.py`
wrote into the same files** (the trap at the top of the README). But every claim already
stores its exact source line in `raw`, so a cleaner fix does not need the re-extract:

`pipeline/reclean.py --match '<regex on raw>' [--apply]` re-renders only the matching
claims through the current cleaner, rebuilds their id / date / body / links exactly as
`extract()` would, and leaves theme, score, weight and everything else untouched. It prints
every changed line as a diff and refuses to write without `--apply`.

## Tripwires, so neither class can come back

`surface.py` grew two more shape rules:
- **a measurement printed with two units** ("9,000 km mi", "1,400 foot m", "3 miles km"),
  written so the false-positive cases pass — "20 m high", "5 ft 6 in tall", "21 km in
  length", "100 acres";
- **an editor's maintenance note** (clarification / citation / verification / dubious
  needed) surviving into a sentence.

Both were control-tested on cases where the answer is known before being trusted.

## The two things I decided not to change

- **23 rows end on a semicolon** — Wikipedia's own `**` sub-bullets under a parent line
  that ends in a colon (the partition of Babylon in 322 BC is the biggest cluster). Round
  ten correctly stopped publishing the colon-terminated parents, which orphans the
  children. Each child is still a complete, verbatim, correctly-cited statement
  ("Sibyrtius governs Arachosia and Gedrosia;"), and every repair — restoring the parent's
  clause, or rewriting the punctuation — would put words on the page that the source did
  not have there. Left verbatim.
- **420 year pages carry fewer than 3 rows.** Not a pipeline fault: the claims files hold
  exactly what Wikipedia's article holds, and for −1005 that is one line. They are also
  the pages the country-year harvest (open task 1) exists to fill, so the fix is more
  harvest, not different rendering.

## State after the round

87,122 rows / 3,078 year pages / 8,752 pages / 4,660 timelines.
`verify.py` 0 failures (87,122 render matches, 87,122 present in revision) and
`--live` re-downloaded 3,428 revisions byte-identical · `coverage` 51/51 ·
`famous` 333/333 · `surface` clean (69 page-kind cases, 195,483 cross-cut rows) ·
`integrity` clean · `audit` clean (8,752 pages, 282,570 bullets, 377,300 links).
