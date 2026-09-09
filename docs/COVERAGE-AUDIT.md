# What was missing from the record, and what is still missing

Written 2026-09-07, written after asking what else could be improved and whether we were
missing important events. The answer to the second half turned out to be yes, badly, and
in a way that no amount of spot-checking would have caught: the pipeline was selecting
*against* the most important event of each year. That is fixed and live. This file records
how it was found, what the numbers were, and the seams that are still unharvested.

## The test that found it

Everything in this project is verified for *provenance* — `verify.py` proves that every
published sentence appears verbatim in the revision it cites, and it has never failed.
What nothing tested was *coverage*: whether the things a person would actually look up are
present at all. Provenance and coverage are different properties, and a dataset can be
perfect on the first while being useless on the second.

The test was crude and took two minutes to write. Take thirty events that any person would
name as the defining event of its year — the fall of Constantinople, D-Day, the Moon
landing, Pearl Harbor, the September 11 attacks — and check whether the exact sentence
describing that event is in the record for that year.

Five of the first six failed.

- **1453** had 24 entries, every one of them a birth or a death. The Fall of
  Constantinople was not in the record at all.
- **1944** had 153 events and no landing on 6 June. It had the bombing of the Normandy gun
  batteries the week before, and a weather forecast.
- **2001** had 125 events and no September 11 attacks. It had the invasion of Afghanistan
  that answered them, and a speech about them.
- **1941** had 144 events and no attack on Pearl Harbor. It had a Japanese spy arriving in
  Honolulu, and the carrier force leaving Hitokapu Bay.
- **1969** had 144 events and no Moon landing. It had Apollo 9, Apollo 10, and the Tour de
  France result for 20 July.

The failure was not random, which is what made it serious. In each case the *page summary*
named the event correctly, because the summary is quoted from Wikipedia's own lead
paragraph. So the 1969 page opened by saying "Apollo 11 lands the first humans on the
Moon" and then listed a bicycle race under 20 July. A reader would notice; a machine
consuming the dated rows would not.

## Four causes, all of them ours

**1. The ranking function scored length as untidiness.** Each themed section of a year page
publishes its 24 highest-weighted entries, and the weight included `length_fit`, which paid
1.0 for a sentence of 70-260 characters and 0.35 for anything over 400. But on a Wikipedia
year article, length tracks importance: the encyclopedia spends its longest bullet on the
biggest thing that happened. D-Day is 416 characters. It was scored at 0.35 and lost its
place to shorter, lesser entries in the same section. The penalty now applies only to
stubs under 70 characters.

**2. A 600-character ceiling in the extractor.** Any cleaned sentence longer than 600
characters was dropped outright, before ranking. The September 11 attacks entry is 631
characters. The ceiling exists to catch a runaway parse, which is a real risk, so it is
still there — at 1,200.

**3. Articles that file events under place headings lost all of them.** The extractor
accepts a fixed set of top-level headings (`Events`, `Births`, `Deaths`, ...) and falls
back to accepting everything only when none of those are present. 1453 has `Births` and
`Deaths` and files its events under `Global events`, `Africa`, `Asia`, `Europe`. The
standard branch was taken, the place headings were not in it, and every event on the page
was discarded while the births and deaths came through. 146 year articles are written that
way. The fallback now also triggers when the standard headings are present but none of
them is event-bearing.

**4. Wikipedia is splitting year articles, and we followed the wrong half.** 1453 has been
rewritten as prose with the dated list moved to a companion article called `1453 events`.
We harvested the prose article, which has no dated list at all. `harvest.py` now detects
the `{{For|...events...|X}}` pointer and, when the article it is on carries no event
bullets of its own, harvests the companion instead — which is a complete year article in
the standard shape, Events, Births and Deaths together. Only 1453 is split this way today.
It is a canary: the whole pipeline assumes bullets, and this is how we lose a year silently
when the encyclopedia reformats it.

**5. Date inheritance broke on qualified date headers.** Where several things happen on one
day, Wikipedia writes a parent bullet holding the date and hangs the events underneath it.
The parent was only recognised when it was a bare date. Through the war years it is
written `December 7 (December 8 - 3:18 a.m., Japan Standard Time) - WWII:`, which did not
match, so its children inherited no day. The attack on Pearl Harbor was therefore filed
under "December" with no day, and never appeared on the December 7 calendar page — the
single most-visited day-page there could be. 295 such headers carried 795 events that had
lost their day; 319 entries gained a date in the rebuild.

## Where it stands now

