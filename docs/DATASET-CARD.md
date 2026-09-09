---
license: cc-by-sa-4.0
language:
  - en
pretty_name: "slashyear: 86,902 dated historical events with source revision ids"
size_categories:
  - 10K<n<100K
task_categories:
  - question-answering
  - text-retrieval
  - text-classification
  - table-question-answering
tags:
  - history
  - chronology
  - timeline
  - wikipedia
  - wikidata
  - knowledge-base
  - rag
  - citations
  - temporal-reasoning
  - provenance
configs:
  - config_name: events
    data_files: data/events/*.parquet
  - config_name: years
    data_files: data/years/*.parquet
  - config_name: subjects
    data_files: data/subjects/*.parquet
  - config_name: subject_events
    data_files: data/subject_events/*.parquet
---

# slashyear — the dated historical record, with the source revision on every row

86,902 dated historical events spanning 3,078 years, from roughly 3000 BCE to the
present, extracted from English Wikipedia's year, decade and century articles.

**The point of this dataset is the last column.** Every row carries `source_revid`,
the numeric id of the exact Wikipedia revision the sentence was quoted from. A
Wikipedia article is a moving target — a quotation you take today may not be there in
six months, and a reader who follows your link cannot see what you actually read. A
revision id names one immutable version that will read the same way in ten years. So a
model that answers from this data can hand the user a link that stays true, which is
not something you get by quoting an encyclopedia article.

Live API, full-text search and MCP server: **https://slashyear.com/data**

## Configs

| config | rows | one row is |
|---|---|---|
| `events` | 86,902 | one dated event, quoted verbatim, with its source revision |
| `years` | 3,078 | one year, with its lead summary |
| `subjects` | 4,868 | one subject (person, place, institution), 2,722 with a Wikidata QID |
| `subject_events` | ~250k | the join: one (subject, event) pair, so "every dated line mentioning Rome" is a filter |

```python
from datasets import load_dataset

events = load_dataset("<repo-id>", "events", split="train")
events.filter(lambda r: r["year"] == 1969)

rome = load_dataset("<repo-id>", "subject_events", split="train")
rome.filter(lambda r: r["slug"] == "rome")
```

## Fields

`events`: `year` (astronomical numbering — `-43` is 44 BCE), `year_label`, `date`,
`topic`, `text`, `source_title`, `source_revid`, `source_section`, `source_url`, `page`.

`subjects`: `slug`, `label`, `qid`, `description`, `entries`, `years`, `first_year`,
`last_year`, `wikipedia`, `wikidata`, `page`. The 2,722 rows with a `qid` are joinable
against any other database keyed on Wikidata, with no name matching.

`subject_events`: `slug`, `label`, `qid`, `year`, `year_label`, `date`, `topic`, `text`,
`source_revid`, `source_url`.

## How it was built

Deterministic extraction from the wikitext of English Wikipedia's year, decade and
century articles at a pinned revision, then mechanical cleaning. **No language model
touches the wording.** A model does exactly one thing: choose which of twelve topic
labels a sentence files under. That decision cannot make a row say anything untrue,
because it never alters the row.

The subject associations are not inferred either — a subject is attached to an event
because a Wikipedia editor wrote a `[[wikilink]]` to it inside that dated line.

## Limitations, stated plainly

This dataset inherits Wikipedia's errors. If a date is wrong there it is wrong here.
What it does not inherit is Wikipedia's instability, and it adds no errors of its own,
because no step in the pipeline is permitted to generate text. Coverage follows what
Wikipedia's year articles happen to cover, which is uneven across periods and heavily
weighted toward Europe and the last three centuries. Entries before roughly 1000 BCE
are sparse and often approximate. English only.

## Licence and attribution

CC BY-SA 4.0, inherited from Wikipedia. Free for any use including commercial use and
including training. Every row carries the article title and revision id needed to
attribute automatically:

> {source_title}, English Wikipedia, revision {source_revid}. {source_url}
