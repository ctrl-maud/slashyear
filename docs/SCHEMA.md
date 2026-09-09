# Schema

Four record types. Every one of them is derived from a numbered Wikipedia revision and carries
enough provenance to be checked against it without asking us for anything.

## Conventions that bite

- **Years are astronomical.** There is no year zero in the common era, so 1 BCE is `0`, 44 BCE is
  `-43` and 776 BCE is `-775`. Page slugs use the same numbering: `/-43` is the year Caesar was
  killed. Getting this wrong offsets every BCE row by one.
- **`revid` is a frozen revision, not a page.** `https://en.wikipedia.org/w/index.php?oldid=<revid>`
  resolves to the exact wording quoted, permanently. A bare article URL does not.
- **`section` is the path inside that revision**, e.g. `Events › January`, and the `#anchor` on the
  citation URL lands the reader on it.
- **`text` is verbatim.** Wiki markup (links, templates, refs) is removed mechanically by
  `clean_line()` in `pipeline/extract.py`; no word is added, reordered or rephrased. That function
  is the single definition of "cleaned", which is why `verify.py` imports it rather than
  reimplementing it.

## `events` — one dated entry

| field | type | meaning |
| --- | --- | --- |
| `year` | int | astronomical year the entry belongs to |
| `date` | string \| null | day within the year as the source writes it (`"January 20"`); null when the source dates it only to the year |
| `text` | string | the source sentence, markup stripped, otherwise untouched |
| `theme` | string | section it was filed under (see themes below) |
| `cite.revid` | int | the revision the sentence was quoted from |
| `cite.title` | string | the article that revision belongs to |
| `cite.section` | string | section path inside that revision |
| `cite.url` | string | `?oldid=<revid>#<anchor>` — resolves to the paragraph |

## `years` — one page payload

| field | type | meaning |
| --- | --- | --- |
| `year`, `label` | int, string | `1969`, `"1969 CE"` |
| `lead` | string | the summary **the source article's own editors wrote** — the year montage caption or the lead paragraph — quoted, not characterised |
| `lead_from` | string | which of those the lead came from, so the reader knows what they are reading |
| `lead_items` | string[] | the entries the lead refers to, verbatim, when the article has no summary |
| `sections[]` | `{title, items[]}` | themed sections in canonical order; a section appears only when it has enough entries to deserve a heading |
| `counts` | object | entries kept vs available, per section |
| `source`, `extra_sources` | object[] | the revisions this page was assembled from |

Bullets inside a section run in calendar order with undated entries last. Which entries make the
page is decided by notability — the byte length of the Wikipedia articles an entry links to, the
encyclopedia's own accumulated judgement of how much there is to say about a thing. How many year
articles link an entity is kept only as a weak tiebreak, because on its own it ranks "Spain" above
the Apollo 11 Moon landing.

## `subjects` — a thing with a timeline

| field | type | meaning |
| --- | --- | --- |
| `label` | string | display name, e.g. `Byzantine Empire` |
| `slug` | string | URL form, `byzantine-empire` |
| `qid` | string \| null | Wikidata id where one was matched |
| `description` | string \| null | short Wikidata description |
| `count` | int | entries in its timeline |

## `subject_events` — the join

`slug` → `event`, so a subject's timeline is a lookup rather than a search. This is what makes
`/timeline/<slug>` static.

## Themes

Section titles are canonical and fixed, not generated per page, so the same theme means the same
thing in 44 BCE and in 1969. `pipeline/theming.py` checks the assignment against the source
article's own "By topic" headings and ratchets: the score may improve, never regress.