The same thirty-event test passes 30/30. The full chain was re-run and re-verified:
**86,322 entries across 2,960 years, 0 verification failures, all 2,960 cited revisions
re-downloaded from Wikipedia and confirmed byte-identical**, rendered audit clean at 6,983
pages. Deployed.

One correction went out with it. The site described its contents as "85,753 dated
historical events". 42% of those rows are birth and death entries, which the source
articles list separately. `/data` now states the split: 86,322 entries, of which 49,685 are
events and 36,637 record a birth or a death.

## What is still missing — the seams we do not harvest

These are measured, not guessed.

**Month articles.** Wikipedia has a separate article for many individual months, and the
year article links to it (`{{Main|June 1944}}`). We have never read one. They are roughly
twice as dense as the month section of the year page:

| | month article | year page section |
|---|---|---|
| June 1944 | 188 bullets | 105 |
| July 1969 | 154 bullets | 58 |

895 distinct month articles are referenced from 80 year articles. They exist mainly for
1940-1980. Harvesting them is the same pipeline pointed at different titles, and it is the
largest single volume lever available.

**Country-year articles.** This is the more important one, because it fixes a bias rather
than just adding rows. Counting country and region mentions across the 49,685 event rows:

| | mentions | | mentions |
|---|---|---|---|
| Britain / England | 6,444 | Africa (entire continent) | 2,267 |
| Italy / Rome | 4,814 | Latin America | 1,455 |
| United States | 4,189 | South-East Asia | 1,179 |
| France | 3,698 | Korea | 570 |

That is English Wikipedia's year articles, inherited whole. But Wikipedia also publishes
`1969 in Japan` (110 bullets), `2001 in India` (151), `1969 in Brazil` (85), `1969 in
China` (64) — dense, dated, individually cited, and largely disjoint from what the year
article carries. Twenty countries across a century and a half is on the order of a hundred
thousand additional rows, weighted exactly where we are thin. It also gives every row a
country, which is a column the dataset does not currently have and which is the first thing
anyone filtering history would reach for.

**Thematic year articles.** `1969 in film` alone is 479 bullets. `1969 in science` is 64.
These are per-domain and would let the topic pages stand on real depth rather than on the
twelve labels a classifier assigns.

**A stated limitations section.** The bias table above belongs on `/data`, in prose. The
product's whole claim is that it can be checked; publishing the shape of its own blind
spots is consistent with that and costs nothing.

## The lesson worth keeping

Provenance testing cannot find a missing row. `verify.py` will pass forever on a dataset
that omits every important event, because everything it *does* contain is correctly cited.
Coverage needs its own test, and the test is a fixed list of things a person would look up,
run on every build. That list should be checked in and grown, and a build that drops one
should fail the way an audit failure does.

---

# Round two — 8 September 2026

The first audit tested six famous events, five of which were missing. Six cases cannot
tell you how big a hole is, so this round built the wide test first and fixed what it
found. `pipeline/famous.py` holds **264 cases** — 249 years and 15 calendar days —
chosen to spread across regions and eras rather than to sample the corpus, because a
test drawn only from Anglo-American history would never see this corpus's measured
Anglocentric bias.

First run: **251/265 present (94.7%)**. Nine of those failures were the test's own bug
(see "The BCE trap" below). Five were real, and each one was a class, not an incident.

## What was actually wrong

**1. The section allow-list was discarding 6,700 source bullets.**
`extract.py` read list items only under nine approved headings (Events, Births, Deaths,
By place, …), with a fallback to "everything not apparatus" when none of them appeared.
The fallback almost never fired, because the strict branch triggered on *any* approved
heading — and "Significant people" is one. The "750s BC" article carries Significant
people, so its **Events and trends** section, which holds the founding of Rome, was
thrown away and 753 BC ended up with no page at all. Measured over all 5,026 harvested
articles the allow-list was silently dropping 6,137 bullets under "Events and trends",
2,395 under "Inventions, discoveries, introductions", 200 under "Architecture", and the
month-range headings ("January – March") some year articles use instead of "Events".

The fix inverts the rule: accept every top-level section that is not apparatus
(references, sources, further reading) or invention (fiction, legend, popular culture,
predicted events). An allow-list of heading names cannot be completed by thinking,
because Wikipedia keeps inventing headings. A deny-list can: there are only **62
distinct top-level headings** in the whole harvest.

**2. Colon-indented bullets were invisible.** Wikipedia writes nesting two ways. The
Roman-republic years use the colon form — `*[[Second Punic War]]` with `:* Hannibal sets
out with 40,000 men and 50 elephants…` underneath — and the extractor only read `*`
lines. 218 BC, the year Hannibal crossed the Alps, was published as a one-line page
about a siege in Asia Minor. 112 lines across 30 articles.

