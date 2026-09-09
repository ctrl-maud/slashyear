# Cloudflare pay-per-crawl — what it actually is, and why we are not doing it
Researched 2026-09-07. Every claim below has a source; the ones that do not are
marked as unverified, because most of the numbers in circulation about this are.

## What it is, in plain words

Normally when a crawler asks for a page it just gets the page. Pay per crawl puts
a toll booth in front: the crawler asks, your server answers **HTTP 402 Payment
Required** along with a header saying the price, the crawler decides whether to
pay, and if it pays it gets the page. Cloudflare sits in the middle, bills the AI
company through Stripe, and pays you monthly.

There is a second flow where the crawler declares up front what it is willing to
pay (`crawler-max-price`); if your price is under that, it gets a 200 and a charge,
otherwise it gets the 402.

The whole thing rests on knowing *which* crawler is asking, because a user-agent
string is just text anyone can type. So paying crawlers have to sign each request
with a cryptographic key (Web Bot Auth, using HTTP Message Signatures / RFC 9421)
and register that key with Cloudflare. That part is genuinely well-built.

Source: https://blog.cloudflare.com/introducing-pay-per-crawl/ (1 July 2025),
enhancements changelog https://developers.cloudflare.com/changelog/2025-12-10-pay-per-crawl-enhancements/

## Status today

**Still closed beta**, fourteen months after launch. Cloudflare's own current docs
say so in as many words — "Pay per crawl is currently in closed beta" —
https://developers.cloudflare.com/ai-crawl-control/features/pay-per-crawl/what-is-pay-per-crawl/

You join by applying at https://cloudflare.com/paypercrawl-signup, or, if you are an
Enterprise customer, by asking your account manager. The docs never state a plan-tier
gate, but "ask your account manager" is not a sentence written for free-tier sites.

It lives inside a suite now called **AI Crawl Control** (formerly "AI Audit"), which
is generally available; the monetization piece specifically is not.

## The part that matters: is anyone paying?

**No AI lab has announced that it pays.** Not OpenAI, not Anthropic, not Google, not
Meta, not Perplexity. Fourteen months of a product whose entire value depends on
buyers, and the buyer side is empty.

The tell is what Cloudflare did on 1 July 2026. It announced it is **moving off**
pay-per-crawl toward a different model called **Pay Per Use**, where publishers get
paid when their content shows up in an AI's *answer* rather than when a page is
fetched. The two launch partners named are **Ceramic.ai** and **You.com** — a
startup and a small search engine. If the flat crawl toll were working, you do not
redesign the mechanism and relaunch it with those two names on it.
Sources: https://techcrunch.com/2026/07/01/cloudflares-new-policy-pushes-ai-companies-to-pay-for-publishers-content/
and https://ppc.land/cloudflare-stops-charging-ai-per-crawl-and-starts-paying-per-answer/
Pay Per Use is itself described as an experiment with broad availability "later in
2026" — so it is not available either.

The publishers named in the 2025 beta — Condé Nast, TIME, the Associated Press,
Adweek, Fortune — are all on the *selling* side. Sellers are easy to recruit. That
list is evidence of supply, not of a single dollar changing hands.

## What has anyone earned?

**No verified payout figure from any named publisher exists.** I looked and could
not find one, and neither could anyone writing about it.

Leaky Paywall ran the arithmetic on 17 July 2026 and stated plainly that it had no
actual reported earnings to work from, only models: a site with **one million
pageviews a month**, assuming AI crawlers are 1-2% of traffic, earns roughly **$20 a
month** at Cloudflare's $0.001 floor, or **$200** at a cent per page. Their own word
for it was "tip-jar money."
https://leakypaywall.com/cloudflare-pay-per-crawl-income-or-spare-change/

The "$50,000 to $200,000 per month for high-traffic sites" figure that circulates is
a market-sizing guess with no traceable source and no publisher behind it. Treat it
as marketing.

For scale: slashyear.com does not do a million pageviews a month. It does not
currently do meaningful traffic at all. Our share of tip-jar money is zero.

## Why it is the wrong product for us specifically

Charging for crawls is a strategy for someone whose problem is that AI takes their
readers. That is the newspaper problem: a reader who gets the answer from ChatGPT
never visits, so the crawl is a pure loss and a toll is the only way to be paid.

Our problem is the exact opposite one. Nobody knows this site exists. Being copied
into a training set or a retrieval index is not our loss, it is the only
distribution channel we have that does not require outranking Wikipedia. We
published bulk dumps, an MCP server and an open search API precisely to make taking
the data cheap. Putting a 402 in front of that would be paying to un-build it.

There is also a real risk, not a theoretical one: the crawlers most likely to *pay*
are the well-behaved ones that identify themselves and sign their requests — the
exact crawlers we want. The ones that would route around a toll with residential
proxies are the ones we do not care about either way. A toll filters out the good
traffic and keeps the bad.

And the money would be, at our volume, cents.

## What we should watch instead

- **Pay Per Use** (payment on citation, not on fetch). If that ever goes generally
  available and pays real money, it is *aligned* with us rather than against us —
  we would be paid for being quoted, which is what we already want to happen. Worth
  re-checking when it leaves experiment status. Not now.
- **RSL (Really Simple Licensing)** — an open standard, launched 10 September 2025,
  backed by ~1,500 organisations including Reddit, Yahoo, the AP and Medium, that
  embeds licensing terms in robots.txt. It is free and it is a declaration, not a
  fence. If it gets real adoption, the version of it we would publish says "free for
  any use, attribute the revision id" — the same thing we already say. Cheap to add
  later; adds nothing today.
- **TollBit, ScalePost, ProRata** — third-party licensing brokers. All live. All
  built for publishers with an audience to defend. TollBit is the most mature.
  None of them are for us.

## The one Cloudflare change that does affect us

Buried in the same 1 July 2026 announcement: from **15 September 2026** Cloudflare
begins blocking "mixed-use" AI crawlers **by default** on new domains, new customers
and **all free-tier zones**. slashyear.com is a free zone.

That is the real action item out of this research, and it has nothing to do with
getting paid. It is handled — see `CRAWLER-ACCESS.md` and
`tools/crawlguard.py`, which checks and repairs the site's openness every
day at 06:40 UTC.

## Could not verify
- Whether a free-plan site can enable pay per crawl at all; the docs are silent.
- Any real named-publisher payout, in any amount.
- Whether the price floor is $0.001 (docs) or $0.01 (secondary sources). Docs win.
