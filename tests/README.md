# The gates

These are the checks a build has to pass before anything deploys. They live in `pipeline/`
because `verify.py` imports the extractor's own `clean_line()` — checking the published text
against a *reimplementation* of the cleaner would only prove the reimplementation agrees with
itself. Run them from the repository root, in this order:

| gate | what it would catch |
| --- | --- |
| `pipeline/verify.py [--live]` | a published sentence that is not in the revision it cites |
| `pipeline/coverage.py` | a well-known event missing from the year it happened in |
| `pipeline/famous.py` | 333 fixed recall cases regressing |
| `pipeline/surface.py` | a page kind losing its shape, trace, identity or budget invariants |
| `pipeline/integrity.py` | the rendered page disagreeing with an independent re-render |
| `pipeline/lifedates.py` | birth/death years drifting from Wikidata (ratcheted) |
| `pipeline/theming.py` | section themes drifting from the article's own By-topic headings (ratcheted) |
| `pipeline/montage.py` | the lead ignoring the article's own caption events |
| `pipeline/audit.py` | a defect visible only in the exported HTML |
| `pipeline/machine.py --live` | the API, dumps, search ranking or MCP surface breaking |

`scripts/reproduce.sh` runs the offline subset in order. The `--live` variants hit Wikipedia and
the deployed site, so they are not run in CI on every pull request.