**3. A day span was filed only on its first day.** The source writes
`October 24–29 – Wall Street Crash of 1929`, so the entry carried October 24 and
**/on/october-29 — Black Tuesday, the date the crash is remembered by — had no crash on
it.** `dates.py` now files a spanned entry on every day it covers, capped at 14 days,
and keeps the printed span in the sentence so the reader sees which range they landed
inside. 938 entries are written as spans; date-page entries went 54,415 → 57,846.

**4. Award tables were let in and had to be shut back out.** Inverting the section rule
admitted 421 Nobel prize lines, which read "Physics – James Watson Cronin, Val Logsdon
Fitch" — true, sourced, and meaningless once our own section taxonomy replaces the
heading that said which prize it was. Every bullet here has to stand alone, so award
sections are now named in the deny-list. This is the argument *for* a deny-list working
in both directions: it is a list of judgements about what the record is, and it can be
corrected.

**5. The BCE trap, which was the test's bug and not the site's.** Pages are keyed in
astronomical numbering: 776 BC is `-775`, 44 BC is `-43`. Writing the BC year with a
minus sign in front tests the year before the one you meant, and nine cases failed that
way on the first run. It is written at the top of `famous.py` now.

## Result

| | before | after |
|---|---|---|
| famous-event sweep | 251/265 (94.7%) | **264/264 (100%)** |
| year pages | 2,960 | **3,078** |
| published entries | 86,322 | 86,691 |
| calendar-date entries | 54,415 | **57,846** |
| total pages | 6,983 | **7,136** |

Extraction yield — claims kept per readable source line, on the 1,231 years whose source
article is the year's own — now has a **median of 1.0 and a worst case of 0.72**. Before
the fix, whole sections read as zero. That ratio is the cheap standing check for the next
extraction bug: it needs no list of famous events and no judgement about what matters.

## Known absence, on the source and not on us

2560 BC has no page. Wikipedia has no article for the year, and the 26th century BC
article dates the Great Pyramid only as a span — "c. 2551–2526 BC: Reign of Khufu". A
span is not a year, so the line is correctly dropped. It is recorded in `famous.py` as
`EXPECTED_ABSENT` so nobody re-opens it.

## The second half of the same audit: people

Everything above tests events. A year page also carries a Births list and a Deaths list,
and testing events cannot see that those are wrong. They were wrong in two different ways,
and the wide test now covers both (`PEOPLE` in `famous.py`, 68 cases).

**Ranked as if fame were genericness.** Entries are scored by the size of the Wikipedia
articles they link, discounted by how many other year articles link the same entity —
that discount is what stops "Spain" from outranking the Moon landing. Applied to a person
it is exactly backwards: being linked from forty year articles is what fame *is*. Measured
over 62 people anyone could name, **only 15 were on the right list of their own year**.
1879 published Grace Coolidge, Georgia Ann Robinson and Franz von Papen, and left out
Albert Einstein. Shakespeare, Newton, Mandela, Mozart, Elvis and Picasso were missing the
same way.

A birth or death line has a fixed shape — "March 14 – Albert Einstein, German-born
physicist, Nobel Prize laureate (d. 1955)" — so its subject is simply the first link that
is not a date, and there is nothing to guess. Births and deaths are now ranked on that
person's own article, undiscounted. Events keep the discounted ranking, which is measured
good.

**And from 1977 there were no deaths at all.** Not ranked badly — absent. Up to 1976 the
year article carries its own Deaths section; from 1977 it says `{{Main|Deaths in 1977}}`
and the list is a separate article, which we had never harvested. Forty-nine consecutive
year pages had an empty Deaths list and nothing in the pipeline could notice, because
verification proves what is published and the events sweep does not look at people.

`pipeline/deaths.py` harvests those 566 articles — "Deaths in 1977" and "Deaths in 1978"
as one page per year, and from 1979 twelve pages a year, "Deaths in January 1979" — parses
both of their layouts, and merges **214,783 deaths** into the years they belong to. Each
claim carries its own source, so the bullet cites the revision it actually came from and
the page footer names every article it quotes. `verify.py` re-downloads those revisions
too: the guarantee is unchanged, it just has more revisions to hold.

That is why 2011 now has Steve Jobs on it, 2013 has Nelson Mandela and Hugo Chávez, 1977
has Elvis Presley and Steve Biko, and 2020 has Kobe Bryant, Ruth Bader Ginsburg, Diego
Maradona and Chadwick Boseman.

