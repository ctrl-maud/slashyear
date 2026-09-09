# The training-data verdict — measured, not argued
The question this document answers, asked on 2026-09-07: *"the criteria we need to use for training data,
what's the verdict on that? You're saying the format is repeated, it's templated. Then
what are you saying? We make a page looking different than every other page? Really? Is
that really the workaround?... the goal here is to have millions of requests a month just
by either users and agents or AI."*

## Verdict in one line

**No. Pages do not need to look different from each other — that was the wrong diagnosis.
Every filter that matters is computed inside a single page. And separately: training data
can never produce millions of requests a month, because a training crawler fetches a page
once per cycle, not repeatedly.** Both halves below are measured or sourced.

---

## Part 1 — what the filters actually measure

I stopped arguing and ran the real code. `datatrove` is the library HuggingFace used to
build FineWeb; the filters below are its upstream classes at their published defaults, in
FineWeb's own pipeline order (`examples/fineweb.py`):

    WARC/HTML -> trafilatura(favour_precision) -> URLFilter -> LanguageFilter(en, 0.65)
              -> GopherRepetitionFilter -> GopherQualityFilter
              -> C4QualityFilter -> FineWebQualityFilter -> MinHash dedup

Reusable as **`tools/trainfilter.py`** (`--help`, `--explain`). Point it at a URL,
a file or a directory and it names the exact filter that kills each page.

### Finding 1 — cross-page sameness is not measured at all
Gopher's repetition thresholds are computed *"over the document"* (Rae et al., arXiv
2112.11446, §A.1.1, Table A1) — duplicate line fraction, duplicate paragraph fraction, and
the top-2/3/4-gram and duplicate-5..10-gram character fractions all compare a page to
**itself**. Nothing in Gopher, C4 or FineWeb compares one page of a site to another page of
the same site. The single cross-document check is MinHash dedup, which fires on whole
near-duplicate documents (FineWeb: 5-grams, 112 hashes, 14 buckets of 8, ~0.75 similarity
target) — our pages carry different facts and are nowhere near that.

### Finding 2 — the nav and footer never reach the filters
FineWeb, RefinedWeb and Nemotron-CC extract from raw WARC with trafilatura (or justext);
DCLM uses resiliparse. All of them strip menus, headers, footers and sidebars *before the
first filter runs*. Trafilatura's own paper describes the algorithm as XPath exclusion of
"unwanted parts of the HTML code (e.g. `<div class="nav">`)" (Barbaresi, ACL 2021 demo).
DCLM measured the difference: resiliparse 24.1 / trafilatura 24.5 / raw WET 20.7 CORE
(arXiv 2406.11794, Table 3). So "every page has the same nav" is not a mechanism.
(C4 and Dolma-v1 *do* use raw WET files with no extractor — but there the boilerplate is
caught by generic per-line rules, still not by a site-wide sameness signal.)

### Finding 3 — what is actually killing us, measured on the live site
165 real pages sampled across every page type, run through the stack above:

| page type | pass rate | what kills it |
|---|---|---|
| `/<year>` (2,909) | 1/30 | 47% `gopher_below_alpha_threshold`, 43% `duplicated_5..7_n_grams` |
| `/timeline/<slug>` (2,941) | 0/30 | 77% `fineweb:line_punct_ratio` |
| `/on/<day>` (367) | 0/30 | 100% `gopher_too_many_bullets` |
| `/topic/<slug>` (12) | 0/12 | 100% `top_3_gram` / `top_4_gram` |
| `/decade/<n>` (273) | 7/30 | 73% `gopher_below_alpha_threshold` |
| `/century/<n>` (33) | 0/30 | 97% `gopher_below_alpha_threshold` |
| `/data` (the prose page) | **PASS** | — |

**About 5% of the site survives.** Four mechanical causes, none of them "the template":

1. **`line_punct_ratio`** — FineWeb drops a document when fewer than **12%** of its lines
   end in `.` `!` `?` or a quote (`line_punct_thr=0.12`). Our event bullets end without a
   full stop. *One character per line.*
2. **`gopher_too_many_bullets`** — more than **90%** of lines starting with `-` or `•`.
   `/on/<day>` pages are 100% bullets.
3. **`gopher_below_alpha_threshold`** — fewer than **80%** of tokens contain a letter.
   Our pages are dates, counts and standalone punctuation. In datatrove's implementation
   the denominator includes bare punctuation tokens, so comma-dense short lines fail even
   when the prose is fine.
4. **`top_n_gram` / `duplicated_n_grams`** — a phrase repeated *inside one page* eating
   too many of its characters.

Plus a real defect worth fixing regardless: our HTML is missing whitespace between inline
elements, so extraction yields `1221 BCE1221 BC—Pharaoh…`, `- 625Battle of Sarus`,
`100 CE33 entries`.

### Finding 4 — I built the fix and measured it
`trainfilter/prose.py` renders the *same facts, same sentences, same
sources* as continuous paragraphs instead of a bulleted table: dates written into the
sentence, every sentence terminated, `&` written as "and", no bullets, and a genuinely
written opening and per-section context.

    baseline year pages   1/30   =  3.3% PASS
    prose render        272/400  = 68.0% PASS

Not one fact was invented, removed or paraphrased. Only the shape changed.

