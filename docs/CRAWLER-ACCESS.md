# Are AI crawlers actually getting in? — verified 2026-09-07

## The answer

Yes. Every AI crawler and every search crawler gets a real page, on every part of
the site, with nothing in the way.

This is not read off the repo. On 2026-09-06 the repo said `Allow: /` while
Cloudflare was serving its own block in front of it, so a file in git proves
nothing. What follows was measured against the live host.

### What was measured

**168 live HTTPS requests** — 28 crawler user-agents × 6 paths. Every one returned
`200` with the real body. Checked for the failure mode a status code hides: a
Cloudflare interstitial ("Just a moment…", "Enable JavaScript and cookies") served
*with* a 200. None found.

Crawlers proved: GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User,
Claude-SearchBot, anthropic-ai, PerplexityBot, Perplexity-User, Googlebot,
Google-Extended, GoogleOther, Bingbot, Applebot, Applebot-Extended, CCBot,
Bytespider, Amazonbot, meta-externalagent, cohere-ai, MistralAI-User, AI2Bot,
YouBot, DuckAssistBot, Diffbot, omgili, Timpibot, FirecrawlAgent — plus a bare
`python-requests` script and a request with **no User-Agent at all**, both of which
also got 200s. There is no allow-list to be left off.

Paths proved: `/`, a year page, a subject timeline, `/api/search`, `/robots.txt`,
`/llms.txt`, `/sitemap.xml`, `/dump/datapackage.json`, `/api`. Also verified
separately:
- `POST /mcp` as GPTBot returns the real tool list.
- `www.slashyear.com` 301s cleanly to the apex for a bot, so a crawler that lands
  on www is not dead-ended.
- `/dump/events.ndjson.gz` downloads whole as CCBot — 5,622,619 bytes, gzip
  integrity verified, first record parses.
- **200 rapid concurrent requests as GPTBot**: zero rate-limits, zero challenges. A
  crawler that decides to take all 6,832 pages in one pass will not be throttled.

### The Cloudflare side

Every switch that can turn a crawler away is off, confirmed by API read:

| setting | value |
|---|---|
| `ai_bots_protection` | disabled |
| `ai_training` / `ai_search` / `ai_user` | disabled |
| `content_bots_protection` | disabled |
| `crawler_protection` | disabled |
| `is_robots_txt_managed` | **false** (this is the one that bit us) |
| `fight_mode` | false |
| WAF managed rules | off |
| custom firewall / rate-limit / transform rulesets | **none exist on the zone** |

`security_level` is `medium` and `browser_check` is `on`, which sound like they
should challenge bots. They measurably do not — that is what the 168 requests and
the 200-request burst are for.

## What changed today

`robots.txt` now carries the **Content Signals Policy** directive on every group:

```
Content-Signal: search=yes, ai-input=yes, ai-train=yes
```

That is the machine-readable version of the permission the header comment already
gave in English: index it, answer from it, train on it. Most sites that ship this
directive use it to say *no*; a crawler parsing for it finds an explicit yes here.
Google has publicly said the directive binds nothing, which is true — it is a
declaration, not a fence. It costs one line and removes an excuse.

The named-crawler list grew from 20 to 40: added ChatGPT-Agent, Claude-User,
Claude-SearchBot, GoogleOther, Google-CloudVertexBot, Meta-ExternalFetcher,
MistralAI-User, AI2Bot, Ai2Bot-Dolma, TikTokSpider, PanguBot, Webzio-Extended,
ImagesiftBot, FirecrawlAgent, Kangaroo Bot, SemrushBot-OCOB, Bravebot, NovaAct,
Operator, omgilibot. `User-agent: *` already covered them; naming them is for the
crawlers that only look for their own group.

Rebuilt, audit clean (6,832 pages, 262,709 bullets, 317,965 links), deployed to
production, cache purged, live robots.txt re-read off the host to confirm.

## The thing that will break this on 15 September 2026

Cloudflare announced on 1 July 2026 that it will begin **blocking "mixed-use" AI
crawlers by default** — the ones that blend search, agents and training — starting
**15 September 2026**, and the default applies to new domains, new customers and
**all free-tier zones**. slashyear.com is a `Free Website` zone.

So the correct answer to "are we good?" is not a one-time yes. It is a check that
runs every day and repairs the site if Cloudflare flips something.

### `tools/crawlguard.py`

```
python3 tools/crawlguard.py --host slashyear.com [--fix] [--json] [--quiet]
```

Checks three independent things and will not accept any one of them as proof of
the others:
1. every `bot_management` enforcement field reads its open value;
2. the robots.txt **served by the live host** has no real `Disallow` and no
   `ai-train=no` / `ai-input=no` signal;
3. all 168 crawler×path requests return a 200 carrying a real body.

`--fix` turns any enforcement switch back off and purges `/robots.txt` from cache.
Exit code 0 = open, 1 = blocked. Scheduled daily at 06:40 UTC (schedule id 12) in
#sh, silent when clean, posts only when something actually changed.

One thing deliberately **not** touched: `ai_bots_migration_opt_out`, currently
`false`. Cloudflare does not document which direction it points, and every
enforcement field it could govern already reads disabled. Flipping an undocumented
switch on a live site to guard against a hypothetical is how you cause the outage
you were trying to prevent. The daily guard catches the flip within 24 hours and
reverses it, which is the same protection without the guess.
