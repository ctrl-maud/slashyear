# Getting slashyear.com found and used

Written 2026-09-07, after the question "how do I make my site's SEO as good as Wikipedia's
and start naturally getting used". Everything in the "Shipped" section is live on
slashyear.com right now and was checked on the real domain, not on a preview.

## The honest starting point

Wikipedia does not rank because of anything on its pages. It ranks because a very large
part of the internet links to it, and has done for twenty years. There is no setting, no
plugin and no amount of tidy code that copies that. So the goal is not "be Wikipedia". The
goal is two separate things: stop losing the traffic you could already be getting, and
build the one thing you have that Wikipedia does not.

There is also a problem specific to this site that has to be said plainly. Every sentence
on a year page is quoted, word for word, from the Wikipedia article of the same name. That
is the whole point of the site and it is why the pages can be trusted. But to Google it
means a year page looks like a copy of a page Google already has, already trusts, and has
ranked for years. **slashyear.com/1066 will never outrank Wikipedia's article on 1066, and
no work will change that.** Anyone who tells you otherwise is selling something.

What that leaves is real and worth having:

- **The cross-cut.** No single Wikipedia article holds everything that happened on
  7 September across 3,078 years with a source link on every line. That page is now ours
  and it is not a copy of anything.
- **The citation.** Every line links to the exact revision of Wikipedia it came from. That
  is a thing programmers and researchers care about, and it is why they would link here.
- **The data.** The whole site is now downloadable as plain files, free, no signup. Being
  built into somebody else's project is a better outcome than being read by one person.

## Shipped today

### The parts search engines read

Every page previously shipped with the same description ("A sourced index of the year X"),
no canonical address, and no structured data. All three are fixed.

- **Titles** now say what the page is: "1066 CE — events, births and deaths" instead of
  "1066 CE — /year".
- **Descriptions** are built from the page's own opening lines, so all 3,275 pages differ
  from each other instead of repeating one sentence.
- **Canonical address** on every page, so the same content at two addresses can no longer
  be counted as two competing pages.
- **Structured data** (the machine-readable summary Google reads for rich results) on every
  page: what the page is, what it is about, the breadcrumb trail, the licence, and — on
  year pages — a pointer to the exact Wikipedia revision it is based on.
- **The year 404 CE was set to "do not index".** Next.js writes its own error page and the
  page for the year 404 to the same filename, and the previous fix moved the year page to
  its own address but left it carrying the error page's instruction to search engines to
  ignore it. It is now indexable with the right title, description and address.
- **www is dead.** `www.slashyear.com` and `slashyear.com` served the same page at two
  addresses, which splits any credit a page earns. www now permanently redirects to the
  bare domain. This is a Cloudflare zone rule, **not** a file in the build: a
  host-qualified line in the Pages `_redirects` file is accepted and then silently ignored
  (measured live — www stayed at 200).
- **Sitemap** now lists 3,278 pages instead of 2,910, and each carries the date its source
  revision was retrieved, so a crawler can tell what changed.

### The new pages — 366 of them

`pipeline/dates.py` re-files every entry that carries a day ("7 September") under that day
instead of under its year. Nothing is rewritten: the same sentence, the same citation, the
same revision id. That produced **366 calendar pages holding 54,415 entries**, at
`/on/september-7` and so on, with an index at `/on`.

This matters more than any of the tag work above:

- "September 7 in history" is a phrase people actually type, every day of the year, and the
  competition there is thin content farms — not Wikipedia.
- It is genuinely original. No source page exists to outrank us.
- It doubles the internal link structure. Every date on a year page is now a link to that
  day, and every year on a date page is a link back. That is the mechanic that makes a
  reference site crawlable instead of 3,275 disconnected pages.

The front page also now shows today's own entries, fetched in the browser, so the home page
says something different every morning and a returning reader has a reason to come back.

### The API

Everything is now also a plain file at `/api/…`: `/api/year/1066.json`,
`/api/date/september-7.json`, plus indexes, with the documentation page at `/api`. No key,
no limit, no account, open to any website. This is the bait. A person reads a page once; a
developer who builds on the files links to the site from their project, and links are the
only currency that actually moves rankings.