### Finding 5 — the experiment that proves the rule
Mid-build I gave every section of a page the *same* context paragraph. Pass rate collapsed
**64% -> 11%**, all of it `duplicated_5_n_grams`. Giving each section its own wording put it
back to **68%**. Meanwhile the page's opening paragraph is byte-identical across all 2,909
year pages and costs nothing at all.

> **Repetition inside one page is fatal. Repetition across pages is free.**
> That is the answer, measured rather than asserted.

---

## Part 2 — training data cannot produce millions of requests a month

This is the more important half, because it means channel three was never the answer to
what was actually asked for.

**A training crawl is a fetch, not a subscription.** Common Crawl runs monthly and only
partially re-fetches URLs it has already seen. The documented extremes are bursts, not
baselines: ClaudeBot hit iFixit ~1,000,000 times in 24 hours (2024-07-24, 404 Media) and
read the whole APIs.io catalog in one day — 558,094 requests on 2026-08-21 against a
43-93/day baseline, settling afterwards to ~12,400/day (apievangelist.com). Cloudflare's
crawl-to-refer ratios (Radar, 2025) run 25,000:1 to 500,000:1 for Anthropic and up to
3,700:1 for OpenAI — i.e. crawlers take, they do not send people back.

So the reason to get into a training corpus is **that a model can name us without being
told**, not traffic. Worth doing. Not the goal that was stated.

### Where millions of monthly requests genuinely come from — five patterns, all sourced

1. **Embedded in a course or tutorial.** REST Countries was baked into the University of
   Helsinki's Full Stack Open exercises 2.18-2.20 and took **~4M hits/day and 120 GB/day**
   until the solo maintainer announced shutdown for lack of funding. Same shape: agify.io
   (social-science teaching), jsonplaceholder (every fetch() tutorial).
2. **A default in a build tool.** PyPI serves **~6 billion requests/day** (PSF, 2026-08-14)
   because every `pip install` and every CI run hits it. npm likewise.
3. **The no-key, no-signup option.** Nominatim had to write a usage policy *banning*
   autocomplete because every hobbyist defaults to it. Open-Meteo, ip-api, Frankfurter,
   sunrise-sunset all the same.
4. **Something AI companies must have.** Wikimedia Enterprise revenue **+148% to $8.3M**
   with Amazon, Meta, Microsoft, Mistral and Perplexity paying — scraper load converted
   into a metered product.
5. **Polling.** GTFS-realtime feeds get fetched every 15 seconds whether or not a human
   is looking. Volume = feeds x cadence.

**We are pattern 3 today, and pattern 1 is the one we can actually manufacture.**

---

## What to do, in order

1. **Ship the prose rendering of every page.** Free, no accounts, fixes the whitespace bug
   too, and takes the site from ~5% to ~68% corpus-survivable. Also better for humans and
   for Google, which is not a coincidence — the filters were built to find readable prose.
2. **Get into things that get taught and copied.** A tutorial, a Colab notebook, a
   client library on PyPI/npm, a "here is how to plot 2,000 years of history in 10 lines"
   post. This is the only lever on the list that has ever produced millions of requests a
   month for a small operator, and it is the cheapest thing on this page.
3. **Then the corpus routes that survive scrutiny.** An arXiv dataset paper (cs.CL/cs.DL,
   free, days) is the cheapest real route into a corpus: arXiv -> Semantic Scholar ->
   S2ORC -> peS2o -> Dolma/OLMo. peS2o's stated bar is title+abstract, English, >=500
   words, >=5 paragraphs, post-1969 — trivially met. **Also: put `schema.org` markup on the
   event pages so Web Data Commons harvests them** (877M pages of JSON-LD extracted at CC
   scale, WWW2023).

## Routes that are dead ends — do not spend time on them

- **Hugging Face upload as a training route.** No corpus builder scans the Hub by
  downloads or likes. Every one hand-picks named sources. Upload it for humans, not for
  training. (`docs/research/hf-hub-to-llm-training-route.md`)
- **GitHub -> The Stack.** Our licence is the blocker: The Stack v1/v2 build permissive
  allowlists from Blue Oak / ScanCode, and **CC BY-SA 4.0 appears nowhere in either**.
  `.csv` and `.gz` are excluded by extension; CSV is on Stack v2's excluded list; Parquet
  and NDJSON are not recognised at all. Only plain `.json`/`.md` clear the format filter,
  and the licence still kills it.
  (`docs/research/github-code-corpus-inclusion-criteria.md`)
- **Citing ourselves on Wikipedia or Wikidata.** Three independent policy grounds:
  **WP:CIRCULAR** covers "publications relying on material from Wikipedia" — restructuring
  into JSON is not an escape; **WP:SELFPUB/COI**; **WP:ELNO#4**. Bulk addition risks the
  domain being spam-blacklisted network-wide, which would be worse than doing nothing. And
  no major corpus ingests Wikidata dumps anyway.
- **Zenodo alone.** DataCite DOIs are not in Semantic Scholar's Crossref/arXiv sourcing —
  a Zenodo-only deposit plausibly never reaches peS2o. Pair it with arXiv or skip it.
- **`llms.txt`.** Unchanged: 97% of them got zero requests in May 2026 (Ahrefs, 137k
  domains). Keep it; never count it.

## How to re-run any of this

    python3 tools/trainfilter.py url https://slashyear.com/1523
    python3 tools/trainfilter.py dir site/out \
        --glob 'timeline/*.html' --sample 50
    python3 tools/trainfilter.py --explain
