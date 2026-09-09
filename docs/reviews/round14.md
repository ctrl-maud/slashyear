# Round fourteen — one subject, five pages

Round thirteen found a defect in **placement**: a perfectly quoted sentence under the wrong
heading. This round is the same idea one level up — a perfectly built page about a subject
that is not one subject.

## The class: an entity page is a claim about identity, and nothing tested it

`entities.py` groups published rows by the article Wikipedia's editors linked:
`[[Constantinople]]` in the wikitext puts that row on `/timeline/constantinople`. That is
the right source of truth — the association is Wikipedia's editorial judgement, not ours.
But the group key was the **string**, and one subject is written many ways. Editors link
Persia and Iran, Macedon and Macedonia (ancient kingdom), Sassanid Empire and Sasanian
Empire, USSR and Soviet Union, Byzantine and Byzantine Empire and Eastern Roman Empire.

Measured against Wikipedia's own redirect graph, before the fix:

- **136 subjects were split across 284 pages.** The Byzantine Empire's timeline was missing
  the 19 rows filed under "Byzantine" and "Eastern Roman Empire". Persia (63 rows) and Iran
  (179) were two countries. The Sasanian Empire's *canonical* page had 59 rows while
  "Sassanid Empire" had 112 — the smaller page was the real one.
- **383 of 4,660 entity pages carried no Wikidata id**, which is the one thing the format
  promises that a Wikipedia article does not: "a QID is the join key every other database
  on earth uses". A redirect title has no item of its own, so exactly the pages with the
  wrong title were the pages with no key.
- 400 of the 4,660 page titles were redirects rather than articles.

No existing gate could see this. `verify.py` reads year pages. `surface.py` checked that
every entity row traces back to a year page — every one of them did, on both halves of a
split. `integrity.py` re-renders text. `audit.py` checks that links resolve — they did.
Splitting one subject into three pages produces three internally perfect pages.

## The fix

`entities.py` now resolves every link title through `action=query&redirects=1` — Wikipedia's
own redirect graph, batched 50 at a time and cached on disk — **before** grouping, and
merges the rows under the canonical article. Deciding for ourselves that "Sassanid" and
"Sasanian" are the same empire is exactly the judgement this project refuses to make; the
redirect graph is Wikipedia making it for us, and it is a fact we can cite.

Three things had to be true for the merge not to cost anything:

1. **A sentence that links both Persia and Iran counts once.** Dedupe after remapping, or
   the merge inflates its own row counts.
2. **A redirect into something we never publish must not delete rows.** "Byzantine emperor"
   and "Ottoman Sultan" redirect to *List of…* articles, "Catholicism" to the excluded
   "Catholic Church". Those groups still merge — they are just titled with the spelling
   the editors used most, so Catholic Church stopped being three pages without becoming
   zero.
3. **A merge must not cost a URL.** Every alias slug that was a live page is written to
   `data/entities-merged.json`, ranked by how many years it covered before the merge, and
   `postbuild.py` turns the first 2,000 into 301s in `_redirects` (Cloudflare Pages accepts
   2,100 rules and silently ignores the rest). Of the 4,660 URLs live before this round,
   **1** now 404s. The aliases are also printed on the page: "Also written as Sasanid
   Empire, Sassanian Empire, Sassanid, …".

## After

| | before | after |
|---|---|---|
| entity timelines | 4,660 | 4,868 |
| carrying a Wikidata id | 4,277 (92%) | 4,837 (99.4%) |
| subjects split across pages | 136 across 284 | 0 |
| rows on entity timelines | 87,898 | 92,894 |
| 301s for merged aliases | — | 2,000 |

43,969 published links followed a redirect to their canonical title. The site grew to 8,959
pages and 287,005 bullets, and the extra timelines fit inside the file budget (18,327 of the
20,000 Cloudflare Pages allows).

## The gate

`surface.py` gained an **IDENTITY** check, because this class comes back the moment anyone
touches the entity build: no two published entity pages may resolve to the same canonical
Wikipedia article, and no page may be titled with a redirect unless the article it
redirects to is one we never publish. It caught its own first regression — after the first
fix, Catholic Church was still three pages and the Ottoman sultans three more, because the
"redirect into a list" branch had quietly reverted to keeping every spelling separate.

## Also found

**`data/site/` is a namespace, not a directory.** Writing the merge map to
`data/site/entities-merged.json` crashed `postbuild.py` with
`ValueError: invalid literal for int(): 'entities-merged'`, and would have crashed
`verify.py`, `surface.py` and `dates.py` the same way: four stages enumerate that directory
as "one JSON per year" and `int()` the filename. The map lives at
`data/entities-merged.json` instead. Anything that is not a year page does not belong in
that folder.

## Known limits

- 31 pages still have no Wikidata id (titles whose sitelink lookup fails, e.g. "Chu (State)").
- Twelve pages are calendar months — `[[January]]` linked as a bare month is a date
  artifact rather than a subject, the same reason `[[January 5]]` is already excluded. They
  are accurate, so they stay for now.
- A cold redirect cache costs 8,024 API batches (~25 minutes) because every link in the
  corpus is resolved, not only the published ones. It is cached on disk and written
  incrementally, so it is paid once.

## Lesson

**A page can be internally perfect and still be the wrong page.** Round thirteen found rows
under the wrong heading; this round found whole pages that were one subject wearing five
names, and every existing test passed on every one of them because each split was
self-consistent. When a system groups by a name, ask who owns the name — and if the source
publishes its own identity graph, join on that instead of on the string.
