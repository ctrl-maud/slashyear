# slashyear

**Every sentence published on [slashyear.com](https://slashyear.com) is quoted verbatim from a
numbered English Wikipedia revision, and the row carries that revision id, the article title and
the section anchor it came from.** No language model writes, paraphrases or summarises any
published wording. This repository is the pipeline that produces those rows, the site that serves
them, and the gates that prove the claim.

The rows are the point. Wikipedia publishes prose, one article per year. slashyear publishes the
individual dated entries underneath that prose as records — tagged with year, calendar day,
subject, century, decade, theme and source revision — so a year can be queried, joined, diffed and
cited rather than only read.

## What a row is

```json
{
  "date": "January 20",
  "text": "January 20 – Richard Nixon is sworn in as the 37th president of the United States of America.",
  "cite": {
    "url": "https://en.wikipedia.org/w/index.php?oldid=1373164180#January",
    "title": "1969",
    "revid": 1373164180,
    "section": "Events › January"
  }
}
```

`text` is the source line with wiki markup mechanically removed and nothing else changed. `revid`
is a frozen revision, not a live page, so the citation still resolves to the same words years from
now even if the article is rewritten. That is what makes the corpus checkable instead of merely
attributed.

## The guarantee, and how it is checked

`pipeline/verify.py` walks the full chain for every bullet on every page:

1. the published text equals `clean_line()` applied to the stored wikitext line — nothing drifted
   in rendering;
2. that wikitext line appears verbatim in the stored article revision;
3. with `--live`, the stored revision is byte-identical to what Wikipedia serves for that revision
   id, so the local copy was never edited or corrupted.

A failure at any step means a published sentence exists that no source supports, which is the one
defect this project cannot ship with, so the exit code is non-zero and a build can be gated on it.
Nine further gates check the things `verify` cannot see — coverage against a fixed event list,
famous-case recall, per-page-kind surface invariants, an independent re-render, life dates against
Wikidata, section themes against the article's own headings, the exported HTML, and the live
machine surface. See [docs/PIPELINE.md](docs/PIPELINE.md) and [tests/](tests/).

## Reproduce it

```bash
git clone https://github.com/ctrl-maud/slashyear && cd slashyear
python3 -m venv .venv && .venv/bin/pip install requests numpy
scripts/bootstrap.sh          # fetch the published data snapshot (no re-harvest)
scripts/reproduce.sh          # rebuild the pages from it and run the gates — prints PASS/FAIL
```

`bootstrap.sh` pulls the released snapshot from this repository's v1.0.0 release because the raw
harvest is hundreds of megabytes of Wikipedia revisions and takes hours. To rebuild the corpus from Wikipedia itself
instead, start at `pipeline/harvest.py` and follow the stage order in
[docs/PIPELINE.md](docs/PIPELINE.md) — the order matters, and the document explains where it bites.

## Layout

| path | what it is |
| --- | --- |
| `pipeline/` | harvest → extract → deaths → classify → notability → build → the gates → postbuild |
| `trainfilter/` | prose filters used to score corpus lines for training-data use |
| `site/` | the Next.js source for slashyear.com (no build output, no `node_modules`) |
| `site/functions/`, `site/edge/` | the search API and the MCP server, as Cloudflare functions |
| `tests/` | one runner that executes the gates in the order a stranger should run them |
| `docs/` | pipeline, schema, API, SEO, coverage audit, and the review archive |
| `docs/reviews/` | every self-review round, kept deliberately — the audit trail is part of the claim |

## Getting the data

- **Reproduction snapshot** — [`slashyear-data-snapshot.tar.gz`](https://github.com/ctrl-maud/slashyear/releases/download/v1.0.0/slashyear-data-snapshot.tar.gz)
  (105 MB) on the v1.0.0 release: the extracted claims, the Wikipedia revisions they came from,
  and the caches the gates need.
- **Bulk dumps** — `https://slashyear.com/dump/events.ndjson.gz`, `years.ndjson.gz`,
  `entities.ndjson.gz`, plus a Frictionless `datapackage.json`.
- **Static JSON API** — `https://slashyear.com/api/year/1969.json`, `/api/date/july-20.json`,
  `/api/entity/byzantine-empire.json`, and an OpenAPI description at `/api/openapi.json`.
  CORS-open, no key, no rate limit, no signup. See [docs/API.md](docs/API.md).
- **MCP server** — `https://slashyear.com/mcp`, so a model can query the corpus directly.

## Licensing

- **Code** — Apache-2.0 ([LICENSE](LICENSE)).
- **Rows** — CC BY-SA 4.0 ([LICENSE-DATA](LICENSE-DATA)). The text is derived from English
  Wikipedia, which is share-alike, so derivatives inherit that licence. Attribution goes to the
  Wikipedia contributors of the cited revisions; the citation shipped with every row is what makes
  that attribution possible.

## Citing

[CITATION.cff](CITATION.cff) is present, so GitHub renders a "Cite this repository" button.