| | before | after |
|---|---|---|
| famous events + people + days | 251/265 events only | **333/333** |
| people on the right list | 15/62 | **68/68** |
| years with no deaths at all | 49 (1977–2025) | **0** |
| sourced claims held | 162,388 | **377,171** |
| published entries | 86,322 | 87,253 |
| pages | 6,983 | **7,205** |

The general lesson is the one from round one, sharpened: **a test can only find what it
looks at.** Round one widened from 6 events to 264 and still saw none of this, because
every case in it was an event. When a record has more than one kind of row, the sweep needs
a case of each kind, and the cheapest way to find the next hole is to ask which kind of row
no test currently names.

## The other known absence: births after 1981

Thirty-four year pages between 1981 and 2022 show no births, and that one is the source's.
Those year articles carry no Births section at all — they point at "Category:1990 births"
instead, and a category is a list of article titles, not a sentence anybody wrote. There is
nothing to quote and nothing to cite, so nothing is published. It is listed in `famous.py`
as `BIRTHS_NOT_PUBLISHED_UPSTREAM` so the next person to notice it can see in ten seconds
that it was looked at. The deaths of the same years were recoverable only because Wikipedia
moved them into an article rather than into a category.

# Round three — 8 September 2026

The instruction that followed was to keep running checks, on the grounds that the work was
not done. That turned out to be correct. Round two had ended with 333/333 on `famous.py`, and that
number was true — but `famous.py` and `coverage.py` between them look at **two of the
site's seven page kinds**, and one class of defect is invisible to every test we own,
including `verify.py`, by construction.

## The class verification cannot see

`verify.py` proves a published sentence is the cleaned form of a stored wikitext line, and
that the line is in the cited revision. It re-derives the sentence **with the same cleaner
that produced it**. So when the cleaner deletes a word, the deletion is reproduced exactly
and the check passes. A sentence can be missing its subject and be perfectly verified.

That is what was happening. Wikipedia writes a named ship as a template — `{{RMS|Olympic}}`,
`{{HMS|Beagle}}`, `{{USS|Nautilus|SSN-571}}` — and the cleaner dropped any template it did
not recognise. It only refused to publish the line if the dropped template contained three
words or more, and a ship's name is one. So the site shipped, for three years, lines like:

- 1908: *"December 16 – Construction begins on the , at the Harland and Wolff Shipyard"* —
  that blank is the RMS Olympic.
- 1820: *"May 11 – , the ship that will later take young Charles Darwin on his scientific
  voyage, is launched at Woolwich Dockyard"* — HMS Beagle.
- 1955: *"January 17 – , the first nuclear-powered submarine, puts to sea"* — USS Nautilus.
- 1911: three lines about a ship nobody could name — RMS Olympic again.