### Telling the search engines

All 3,278 addresses were submitted through IndexNow (`pipeline/indexnow.py`), which reaches
Bing, Yandex, Seznam and Naver in one call with no account needed. Google does not take
part in that scheme.

### Verification

The site's guarantee — every published sentence is word for word from the revision it cites
— was re-checked after all of this against the rendered pages, not against the source data:
**86,902 bullets across 3,078 year pages, 0 differences**, and **all 54,415 date-page
entries trace back to a real bullet on a year page**.

## Shipped in the second round, same day

The first round gave the site a surface Wikipedia does not have: the 366 calendar days.
This round did the same trick three more times and then built the machinery that turns
readers into links.

**616 more pages, all of them aggregates no single Wikipedia article holds.**

- **12 subject pages** (`/topic/science-and-discovery`) and **290 subject-by-century pages**
  (`/topic/science-and-discovery/17th-century`). This is the part of the site that is
  genuinely ours: which subject a sentence belongs to was decided by our own pipeline, not
  by Wikipedia, so "science and discovery in the 17th century, 145 sourced entries, 1600 to
  1699" is a page that exists nowhere else. Births and deaths are deliberately excluded —
  a list of people per century is only Wikipedia's own layout again.
- **32 century pages** and **273 decade pages**. These are less about ranking and more
  about shape. Until today every one of 3,078 year pages was reachable only from a single
  1.1MB directory page, which is the worst possible thing to hand a crawler. Now it is
  century → decade → year, roughly fifty links a step. A century here runs 1900–1999
  rather than 1901–2000, because the pedantic definition puts the 1100s in two centuries at
  once, which would mean the same decade on two pages.
- Thin pages are dropped rather than published. A decade needs 12 entries, a century 20, a
  subject-century 8. A page carrying three lines is a liability in an index.

**A one-tag embed at `/embed`.** `<script src="https://slashyear.com/embed.js" async>` puts
today's entries on anybody else's page, inherits their fonts, sets no cookie, and prints a
credit link home. It is the only link-building mechanism here that needs nobody's
permission: every site that installs it is a link, and the licence on the text means the
credit line is not optional.

**The API is now machine-discoverable.** `/api/index.json` is the endpoint list and
`/api/openapi.json` is a standard OpenAPI 3.1 document — those two files are what API
directories, SDK generators and AI agents look for when they find a site on their own. The
API also grew the new axes: `/api/topic/...`, `/api/century/...`, `/api/decade/...`,
`/api/cross.json`.

**Client-side navigation was removed.** Next was writing four React payload files per page
purely so links could swap pages without a reload — 15,560 files, which pushed the
deployment past Cloudflare's 20,000-file ceiling and, once deleted, left every link firing a
404 request on hover. Plain links now. Pages are static and edge-cached; nobody will notice
except the crawler, which never used any of it.

**A permanent auditor: `pipeline/audit.py`.** The double-check that found the real defects
yesterday was done by hand. It is now a script that reads the built site back and fails the
build on four things: every rendered bullet must equal the sentence it was built from, every
internal link must resolve the way Cloudflare resolves it, every title/description/canonical
must exist and be unique, and nothing but the not-found page may carry noindex. Current
state: **3,890 pages, 188,860 bullets, 190,017 links, clean.**

## What comes next, in order of what it is worth

1. **Links, which is the whole game.** Nothing above will beat a handful of real sites
   linking here. The realistic first ones: a Show HN post on Hacker News about the
   citation-per-sentence idea and the free API; the subreddits that care (r/history,
   r/datasets, r/InternetIsBeautiful); and the people who run "on this day" bots, who need
   exactly the file we now publish.
2. **The `public-apis` listing and the other API directories.** Blocked only on a GitHub
   account. This is the highest-value link a free API can get.
3. **Preview images.** Right now a link posted to a group chat, a forum or social shows no
   picture. A generated card per page fixes that and lifts how many people click.
4. **Answer the questions people actually ask.** "How long ago was 1066", "what year was
   the Battle of Hastings" — small derived pages that Wikipedia does not serve well.
