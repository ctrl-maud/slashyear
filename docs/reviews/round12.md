# Round twelve — the editors' own picks

Round eleven asked what class of defect no test names, and found a *rendering* bug. This
round asked the harder version of the same question: **is there an importance signal in
the data that we did not invent?** Every coverage test we own — `coverage.py` (51 cases),
`famous.py` (333) — checks a list I wrote, so it can only ever find holes I already
thought of. Both were passing.

There is such a signal. Every year article from 1900 on carries a photo montage, and its
caption names the handful of events that year's own editors chose to stand for the year.
We already quote it: it is the muted lead line on those 121 pages. Nothing checked whether
the events it names are actually **on the page**.

## What that test found

**44 caption events had been harvested and then dropped**, in years where every other test
passed:

| year | the caption says | we published |
|---|---|---|
| 1940 | the Dunkirk evacuation, the Katyn massacre, the Greco-Italian War | none of them |
| 1944 | the 20 July plot | no |
| 1945 | Iwo Jima; Truman succeeding Roosevelt; Ho Chi Minh's declaration | no |
| 1961 | the Bay of Pigs invasion | no |
| 1971 | the Pentagon Papers | no |
| 1979 | the Iran hostage crisis | no |
| 1955 | the Warsaw Pact | no |
| 1943 | the Zoot Suit Riots | no |
| 1946 | *It's a Wonderful Life* | no |

Lowering the match floor to the point where a second word has to agree found **70 more of
the same kind**: the Titanic leaving Southampton (1912), the Treaty of Versailles (1919),
the Enabling Act (1933), the first nuclear chain reaction under Stagg Field (1942), My Lai
(1968), Apollo 13's splashdown (1970), the iPod (2001), Hurricane Katrina (2005), the
Tōhoku earthquake and the death of Osama bin Laden (2011), the San Francisco earthquake
(1906), Tunguska and the Model T (1908), Roswell (1947), Selma and the Voting Rights Act
(1965).

The cause is the per-section cap. A war year has hundreds of Conflict & Security entries
and the page shows 24, ranked by our own weighting — which is measured good on 384 cases
and still silently drops Dunkirk.

## The fix

`build.py` now **pins** every row the montage caption is talking about into its section, on
top of the cap, before ranking decides anything (`montage_picks()`). A section can run a
few entries long on a montage year; that is the intended cost. 87,122 → 87,193 rows.

`pipeline/montage.py` is the permanent gate: for each caption clause it compares the best
**published** row against the best row we harvested and **dropped**, and fails when the
dropped one matches clearly better. Its scorer is deliberately not `build.montage_picks` —
a test that reuses the selector's own matcher agrees with it by construction. 912 clauses
across 121 pages, now clean.

Two limits, stated rather than hidden: the signal only exists for years with a montage
(1900 onwards), and **69 caption clauses name something the article's own bullet list never
carries** — Typhoon Jane in 1950, Wilt Chamberlain's 100-point game in 1962, the Iran–Contra
affair in 1985. There is nothing to publish for those; the caption itself is on the page as
the lead.

## Second find: the lead nobody verified

`verify.py` checks the lead only when it was assembled from published rows. On the **182
pages that quote the source article's own prose** — 121 montage captions and 61 article
leads — the most prominent text on the page was checked by nothing at all. `integrity.py`
now confirms every clause of those leads appears in the cited revision, reading the
wikitext two ways (templates kept, because the caption lives inside `{{multiple image}}`;
and templates stripped, because a lead sentence is interrupted by `{{efn}}` footnotes).
All 182 pass. The three that failed first were the test's own fault, fixed before shipping.

## Third find: a bare year that lost its era

`[[113 BC|113]]` renders on Wikipedia as a link labelled "113" — the era is carried by the
link. We publish plain sentences with no links, so −87 read *"Lady Gouyi, mother of Zhao of
Han (b. 113)"*: two centuries wrong to a reader, in a line that is otherwise verbatim. The
era is now restored **only when the finished sentence states no era anywhere**, because in
"136–132 BC" the source already says it and spelling out both halves reads worse than the
source.

## Classes probed that came back clean

- **Birth/death arithmetic** across 37,217 rows: 19 impossible pairs (born after they
  died, or a 464-year life). Every one is verbatim Wikipedia — Thomas Parr's alleged 152
  years, Eber "according to the Hebrew calendar", Hasan-i Sabbah's "(b. c. 1250)" against
  his 1124 death. We quote, we do not correct: the row links the revision that says it.
- **The same sentence on two different year pages** — 19, all legitimate: "approximate
  date" people the source lists in both candidate years, and Prince Narinaga, whom
  Wikipedia itself files under 1337 *and* 1344 because the sources contradict.
- **Entity slug collisions** (would merge two different people into one timeline): 3,415
  slugs carry more than one spelling, but only 25 differ by more than case or accents and
  every one of those is "&" against "and" — Marks & Spencer, Tom & Jerry. No merges.
- **Timelines with impossible spans** (Elizabeth II from 683, Aristotle to 1978): correct.
  A timeline is every row that mentions the entity, not a lifespan.

## State after the round

87,193 rows / 3,078 year pages / 8,756 pages / 4,665 timelines.
`verify.py` 0 failures · `--live` 3,428 revisions byte-identical · `coverage` 51/51 ·
`famous` 333/333 · `surface` clean · **`montage` clean (new)** · `integrity` clean ·
`audit` clean (282,866 bullets, 377,520 links).
