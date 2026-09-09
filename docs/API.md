# API, bulk downloads and MCP

Everything below is free, static, CORS-open and unauthenticated. No key, no rate limit, no signup.
The site is a static export on Cloudflare Pages, so a "request" is a file read; the only route that
computes is search.

## Static JSON

| path | returns |
| --- | --- |
| `/api/index.json` | the machine index: what exists, licence, base URL, no auth |
| `/api/openapi.json` | OpenAPI description of everything below |
| `/api/year/<year>.json` | the full year payload (astronomical numbering: `-43` = 44 BCE) |
| `/api/date/<month>-<day>.json` | every entry on that calendar day, any year — `july-20` |
| `/api/entity/<slug>.json` | a subject's whole timeline — `byzantine-empire` |
| `/api/entities.json` | the subject index, largest record first |
| `/api/century/<slug>.json`, `/api/decade/<slug>.json` | century and decade payloads — `11th-century`, `1960s` |
| `/api/dates.json`, `/api/cross.json` | the calendar index and the cross-page links |

The site pages mirror these one-for-one: `/1969`, `/on/july-20`, `/timeline/byzantine-empire`,
`/topic/<theme>`, `/century/<slug>`, `/decade/<slug>`. Every page is prerendered; the JSON is the
same data the page was built from, not a second pipeline.

## Search

```
GET /api/search?q=eruption&from=1800&to=1900&limit=20
```

Answers two questions at once, because a caller usually has both: which **subjects** match (each
with a timeline behind it) and which individual dated **entries** match. Krakatoa has no subject
page — it appears in three years — and still returns its eruptions, which is the case that made a
full-text index worth building. `from`/`to` are astronomical years; `limit` defaults to 25, caps at
200.

The query tokenizer in `site/edge/search.js` and the index builder in `pipeline/postbuild.py` are
the same tokenizer written twice and **must stay in sync** — a query token the index does not hold
returns nothing.

## Bulk

| file | contents |
| --- | --- |
| `/dump/events.ndjson.gz` | every dated entry with its citation |
| `/dump/years.ndjson.gz` | every year payload |
| `/dump/entities.ndjson.gz` | subjects and their timelines |
| `/dump/datapackage.json` | Frictionless descriptor for the three above |

The same corpus is packaged as Parquet by `pipeline/hfpack.py`; the card describing those
tables is [DATASET-CARD.md](DATASET-CARD.md).

## MCP

`https://slashyear.com/mcp` speaks the Model Context Protocol over HTTP, so an assistant can query
the corpus directly instead of recalling it. Tools:

- **search_history** — words, optional year range, limit
- **get_year** — one year's entries
- **get_day** — accepts `july-4`, `July 4`, `07-04` or any `YYYY-MM-DD`
- **get_timeline** — a subject's entries by name or slug
- **list_subjects** — browse subjects, largest record first

Every returned entry carries its `revid` and citation URL, which is the point of pointing a model
at this rather than at a summary: the model can hand the user something checkable.

`pipeline/machine.py --live` is the gate for this whole surface, including search ranking cases.