5. **Keep it fresh.** Re-harvesting the source revisions on a schedule keeps the retrieved
   dates current and gives crawlers a reason to come back.

## Timescale

Nothing here shows up this week. A new domain with no links takes weeks to be crawled
properly and months to rank for anything. The order of events is: Google finds the sitemap,
takes the pages slowly, starts showing the date pages for low-competition searches, and
only then does volume build. Search Console is what lets you watch that happen instead of
guessing.

## Files

- `pipeline/dates.py` — builds the 366 calendar pages from the year data.
- `pipeline/cross.py` — builds the decade, century and subject pages.
- `pipeline/audit.py` — reads the built site back and fails on text, link, head or robots
  defects. Run it before every deploy.
- `pipeline/indexnow.py` — submits every address to Bing/Yandex/Seznam/Naver after a deploy.
- `pipeline/postbuild.py` — now also writes the API files, the sitemap with dates, and
  repairs the year 404 page's head.
- `site/lib/seo.tsx` — the shared titles, descriptions, canonical addresses and structured
  data.
- `site/components/Today.tsx` — today's entries on the front page.
- `site/app/topic/*`, `site/app/century/*`, `site/app/decade/*`, `site/app/embed` — the new
  pages.
- `recon/seo-home-mobile.png`, `recon/seo-date-mobile.png` — what it looks like on a phone.

---

# Round three, 2026-09-07 evening — "what makes us special, and why would a machine use us?"

The question was two questions. *If we quote Wikipedia verbatim, what are we?* and *how do
we give crawlers, APIs and language models a reason to pull from us?* They have the same
answer, so this is one piece of work.

## The honest position first

We are not a better encyclopedia and never will be. A year page here will not outrank
Wikipedia's article of the same name — that was true in the first round and nothing since
has changed it.

But "a wrapper of Wikipedia" is not what the site is, and the difference is worth being
precise about, because it is the entire product.

Wikipedia publishes **prose, per article**. It has an article about the year 1666, an
article about the Great Fire of London, and an article about London. What it does not
publish is **the underlying rows**: 86,902 individual dated statements, each one tagged
with the year it belongs to, the calendar day it names, the subject it is about, the
century and decade it sits in, the entities it mentions, and the exact revision it was
taken from — all in one structure you can query, join and download. Nobody publishes that,
including Wikipedia, because Wikipedia's unit is the article and ours is the sentence.

That is what we sell to a machine. Not the words — the words are free everywhere. The
**shape**.

## Shipped in this round

### 1. 2,941 subject timelines — `/timeline/<subject>`

Every dated entry in which Wikipedia's own editors linked to a subject, in order, from its
first appearance to its last. Constantinople: 378 entries across 355 years, 237 CE to 1930.
Rome: 470 entries, 771 BCE to 1998.

Three things make this ours rather than a copy:

- The association is not our guess and not a model's. It is the `[[Constantinople]]` link
  in the wikitext of the year article — Wikipedia's own editorial judgement, read
  mechanically out of the source.
- Only sentences already published on one of our year pages are used, so every line has
  been through `verify.py` and links back to a page of ours that also contains it.
- Wikipedia has hand-written "Timeline of ..." articles for perhaps a few dozen subjects.
  It does not have one for 2,941 of them, and none of the ones it has carry a per-line
  citation to a fixed revision.

Each timeline also resolves to a **Wikidata Q-number** (2,722 of the 2,941 have one). That
single field is what turns the file from text into data: a QID is the join key every other
database on earth uses, so somebody merging our timeline into theirs never has to match on
a string. It is also the reason the JSON is worth more than the page.

### 2. Full-text search, with nothing running — `/api/search?q=`

Every one of the 86,902 sentences is now indexed by word. `?q=Krakatoa` returns the three
eruptions; `?q=eruption&from=1800&to=1900` returns the ten in that century. Krakatoa is the
case that made it necessary: it appears in three years, so it never earned a subject page,
and the earlier subject-only matching returned nothing for it — which is the exact moment a
machine gives up on you and goes back to scraping the encyclopedia.

