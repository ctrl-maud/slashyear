# Round sixteen — the half of the site no human ever looks at

**The class: every gate this project had ends at the HTML. The product doesn't.**

`audit.py` reads the exported pages back and proves they say what `data/site` says.
`verify.py` proves `data/site` came from Wikipedia. Fifteen rounds of review, and every
one of them stopped at the rendered page. But the pitch for this site is that we sell the
shape, not the words — and the shape is delivered through `/api`, `/dump`, `/api/search`,
`/mcp` and `llms.txt`. Not one test had ever read a byte of any of them.

`pipeline/machine.py` is the gate. Six checks: MIRROR (every `/api` file equals the payload
its page was rendered from, in both directions), DUMP (the three NDJSON dumps round-trip
every published row exactly), INDEX (the API indexes name every file that exists and none
that doesn't), TEXT (every posting in the inverted index resolves, every indexed sentence
is published, every token really occurs in the sentence it is posted against), DOC (every
URL promised by `index.json`, `openapi.json`, `datapackage.json` and `llms.txt` exists),
and LIVE (`/api/search` and the `/mcp` JSON-RPC server called for real, every returned row
cross-checked against the local data).

The static half came back clean: 8,949 API files, 86,902 dump rows, 86,902 indexed
sentences, 321 documented URLs. Then the live half.

## What it found

**`/api/search` — the only endpoint on this site that computes — was ranking by year and
calling it search.**

```
GET /api/search?q=Apollo+11
  1920  The New York Times ridicules American rocket scientist Robert H. Goddard...
  1930  Buzz Aldrin, American pilot, astronaut (Apollo 11), second person...
  1930  Neil Armstrong, American astronaut, first human to set foot on the Moon...
  1969  Apollo 11 (Buzz Aldrin, Neil Armstrong, Michael Collins) lifts off...
```

An agent asking this site about Apollo 11 got a 1920 newspaper item. Three separate causes,
each of which passed every other check because every row returned was real, published and
correctly cited — the defect was the *order*, and nothing had ever looked at an order.

1. **The tokenizer threw the query away.** `_tokens()` in `postbuild.py` and `queryTokens()`
   in `edge/search.js` both drop tokens under three characters, so "Apollo 11" was indexed
   and searched as "Apollo". Sixty rows matched instead of nine, and the one word that
   made the query specific was the one word discarded. Same for "9/11", "V2", "44 BC".
   Fixed by keeping any token that contains a digit from two characters, on both sides.

2. **The ranking was settled before the answer was read.** The postings give a score, but
   the phrase check — the only thing that can tell "Apollo 11" from "Apollo" — runs on
   sentences already fetched, and the fetch stopped after 24 shards taken in docid order.
   Docids are handed out in year order, so hydration always started at the beginning of
   history and the sentence that actually said "Apollo 11" was never read. Fixed by
   hydrating the *densest* shards first — where a query's matches cluster is where its
   answer is — and raising the ceiling to 40.

3. **Every match was equal, so the earliest year won.** Four rows carry the phrase
   "Apollo 11": the 1969 launch opens with it, Buzz Aldrin's birth has it in a
   parenthesis, and the 1920 item has it in its final clause. All three got the same
   phrase bonus and the tie broke on year. Fixed by scoring *where* the phrase sits: a
   sentence that opens on the phrase is about it, one that ends on it is mentioning it.

And separately: **a bare year is a query on a site of year pages.** `q=1969` answered with
a 1622 shipwreck, because every "(d. 1969)" birth row matches the token just as well and
there are more of them. A row whose own year equals a numeric query now outranks them.

```
GET /api/search?q=Apollo+11        1969  Apollo 11 returns from the first successful Moon landing
GET /api/search?q=moon+landing     1969  Apollo program Moon landing: ... Lunar Module Eagle lands
GET /api/search?q=Stonewall+riots  1969  The Stonewall riots, a milestone in the modern gay rights movement
GET /api/search?q=1969             1969  1969 West German federal election...
```

## The gate that stays

SEARCHQ is `coverage.py`'s discipline pointed at the search endpoint: twelve queries anyone
would type, each with the answer that has to be in the top one, two or three. A search that
returns real rows in the wrong order passes every other test in this repository, so the
only way to hold the fix is to name the answers.

Calibration, twice, in this round alone: three of the gate's first "failures" were the
instrument's own bugs (it read cross-cut navigation files as page payloads, it pulled the
URL out of a shard row instead of the sentence, it tried to fetch documented URL
*templates*), and one was the gate insisting on its favourite Apollo 11 row when the launch
and the return are both right answers. A test that charges the site with the tester's taste
is not a test. Same lesson as the Julian calendar in round thirteen and the entity
categories in round fifteen — the first run of a new instrument is mostly artefact, and
you check the instrument before you believe it.

## What shipped

- `pipeline/machine.py` — the gate (MIRROR, DUMP, INDEX, TEXT, DOC, LIVE, SEARCHQ).
- `pipeline/postbuild.py` — `_tokens()` keeps digit-bearing tokens from two characters.
- `site/edge/search.js` — matching query tokenizer, densest-shard hydration, phrase-position
  scoring, bare-year boost.
- `FLEX.md` — the paste-ready description of what the site is, with the links.

Live and green: verify 86,902/0, coverage 51/51, famous 333/333, surface clean, integrity
clean, lifedates within baseline, theming 0, audit clean, machine clean including the live
API and all five MCP tools.

## The lesson

A gate that stops at the last thing a human sees will never test the thing a machine uses,
and on this site the machine surface *is* the product. Ask what the artefact is actually
for, then check that, not the part that happens to be easiest to render.
