#!/usr/bin/env python3
"""crawlguard -- keep a Cloudflare site permanently open to AI crawlers.

Why this exists: on 2026-09-06 slashyear.com was serving a robots.txt that said
"Allow: /" from the repo while Cloudflare silently prepended its own managed
robots.txt blocking nine AI crawlers. Nothing in the codebase showed it. On top
of that, Cloudflare announced (2026-07-01) that from 2026-09-15 it would start
blocking "mixed-use" AI crawlers by DEFAULT on free-tier zones. Both are changes
made on Cloudflare's side, to a setting we never touched, that only ever show up
in the live response.

So this checks the three things that can actually be true or false:
  1. the zone's bot_management enforcement switches are all off,
  2. the robots.txt served by the live host allows everything,
  3. a real request carrying each AI crawler's User-Agent gets a real 200.

With --fix it turns any enforcement switch back off and purges robots.txt.
Exit code 0 = open, 1 = something is blocking (or was, and was repaired).

  crawlguard.py --zone <id> --host slashyear.com            # check
  crawlguard.py --zone <id> --host slashyear.com --fix      # check and repair
  crawlguard.py --host slashyear.com --no-api               # probe only, no token
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.cloudflare.com/client/v4"
SECRETS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", ".secrets", "cloudflare.env")

# Every bot_management field that can cause a crawler to be turned away. All of
# them must read "disabled"/False; anything else is a block we did not ask for.
ENFORCEMENT = {
    "ai_bots_protection": "disabled",
    "content_bots_protection": "disabled",
    "crawler_protection": "disabled",
    "ai_training": "disabled",
    "ai_search": "disabled",
    "ai_user": "disabled",
    "is_robots_txt_managed": False,
    "fight_mode": False,
}

# The crawlers worth proving, with the UA string each one really sends.
CRAWLERS = [
    ("GPTBot", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot"),
    ("OAI-SearchBot", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot"),
    ("ChatGPT-User", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"),
    ("ClaudeBot", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ClaudeBot/1.0; +claudebot@anthropic.com"),
    ("Claude-User", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-User/1.0; +Claude-User@anthropic.com"),
    ("Claude-SearchBot", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-SearchBot/1.0; +Claude-SearchBot@anthropic.com"),
    ("PerplexityBot", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot"),
    ("Perplexity-User", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user"),
    ("Googlebot", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    ("Google-Extended", "Google-Extended"),
    ("GoogleOther", "Mozilla/5.0 (compatible; GoogleOther)"),
    ("Bingbot", "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"),
    ("Applebot", "Mozilla/5.0 (compatible; Applebot/0.1; +http://www.apple.com/go/applebot)"),
    ("Applebot-Extended", "Applebot-Extended"),
    ("CCBot", "CCBot/2.0 (https://commoncrawl.org/faq/)"),
    ("Bytespider", "Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)"),
    ("Amazonbot", "Mozilla/5.0 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)"),
    ("meta-externalagent", "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"),
    ("cohere-ai", "cohere-ai"),
    ("MistralAI-User", "MistralAI-User/1.0"),
    ("AI2Bot", "Mozilla/5.0 (compatible) AI2Bot (+https://www.allenai.org/crawler)"),
    ("YouBot", "Mozilla/5.0 (compatible; YouBot (+http://www.you.com))"),
    ("DuckAssistBot", "DuckAssistBot/1.0; (+http://duckduckgo.com/duckassistbot.html)"),
    ("Diffbot", "Mozilla/5.0 (compatible; Diffbot/0.1; +http://www.diffbot.com)"),
    ("omgili", "omgili/0.5 +http://omgili.com"),
    ("Timpibot", "Mozilla/5.0 (compatible; Timpibot/0.9; +http://www.timpi.io)"),
    ("FirecrawlAgent", "Mozilla/5.0 (compatible; FirecrawlAgent)"),
    ("plain-script", "python-requests/2.32.0"),
]

# Paths that together prove the whole surface is reachable, not just the shell.
PATHS = ["/", "/robots.txt", "/llms.txt", "/sitemap.xml",
         "/api/search?q=moon+landing&limit=2", "/dump/datapackage.json"]

# A body that is a Cloudflare interstitial rather than the page. A 200 that says
# one of these is a block wearing a success code, which is the failure mode that
# a plain status-code check misses.
INTERSTITIAL = ("just a moment", "enable javascript and cookies",
                "cf-browser-verification", "attention required",
                "checking your browser", "verify you are human")


def load_token() -> str | None:
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        return os.environ["CLOUDFLARE_API_TOKEN"]
    if os.path.exists(SECRETS):
        for line in open(SECRETS, encoding="utf-8"):
            line = line.strip()
            if line.startswith("CLOUDFLARE_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return None


def cf(token: str, path: str, method: str = "GET", body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API}/{path}", method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def probe(host: str, name: str, ua: str, path: str) -> tuple[str, str, int, str]:
    """One request. Returns (crawler, path, status, note) -- note is '' when clean."""
    url = f"https://{host}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": ua,
                                               "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            head = r.read(4096).decode("utf-8", "replace").lower()
            hit = next((s for s in INTERSTITIAL if s in head), "")
            return name, path, r.status, f"interstitial:{hit}" if hit else ""
    except urllib.error.HTTPError as e:
        return name, path, e.code, "http-error"
    except Exception as e:                                   # DNS, TLS, timeout
        return name, path, 0, type(e).__name__


def read_robots(host: str) -> tuple[str, list[str]]:
    """The live robots.txt and every Disallow rule in it. Read off the host,
    never off the build -- the managed-robots block only exists on the wire."""
    try:
        req = urllib.request.Request(f"https://{host}/robots.txt",
                                     headers={"User-Agent": "crawlguard/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode("utf-8", "replace")
    except Exception as e:
        return "", [f"unreadable: {e}"]
    bad = [ln.strip() for ln in txt.splitlines()
           if ln.strip().lower().startswith("disallow:")
           and ln.split(":", 1)[1].strip()]
    if "ai-train=no" in txt or "ai-input=no" in txt:
        bad.append("Content-Signal says no to AI use")
    return txt, bad


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prove a Cloudflare site is open to every AI crawler, and repair it if not.")
    ap.add_argument("--host", default="slashyear.com", help="hostname to probe")
    ap.add_argument("--zone", default="9d4c5ff1104c52873515cb86487cfbf5",
                    help="Cloudflare zone id to read/repair settings on")
    ap.add_argument("--fix", action="store_true",
                    help="turn any enforcement switch back off and purge robots.txt")
    ap.add_argument("--no-api", action="store_true",
                    help="probe the live host only; do not talk to the Cloudflare API")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--quiet", action="store_true",
                    help="print nothing when everything is open (for cron)")
    a = ap.parse_args()

    problems: list[str] = []
    repaired: list[str] = []
    settings: dict = {}

    # 1. the switches
    token = None if a.no_api else load_token()
    if token:
        r = cf(token, f"zones/{a.zone}/bot_management")
        if r.get("success"):
            settings = r["result"]
            wrong = {k: settings.get(k) for k, want in ENFORCEMENT.items()
                     if k in settings and settings[k] != want}
            if wrong:
                problems += [f"bot_management.{k} = {v!r} (want {ENFORCEMENT[k]!r})"
                             for k, v in wrong.items()]
                if a.fix:
                    fix = cf(token, f"zones/{a.zone}/bot_management", "PUT",
                             {k: ENFORCEMENT[k] for k in wrong})
                    if fix.get("success"):
                        repaired += [f"bot_management.{k} -> {ENFORCEMENT[k]!r}" for k in wrong]
                        settings = fix["result"]
                        cf(token, f"zones/{a.zone}/purge_cache", "POST",
                           {"files": [f"https://{a.host}/robots.txt"]})
                        repaired.append("purged /robots.txt from cache")
                    else:
                        problems.append(f"repair failed: {fix.get('errors')}")
        else:
            problems.append(f"cannot read bot_management: {r.get('errors')}")
    elif not a.no_api:
        problems.append("no Cloudflare token found; ran probe-only")

    # 2. the live robots.txt
    robots, disallows = read_robots(a.host)
    problems += [f"robots.txt: {d}" for d in disallows]

    # 3. the actual requests
    jobs = [(n, ua, p) for n, ua in CRAWLERS for p in PATHS]
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda j: probe(a.host, *j), jobs))
    blocked = [(n, p, s, note) for n, p, s, note in results
               if s != 200 or note]
    problems += [f"{n} {p} -> {s} {note}".strip() for n, p, s, note in blocked]

    ok = not problems
    if a.json:
        print(json.dumps({"host": a.host, "open": ok, "checks": len(results),
                          "settings": settings, "problems": problems,
                          "repaired": repaired}, indent=2))
    elif not (a.quiet and ok and not repaired):
        print(f"crawlguard {a.host}: {len(results)} live requests "
              f"({len(CRAWLERS)} crawlers x {len(PATHS)} paths)")
        for line in repaired:
            print("  REPAIRED", line)
        if ok:
            print("  OPEN - every crawler got a real 200, robots.txt allows all, "
                  "no Cloudflare enforcement switch is on")
        else:
            for line in problems:
                print("  BLOCKED", line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