There is no database and no server. Word postings are bucketed into 36 static files by
first letter and the sentences into 335 shards of 256; a query fetches the two or three it
needs and hydrates only the shards its results actually land in. It cannot fall behind the
site because it is built from the same payloads the pages are, and there is nothing that
can be down while the site is up.

### 3. An MCP server — `slashyear.com/mcp`

This is the direct answer to "give language models a reason to use us". MCP is the standard
a model uses to call an outside tool; pointing any MCP client at that URL — no key, no
account, no session — gives the model five tools: `search_history`, `get_year`, `get_day`,
`get_timeline`, `list_subjects`.

The pitch to the model is one sentence, and it is in the server's own instructions so the
model reads it on connect: *a model that quotes an encyclopedia article cannot prove what
the article said when it read it, and every row here carries the revision id, so a claim
built on it stays checkable.* That is a real reason to prefer us that does not depend on
having better facts than Wikipedia — it depends on having the same facts pinned down.

    claude mcp add --transport http slashyear https://slashyear.com/mcp

### 4. The whole corpus as a download — `/dump/`

Three gzipped newline-delimited JSON files: every entry (5.4 MB), every year, every subject
timeline, plus a Frictionless `datapackage.json` describing them. Free for any use
including training and redistribution.

Giving the data away unconditionally is not generosity, it is distribution. A scraper that
takes 6,800 pages owes us nothing and credits nobody; somebody who downloads a described,
licensed data package cites it, and that citation is a link. It is also the only asset here
that cannot be outranked.

### 5. `/llms.txt` and `/llms-full.txt`

The convention a model-side crawler looks for when it wants to know what a site is without
rendering it. Ours leads with the one fact that matters to a model — every sentence is
attributable to a fixed revision — then lists the dumps, the API, the MCP server and the
300 largest timelines.

### 6. A `Dataset` record on `/api`

Structured data of type `Dataset`, with the three downloads declared as distributions. This
is what **Google Dataset Search** indexes, and it is an index we can actually place in,
because it ranks datasets and Wikipedia does not publish one.

### 7. Cloudflare was blocking every AI crawler. It is not any more.

This was the largest single finding of the round and it was invisible from the site's own
files. Cloudflare's *managed robots.txt* was switched on for the zone, which silently
prepends its own block to the top of `robots.txt` before ours:

    User-agent: *
    Content-Signal: search=yes,ai-train=no,use=reference

    User-agent: GPTBot
    Disallow: /
    User-agent: ClaudeBot
    Disallow: /
    ... and Google-Extended, CCBot, Amazonbot, Bytespider, Applebot-Extended,
        meta-externalagent

So the site had been telling every model crawler to go away — the exact opposite of the
strategy — while the file in the build said `Allow: /`. Turned off via
`PUT /zones/<id>/bot_management` with `is_robots_txt_managed: false` and
`ai_bots_protection: disabled`, cache purged, and confirmed live: `robots.txt` is now our
own file, which names twenty model crawlers and allows all of them explicitly.

The general lesson: **the robots.txt in your repository is not necessarily the robots.txt
on your domain.** Read it off the live host.

## Where the traffic actually comes from now

In order of how much of it we control:

1. **Being downloaded and built on.** `/dump/` + `datapackage.json` + the Dataset record.
   Somebody else's project citing us is worth more than a thousand visits.
2. **Being called by models.** The MCP server and `/api/search`. Every answer a model
   writes from it can carry our link.
3. **The timeline pages.** 2,941 new pages targeting "<subject> timeline", a query shape
   Wikipedia's article about that subject does not directly answer.
4. **The date pages.** Still the strongest ordinary-search asset — "on this day" is a real
   query and no article answers it.
5. **The embed.** One script tag, a credit link home, needs nobody's permission.

## What is deliberately not being done

- **Writing our own summaries to look less like a copy.** The moment a sentence on this
  site is ours, the guarantee that every sentence is checkable dies, and the guarantee is
  the only thing we have that Wikipedia does not.
- **Adding a second text source for the sake of it.** The Library of Congress newspaper
  archive was tested this round and dropped: the modern endpoint returns two-megabyte
  responses and cut off mid-transfer, and the old one 403s. It stays on the list, but a
  flaky source that breaks a build is worse than no second source.
