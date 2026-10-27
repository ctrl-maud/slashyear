---
license: cc-by-sa-4.0
language:
- en
pretty_name: SlashYear-Bench
size_categories:
- n<1K
task_categories:
- question-answering
tags:
- temporal-knowledge
- history
- closed-book-qa
configs:
- config_name: default
  data_files: items.jsonl
---

# SlashYear-Bench

SlashYear-Bench is a 1,000-question closed-book benchmark for temporal knowledge in language models: when things happened, who held an office in a given year, what was No. 1 on the Billboard Hot 100 in a given week, and how US prices changed between two years. Every question is generated from records published on [slashyear.com](https://slashyear.com), and every item carries its gold answer together with the source record it came from (a Wikipedia revision id or a FRED series URL), so any item can be checked against the exact text it was derived from.

## Question types

| type | n | question template | gold | scoring |
|---|---|---|---|---|
| `event_year` | 400 | "In what year did this happen? <sentence>" | year (integer) | exact year; secondary metric: within ±1 year |
| `number_one` | 200 | "Which song was No. 1 on the Billboard Hot 100 chart dated <Month D, YYYY>?" | song title (artist kept in the source record) | normalized title match |
| `leader` | 250 | "Who was the <title> of <state> in <year>? Answer with the name only." | person name | name matcher (see below) |
| `cpi` | 150 | "Using the U.S. BLS CPI-U annual average, $100 in <Y1> is equivalent to how many dollars in <Y2>? Answer with a number." | 100 × CPI[Y2] / CPI[Y1] | within 3% |

## Data fields

`items.jsonl`, one JSON object per line:

- `id`: `ev-NNNN`, `no1-NNNN`, `ld-NNNN` or `cpi-NNNN`
- `type`: one of the four types above
- `question`: the prompt text sent to the model
- `answer`: the gold answer (integer year, title string, name string, or a number rounded to cents)
- `accept`: list of accepted surface forms (title variants, alternative name forms; for `cpi` the unrounded value as text)
- `source`: `{kind, url, revid, page, record}`. `kind` is `wikipedia_revision` or `fred_series`. `url` is a permanent link (`index.php?oldid=...`) to the Wikipedia revision the record was quoted from. `record` holds the original data row (for `event_year` the full verbatim entry including its date and section, for `leader` the holder's quote line with tenure years and Wikidata QID, for `number_one` the chart date, title and artist, for `cpi` both index values).
- `meta`: stratification info (era, decade, region, conversion direction)

## Construction

All items come from the static JSON export of slashyear.com (`api/year/<year>.json`, `api/facts/<year>.json`, `api/hot100.json`, `api/prices.json`), retrieved by the site between September and October 2026. `build.py` regenerates `items.jsonl` deterministically (seed 20261027).

**event_year.** Candidates are dated entries from the year pages for 1500–2025 whose text has the form "<Month> <day> – <sentence>" (31,707 entries). Births and deaths sections are excluded, as are sections such as holidays, incumbents and "date unknown". The date prefix is removed, and a sentence is rejected if it:

- contains any 4-digit number (which removes years and names like "the 1969 Portugal earthquake");
- contains a decade ("1960s", "'60s"), a numeric ordinal ("20th", "37th"), the words century, millennium or decade, spelled-out centuries, or era markers (AD, BC, CE);
- is shorter than 8 words or longer than 70;
- starts with a second date (stacked date prefixes);
- has the same normalized text (accent-folded, lowercased, punctuation removed) as an entry under any other year anywhere on the site;
- has fewer than two capitalized proper-noun tokens besides sentence-initial words and month names, as a rough proxy for "names a specific, notable entity".

That leaves 23,446 sentences. 400 are sampled with era quotas (1500s: 45, 1600s: 45, 1700s: 50, 1800s: 65, 1900–1949: 55, 1950–1999: 75, 2000–2025: 65). Entries from the main "<year>" article are preferred over "<year> in <country>" articles, and each year contributes at most two items, relaxed only where an era did not fill its quota. The questions come from 263 distinct Wikipedia revisions.

**number_one.** Chart weeks from the first Hot 100 (August 4, 1958) to December 2025, sampled by decade (1958–59: 20, 1960s through 2000s: 30 each, 2010s: 20, 2020–2025: 10), with at most one question per song. The `accept` list contains the title as given, the title without parentheticals, and the individual parts of medleys and double A-sides.

**leader.** From the state-leader lists on facts pages for 1800–2025, a (state, year, title) triple is kept only when exactly one holder with that title is recorded for that state in that year. This makes the items unambiguous within slashyear's checked leader record, not necessarily in the historical record: if slashyear's cross-check dropped a second holder for some year, that year can still show a single recorded holder. In addition, the holder's tenure in the quote line must strictly contain the year (the term neither starts nor ends that year), so a year with a mid-year handover is never asked. Titles that are acting, provisional, interim or collective (councils, regents, captains regent, co-princes), holders without a Wikidata QID, composite state labels containing "/", and single-token generic names (for example "Ali") are dropped. 250 items are sampled by period (1800–49: 45, 1850–99: 45, 1900–49: 55, 1950–99: 60, 2000–25: 45), with each person used once and each state at most twice. State labels are lightly cleaned for readability (date-range parentheticals removed, "X: Y dynasty" becomes "X (Y dynasty)").

**cpi.** Year pairs from 1913–2025 at least five years apart, about 88% converting forward in time and 12% backward. The gold value uses the CPI-U (FRED series CPIAUCNS, all items, U.S. city average) annual averages from `prices.json`. These are means of the monthly values, which agree with BLS-published annual averages well within the 3% tolerance.

## Scoring

`score.py` grades cached responses. Errors and empty responses count as wrong, and accuracy is computed over all 1,000 items.

- `event_year`: the first 3- or 4-digit integer in the response is the prediction. The main metric is the exact year; the secondary metrics are accuracy within ±1 year and the median absolute error.
- `number_one`: the response is split into candidate titles (quoted strings, the first line, and text before "by" or a dash), then case, accents, punctuation, "&"/"and" and parentheticals are normalized away. Correct if any candidate equals an accepted title. Titles of three or more words also count if they appear as a whole phrase in the response. The artist is not required.
- `leader`: names are accent-folded (including đ, ø, ł and similar), lowercased and tokenized, particles (de, von, al, ibn, ...) and honorifics are dropped, and common given-name exonyms are mapped to one form (William/Wilhelm/Guillaume, Mohammed/Muhammad, and so on). A response is correct if (a) for a regnal name such as "Louis XVIII" or "Rama II", it contains the base name followed by the same numeral (Roman or Arabic, "3rd" also accepted); otherwise if (b) it contains the gold's last significant token (the surname), unless the word just before it is a different given name (so "Heydar Aliyev" does not count for "Ilham Aliyev"); or (c) it contains two significant tokens of the gold name, at least one of which is not a very common given name; or (d) for names of three or more tokens, it contains a distinctive first token (for example "Mobutu" for "Mobutu Sese Seko"). A surname of five or more letters also matches a transliteration variant with the same first letter and a string similarity of at least 0.8 ("Fahmi" for "Fahmy"). A regnal name that also carries a family name ("Alexandru II Ghica") falls back to the surname rules, unless the response gives a different numeral. Both the `name` and the fuller `person` label from the source are tried.
- `cpi`: the first number in the response, ignoring the two years and the number 100, must be within 3% of the gold value.

## Results

Closed-book, single-turn runs on 2026-10-27 through the Azure OpenAI Responses API. No tools were passed, so the models had no web search or retrieval. Instructions: "Answer from memory. Be concise; give only the answer." `max_output_tokens` was 4000, with one retry at 16000 if a reasoning model returned no text. Accuracy is over all 1,000 items. "macro" is the unweighted mean of the four per-type accuracies.

| model | overall | macro | event_year (exact) | event_year (±1) | number_one | leader | cpi |
|---|---|---|---|---|---|---|---|
| gpt-6.1-sol | 0.967 | 0.976 | 0.933 | 0.950 | 0.980 | 0.992 | 1.000 |
| gpt-6-astra | 0.965 | 0.975 | 0.930 | 0.948 | 0.980 | 0.988 | 1.000 |
| gpt-6-luna | 0.907 | 0.910 | 0.898 | 0.922 | 0.780 | 0.976 | 0.987 |

On `event_year`, the median absolute error is 0 for all three models, and the mean absolute error is 1.69 (astra), 1.92 (sol) and 2.31 (luna) years. Two `event_year` items (ev-0078 and ev-0367) were rejected by the Azure content filter for every model and are scored as wrong. Most of gpt-6-luna's `number_one` misses name a song that was No. 1 a few weeks before or after the asked chart date.

All three models are close to ceiling on `cpi` and `leader`. The benchmark separates them mainly on `event_year` and `number_one`.

**Leader matcher check.** I read 30 randomly sampled graded `leader` items (across all three models), and the matcher's grade agreed with my reading on all 30. I also read every `leader` response graded wrong (11 across the three models). Four were matcher false negatives: a transliteration ("Hussein Rushdi Pasha" for "Hussein Roshdy Pasha", three times) and "Mahmud Bey" for Mahmud ibn Muhammad. Three followed a different numbering convention: the gold says "Francis II" (Holy Roman Empire numbering), and the models answered "Francis I of Austria", the same person. Four were genuine errors. Leader accuracy is therefore understated by up to about one point per model. Raw responses and per-item grades are in `results/`.

## Limitations

- Gold answers are only as good as the Wikipedia revisions they were quoted from. Year-article events sometimes carry disputed or Julian/Gregorian-ambiguous dates, and leader lists contain occasional errors. Pre-1900 leader titles in particular follow the list articles' conventions (for example, Muhammad Ali of Egypt is listed as "Khedive").
- The proper-noun filter is a heuristic. Some `event_year` sentences remain hard to date even for an expert, and some still contain indirect clues such as "Apollo 11" or "Super Bowl III". That is intended: those clues test knowledge rather than give away the answer.
- Gold leader names follow the source list's naming and numbering. For example, Francis II/Francis I of Austria counts only under the list's numbering.
- The leader matcher is string-based and can be wrong in both directions: unusual transliterations can be missed, and a response naming a different person who shares the surname can be accepted when there is no given name to compare against. A manual spot check is reported above.
- Some `number_one` questions near year boundaries or chart-policy changes may be answered with a song that was No. 1 on a neighbouring week. These count as wrong.
- The benchmark is English-only and skews toward Europe and the Americas, as the source articles do.

## License

The `event_year`, `number_one` and `leader` items quote or derive from English Wikipedia text and are released under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Each item links to the specific Wikipedia revision it came from, which serves as attribution to that revision's authors. The CPI series is a U.S. government work in the public domain.

## Citation

```bibtex
@misc{slashyear_bench_2026,
  title        = {SlashYear-Bench: a temporal-knowledge QA benchmark built from slashyear.com},
  author       = {{slashyear.com}},
  year         = {2026},
  howpublished = {\url{https://slashyear.com}},
  note         = {Questions derived from verified, revision-pinned Wikipedia quotations and FRED CPI-U data published on slashyear.com}
}
```

## Files

- `items.jsonl`: the benchmark
- `build.py`: regenerates `items.jsonl` from the slashyear.com API export
- `run.py`: queries models (closed book, no tools) and caches raw responses in `results/raw/`
- `build_stats.json`: candidate and filter counts from the last build
- `score.py`: grades responses and writes `results/<model>.jsonl` and `summary.json`
- `summary.json`: per-model accuracy, per-type accuracy and event-year error metrics