The guard that was supposed to catch this ("a line that now opens on a comma has lost its
subject") only looked at the first character of the line, and these lines open on a date.

**Fixes.** Ship templates now render (`SHIP_PREFIXES` + `render_ship` in `extract.py`),
along with `{{cvt}}`, `{{frac}}`, `{{chem}}`, `{{overbar}}`, `{{langx}}`, `{{M|w}}` (the
magnitude label in every modern earthquake line) and `{{reign}}`. More importantly the rule
is inverted: an unknown template that renders to nothing now makes the line unpublishable
**whatever its length**, and only an explicit list of citation and maintenance families
(`droppable()`) is allowed to vanish. And the fragment guard is applied a second time with
the printed date removed, so "May 11 – ," fails it. Cost of the strict rule, measured
before shipping: 106 rows out of 87,253, and the list of what caused those 106 was itself
the map of every remaining template that was eating content.

## Four more, found by asking which page kind no test names

- **The 20th century page had three highlights and the 21st had none**, while every other
  century had eight — and every decade page from the 1900s to the 2020s listed its years
  with nothing underneath them. `build.py` returned the three lead entries of a year only
  when the year had *no* montage-caption summary of its own, and every year from 1900 on
  has one. The decade and century pages are built from exactly that field. Fixed: the
  field is always populated, and when a caption exists it is used to *choose* which three
  published entries stand for the year, so the 1960s page now leads 1969 with Apollo 11
  instead of two John Lennon bed-ins.
- **613 calendar-page rows began mid-sentence**, e.g. `/on/august-28` carrying
  *"30 – Second Battle of Bull Run"*. A day page strips the day it is about off the front
  of the sentence, and on the first day of a printed range that cut the range in half.
  Fixed in `dates.py`: a range is never cut, whether or not the span is short enough to
  file on every day it covers.
- **Thirteen year articles had a `/timeline` page of their own** — `/timeline/ad-4`,
  `/timeline/ad-757` — because the year filter matched "757 AD" but not "AD 757".
- **Nobody famous had a timeline.** The floor was eight distinct years and most people
  appear in three to seven, so van Gogh, the Berlin Wall, Anne Frank, Jane Austen and
  Gutenberg all missed. The floor is six now, capped at 4,700 pages, which is what the
  Cloudflare Pages 20,000-file ceiling allows (each entity costs two files). 3,114 →
  **4,670 timelines**.

## The test that should have existed: `pipeline/surface.py`

Every defect above sat on a page kind no test named. `surface.py` names all seven:

- **KIND** — 69 cases across topic hubs, decades, centuries and entity timelines.
- **SHAPE** — every published sentence on every page kind: no wiki markup, no opening on
  punctuation, none opening on punctuation *after* its printed date (the ship class), none
  opening on a bare day number (the span class), nothing shorter than a clause. 283,000
  rows.
- **TRACE** — every row on a cross-cut page must exist on its own year page with the same
  revision id. A cross-cut is a re-filing; a row in one and not the other is invented.
  196,038 rows checked.
- **FILL** — no century without highlights, no decade whose years show nothing, no empty
  calendar day.
- **BUDGET** — the file count against the Cloudflare 20,000 ceiling, so that fails here
  rather than at the deploy.

## Result

87,279 published entries (was 87,253) across 3,078 year pages; **8,762 pages**, 17,933
files; **4,670 entity timelines** (was 3,114). `verify.py --live` 0 failures with all
3,428 cited revisions re-downloaded byte-identical; `coverage.py` 51/51; `famous.py`
333/333; `surface.py` clean; `audit.py` clean on 283,282 rendered bullets and 377,957
internal links; every page but the internal not-found reachable from the home page.

## The lesson

Round two's lesson was that a test only finds what it looks at. This round's is narrower
and worse: **a test that re-derives the output with the same code that produced it cannot
find a bug in that code.** Verification proves consistency, not correctness. The only
things that find a deletion are a rule about the *shape* a sentence must have, and a list
of what is allowed to disappear.

# Round four — 8 September 2026, second opinion

Same day, next round. An Azure endpoint for `a second, unrelated frontier model` was wired in with the
instruction to use it but assume it is wrong until proved otherwise. Six review angles
(the cleaner, the ranking, the three cross-cut builders, the post-build, 260 sampled
published rows with their wikitext, and the Next.js pages), 60 claims, **13 real**. The
full claim-by-claim verdict table, including the measurement that killed each false one,
is in `LUNA-REVIEW-2026-09-08.md`.

The two that mattered:

- **162 published sentences were truncated in the middle of themselves.** When a cleaned
  line ended up with more `(` than `)` — because the closing half was inside a template or
  a reference the cleaner removed — the old code cut the sentence at the bracket and
  published the stump: *"…on his way toward Italy, in order to assert his claim to become
  King of Naples"* is where 1494's entry stopped. It now marks the line unpublishable.
  This is the same family as the ship bug from round three, and it is invisible for the
  same reason: `verify.py` re-derives the published text with the same cleaner.
- **1,005 of 4,670 entity timelines were out of order**, because rows inside a year were
  sorted on the date *string* — "December 1" sorts before "January 1". Michael Jackson's
  2009 read "June 25, June 25, March 5". Sorting is now on (month, day).

Also fixed: 61 rows that were the colon-terminated heading above a nested list rather than
a statement; 17 calendar rows filed on days the event never touched, because "November 5 –
11,000 scientists publish a study" parsed as the range 5–11; 4 rows carrying a raw
bracketed URL; the one page where astronomical year 0 sat in an AD decade and a BC century
at the same time; `20th Century Fox` being scored as a date rather than a subject; and two
structured-data/attribution errors on the pages themselves.

`surface.py` grew six new tripwires, one per class.

**Result:** 87,122 published entries (the drop from 87,279 is the 162 truncated rows and
the 61 headings leaving), 8,752 pages, 4,660 timelines. verify --live 0 failures across
3,428 revisions re-downloaded byte-identical; coverage 51/51; famous 333/333; surface
clean; audit clean on 282,570 rendered bullets and 377,300 links.

**The lesson.** A second model is a hypothesis generator, not a reviewer: it cannot tell
the difference between a defect it found and one it invented, and it presents both
identically. Two thirds of what it said was wrong — including its single largest finding,
which was really the model not knowing that nested bullets inherit their parent's date.
The value was in the third that was right, and the only way to find that third is to
measure every claim against the corpus before touching anything.
