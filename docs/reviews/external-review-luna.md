# Second-opinion audit: a second, unrelated frontier model, 8 September 2026

The maintainer supplied an Azure endpoint for `a second, unrelated frontier model` and said to use it but to take its
output with a grain of salt and double-check everything. That is the right instruction:
of the 60 claims it made across six review angles, **13 were real**, and the rest were
either theoretical (invented inputs that do not occur in this corpus), wrong about the
code, or wrong about the design.

Every claim below was checked against the real corpus or the real code before it was
acted on. The auditor was driven by a small local script; its credentials live in
an environment file kept outside the repository.

## Confirmed and fixed

| # | Claim | How it was confirmed | Fix |
|---|---|---|---|
| A3 | An unbalanced `(` truncates the sentence and it is still published | **162 published rows** ended mid-sentence, e.g. 1494 "…on his way toward Italy, in order to assert his claim to become King of Naples" | `extract.py` now marks the line unclean instead of truncating it |
| E20 | Lines that are a heading for nested bullets are published as rows | **61 rows** ending in a colon, e.g. 1455 "May 22 (killed at the First Battle of St Albans):" | `extract.py` rejects a sentence that ends on a colon |
| A14 | A label-less external link survives into the sentence | 4 rows, e.g. 1981 "…assassinated in Chittagong.[https://news.bbc.co.uk/…]" | `BARELINK_RE` strips it |
| E23 | Unbalanced italics leave a stray apostrophe | 3 rows, e.g. 1855 "…is incorporated as a city.'" | rejected by the same guard |
| C1 | `span_days` reads "November 5 – 11,000 scientists…" as the range 5–11 | **17 calendar rows** filed on days the event did not happen | `SPAN_SAME`/`SPAN_CROSS` end with `(?![\d,])` |
| C9 | Entity timelines sort on the date *string*, so December precedes January | **1,005 of 4,670 timelines** out of order — Michael Jackson's 2009 read "June 25, June 25, March 5" | `entities.py` sorts on `(month, day)` |
| C5 | Astronomical year 0 is 1 BCE but `decade_of` sent it to the AD side | `/0` sat in decade `0s` and century `1st century BC` at once | `decade_of` treats `year >= 1` as AD |
| B7 | `DATEISH` is not end-anchored, so "20th Century Fox" is scored as a date | `DATEISH.match("20th Century Fox")` was true | anchored |
| F | The timeline JSON-LD claims `numberOfItems: p.entries` but encodes 40 | read the component | count is now the encoded length |
| F | The year footer says every line is quoted from *one* source, but deaths pages carry extra sources | read the component | footer now points at the revision linked beside each line |
| C4 | 100 BC sits in our 2nd century BC while Wikipedia calls it the 1st | Wikipedia's own short description: "1st century BC — one hundred years, from 100 BC to 1 BC" | **not** a bug: it is the same loose convention the site already uses for AD (1900–1999), without which decades do not nest. The century page now states the BC side of the rule explicitly |

Plus five new tripwires in `pipeline/surface.py` so none of these can come back: raw
external links, colon-terminated headings, unbalanced brackets, non-chronological
timelines, era-inconsistent breadcrumbs, and calendar rows printing a range that does not
contain the day they are filed under.

## Rejected, with the measurement that rejected it

- **"19 published rows have a date that is not in the wikitext" (its single largest
  finding).** False, and it is the model not knowing the format. Wikipedia writes a bare
  date bullet with the events nested under it, and those children inherit the parent's
  date — **251,413 claims** carry an inherited `date_prefix`. The date is in the source,
  one line up.
- **"Markup residue in a published sentence."** Zero in the current corpus.
- **"Impossible dates such as February 31 are published."** Zero.
- **"Claims whose theme is not in SECTION_ORDER are silently lost."** All 14 themes the
  classifier emits are in `SECTION_ORDER`; the set difference is empty.
- **"Chronicle content in wikitables and numbered lists is never extracted."** 599 source
  articles contain 5 tables and 1 numbered line between them.
- **"The 404 page fetches /years.json, which the build never writes."** It does write it;
  the file is in `site/out/years.json` and the page works.
- Everything in its lists that was triggered by a hand-written input never present in the
  corpus (nested ship templates, `</ref >` with a space, `&#124;`, `<span title="a > b">`,
  120-character duplicate prefixes) — checked, none occur.

## What the exercise is worth

The model is a useful *generator of hypotheses* and a bad judge of which ones are true: it
cannot tell a real defect from one it invented, and it presented both in the same
confident format. Its best single contribution — the truncation bug — was worth the whole
run, and it was found by reading the code rather than the data, which is the half a
data-driven sweep cannot do. The rule that follows is to keep using it exactly this way:
let it propose, measure every claim against the corpus, and never let it write.
