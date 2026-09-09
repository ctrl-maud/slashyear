# Round fifteen — the one decision that is ours

**The class: every gate on this site tests whether we copied Wikipedia faithfully. The
section heading is not copied from anywhere, and nothing had ever tested it.**

`classify.py` is the only place a language model touches the pipeline. It does not write
words; it decides which themed section each sentence files under. The file's own comment
said that this cannot matter -- "a mis-sorted bullet is a filing error, not a factual
one" -- which is the same reasoning round thirteen already disproved for the Deaths
heading, where 910 rows were published as deaths that were accessions. A heading is a
claim about the row underneath it. And `cross.py` calls the topic axis "the half of the
site that is genuinely ours": 12 topic hubs and 302 topic-century pages are built out of
that decision and nothing else.

## Finding the ground truth

The problem with testing a filing decision is that no source states the answer, so there
is nothing to join on. Except that for part of the corpus there is. Wikipedia's year
articles file part of their Events section under headings the editors chose:

```
== Events ==
=== By topic ===
==== Religion ====
==== Literature ====
==== Astronomy ====
```

2,407 of our claims sit under one of those. It is editor-written, it is about the row
rather than about an entity in it, and `classify.py` had never read it. That makes it a
held-out test set that we did not write -- the round twelve lesson, applied again.

**Result on the 1,921 rows whose heading has one unambiguous reading: we agreed with the
editors on 1,457 and disagreed on 464 (24%).**

Hand-checking 24 of the disagreements: 14 were plainly our error, 4 arguable, 6 were the
instrument being wrong (an erupting volcano filed under Climate & Environment when the
article files it under Science is a difference of taste, not a defect). So roughly 270
genuine misfilings in a 1,921-row slice, about one row in seven.

Two failure modes account for most of them.

**The work, not its plot.** The classifier embeds the sentence, so it responds to what a
work of art depicts rather than to the fact that the work was made:

| published as | sentence |
|---|---|
| Crime & Justice | Sophocles' play *Electra* is performed. |
| Crime & Justice | Aristophanes' play *Plutus* is performed. |
| Crime & Justice | A bronze statue called Dying Gallic trumpeter is made. |
| Religion & Belief | Aeschylus writes *Seven Against Thebes* and wins the Dionysia. |
| Religion & Belief | Kamo no Chōmei, a Japanese poet and essayist, writes the Hōjōki. |

**The building, not the transaction.** A sentence that names a religious institution went
to Religion & Belief whatever it was reporting:

| published as | sentence |
|---|---|
| Religion & Belief | The Sienese bankers of the Gran Tavola become the main financiers of the Papacy. |
| Religion & Belief | Henry II of England is using the safes of the Temple Church, under guard of the Templars. |
| Exploration & Expansion | The first evidence of the Knights Templar being used as cashiers by Henry III. |
| Technology & Infrastructure | John, King of England, permits Jews to live freely in England and Normandy. |
| Disasters & Accidents | The Muslims expel 300 Christians from Jerusalem. |

## The instrument that failed, and why that is in this file

The first ground truth built was **not** the headings: it was the Wikipedia category graph
of every entity our rows link (`categories.py`, 80,847 titles, 27 MB). It reported 4,094
disagreements — three times the heading test — and it was wrong. Hand-checking 22 of them
found our filing right or defensible in most:

- *Sparta attacks Corcyra* — Corcyra is in "Corinthian colonies", so the instrument
  demanded Exploration & Expansion.
- *The Treaty of Jaffa is signed* — Jaffa is in "Military history of Jaffa", so it
  demanded Conflict & Security over Geopolitics.
- *A French ship is shipwrecked on the Isle of Wight on the first Sunday after Easter* —
  Easter is a Christian festival, so it demanded Religion & Belief over Disasters.

An entity's categories describe that entity's whole existence, not what it is doing in
this sentence. Restricting the vote to links that are neither people nor places lifted
agreement from 67.1% to 79.7% and it still could not be gated. It stays in `theming.py` as
a reported diagnostic, and it is the reason the gate is the heading test alone: **run
controls on a discriminator before letting it charge anyone.** That is the same lesson
`lifedates.py` learned when 35% of its findings turned out to be the Julian calendar.

## The fix

`classify.py` now decides in four tiers instead of two:

```
Deaths            if the row's own dated clause reports a death   (round 13)
source heading    if the article states the topic                 (round 15)
priority rule     work-creation, or finance in a religious frame   (round 15)
lexical rule      as before, tie-broken by the embedding
embedding argmax  otherwise
```

The second tier is the important one and it is not a heuristic: where Wikipedia says what
the topic is, guessing it is strictly worse than reading it, and the section stops being
our opinion and becomes a sourced fact like everything else on the page. 1,921 rows are
now filed by their own article.

The third tier generalises the two measured failure modes to the whole corpus, where no
heading exists:

- creation verb + a work noun, or + a linked title Wikipedia categorises as a work
  ("Plays by Aeschylus", "Lost sculptures") → Culture & Society, with scripture and
  monastic authorship excluded so that a sacred text being compiled stays Religion;
- bankers, financiers, moneylenders, coinage, letters of credit → Economy & Finance.

488 rows were decided by a priority rule.

## Measuring the fix without measuring it against itself

Once the classifier reads the headings, testing it against the headings is circular. So
`theming.py --pure` re-derives every theme from the cached similarity matrix and the rules
while **ignoring** the heading, which keeps the gate a held-out test of the guessing part:

| | heading agreement |
|---|---|
| before | 1,457 / 1,921 = **75.8%** |
| after, pure (heading held out) | 1,490 / 1,921 = **77.6%** |
| after, as shipped | 1,921 / 1,921 = **100%** (1,921 rows now sourced) |

The independent category diagnostic moved 79.7% → 80.3% over 6,699 rows, which is weak
confirmation from a weak instrument, but it moved the right way.

`theming.py` is now a gate with a baseline ratchet (`theming.baseline.json`), so a future
change to the prototypes, the rules or the extractor cannot quietly un-file these rows.

## What shipped

- `pipeline/theming.py` — the gate (HEADING, gated; CATEGORY, diagnostic).
- `pipeline/categories.py` — Wikipedia's categories for all 80,847 linked entities,
  cached in `data/categories.json`; also feeds the work-detection rule.
- `pipeline/classify.py` — four-tier theming, `theme_from` recorded on every claim.
- `pipeline/entities.py` — cap raised 4,700 → 4,900 so that everything clearing the
  six-year floor is published (the reshuffle had pushed `/timeline/anne-frank` out).

Live: 8,959 pages, 86,902 bullets, 4,868 timelines, 18,326 files (cap 20,000).
verify 86,902/0 failures, coverage 51/51, famous 333/333, surface clean, integrity clean
(287,009 bullets), lifedates within baseline, audit clean, theming 0 heading disagreements.

## The lesson

Every test this pipeline had was a test of fidelity: does the published sentence match the
source. Fidelity tests are blind to any decision the source did not make, and there was
exactly one of those — and it turned out the source HAD made it, for part of the corpus,
in a heading nobody had read. **When a system has one component that answers a question
its source never answers, look again: the source usually answers it somewhere, for some
of the data, and that slice is the test set you did not have to write.**
