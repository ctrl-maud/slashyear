#!/usr/bin/env python3
"""prices.py — what a year cost, and how many people were alive in it.

The year pages quote Wikipedia, and to a search engine or a model that makes them a copy
of a page that already ranks. The questions people actually put to a year ("what did gas
cost in 1985", "what is $100 from 1970 worth now") are answered by none of those quotes.
They are answered by public statistical series, so this pulls those series from their
publishers, keeps the series id next to every number, and writes one file the site and
the API read.

  - Prices: U.S. Bureau of Labor Statistics, via FRED. CPI-U back to 1913; BLS average
    retail prices for staple goods from 1976-1995 onward. Public domain.
  - Population: Our World in Data's world population series (HYDE + UN WPP), CC BY 4.0.

Annual figures are the mean of the year's monthly (or quarterly) observations. A year
missing more than one month is left out rather than averaged short (one month is allowed:
the 2025 shutdown cancelled October's collection, so 2025 has eleven). The current figure
is the latest observation and is labelled with its month.

Usage:
  prices.py [--out data/extras/prices.json]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UA = "slashyear-build/1.0 (https://slashyear.com)"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
OWID = "https://ourworldindata.org/grapher/population.csv?country=~OWID_WRL"

ITEMS = [
    # id, series, label, unit, frequency
    ("gas", "APU000074714", "Gallon of regular gasoline", "gallon", "monthly"),
    ("eggs", "APU0000708111", "Dozen large eggs", "dozen", "monthly"),
    ("bread", "APU0000702111", "Pound of white bread", "pound", "monthly"),
    ("milk", "APU0000709112", "Gallon of whole milk", "gallon", "monthly"),
    ("beef", "APU0000703112", "Pound of ground beef", "pound", "monthly"),
    ("coffee", "APU0000717311", "Pound of ground coffee", "pound", "monthly"),
    ("bananas", "APU0000711211", "Pound of bananas", "pound", "monthly"),
    ("electricity", "APU000072610", "Kilowatt-hour of electricity", "kWh", "monthly"),
    ("house", "MSPUS", "Median price of a new house sold", "house", "quarterly"),
    ("income", "MEHOINUSA646N", "Median household income", "year", "annual"),
    ("minwage", "STTMINWGFG", "Federal minimum wage", "hour", "annual"),
]
NAMES = {
    "CPIAUCNS": "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
    "APU000074714": "Average Price: Gasoline, Unleaded Regular (Cost per Gallon/3.785 Liters)",
    "APU0000708111": "Average Price: Eggs, Grade A, Large (Cost per Dozen)",
    "APU0000702111": "Average Price: Bread, White, Pan (Cost per Pound/453.6 Grams)",
    "APU0000709112": "Average Price: Milk, Fresh, Whole, Fortified (Cost per Gallon/3.8 Liters)",
    "APU0000703112": "Average Price: Ground Beef, 100% Beef (Cost per Pound/453.6 Grams)",
    "APU0000717311": "Average Price: Coffee, 100%, Ground Roast, All Sizes (Cost per Pound/453.6 Grams)",
    "APU0000711211": "Average Price: Bananas (Cost per Pound/453.6 Grams)",
    "APU000072610": "Average Price: Electricity per Kilowatt-Hour",
    "MSPUS": "Median Sales Price of Houses Sold for the United States",
    "MEHOINUSA646N": "Median Household Income in the United States (current dollars)",
    "STTMINWGFG": "Federal Minimum Hourly Wage for Nonfarm Workers for the United States",
}
PUBLISHER = {
    "MSPUS": "U.S. Census Bureau and U.S. Department of Housing and Urban Development",
    "MEHOINUSA646N": "U.S. Census Bureau",
    "STTMINWGFG": "U.S. Department of Labor",
}


def fetch(url: str) -> str:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 + attempt * 3)
    raise RuntimeError(url)


def series(sid: str) -> list[tuple[str, float]]:
    text = fetch(FRED + sid)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or rows[0][0] != "observation_date":
        raise RuntimeError(f"{sid}: not a FRED csv")
    out = []
    for d, v in rows[1:]:
        if v and v != ".":
            out.append((d, float(v)))
    return out


def annual(obs: list[tuple[str, float]], frequency: str) -> dict[int, float]:
    need = {"monthly": 11, "quarterly": 4, "annual": 1}[frequency]
    by: dict[int, list[float]] = {}
    for d, v in obs:
        by.setdefault(int(d[:4]), []).append(v)
    return {y: round(sum(vs) / len(vs), 4) for y, vs in by.items() if len(vs) >= need}


def source(sid: str) -> dict:
    return {
        "series": sid,
        "name": NAMES[sid],
        "publisher": PUBLISHER.get(sid, "U.S. Bureau of Labor Statistics"),
        "url": f"https://fred.stlouisfed.org/series/{sid}",
        "license": "Public domain (U.S. government work)",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "extras", "prices.json"))
    a = ap.parse_args()

    cpi_obs = series("CPIAUCNS")
    cpi = annual(cpi_obs, "monthly")
    latest_d, latest_v = cpi_obs[-1]

    items = []
    for iid, sid, label, unit, freq in ITEMS:
        obs = series(sid)
        years = annual(obs, freq)
        items.append({
            "id": iid, "label": label, "unit": unit, "frequency": freq,
            "years": {str(y): v for y, v in sorted(years.items())},
            "latest": {"date": obs[-1][0], "value": obs[-1][1]},
            "source": source(sid),
        })
        time.sleep(1)

    pop_rows = list(csv.DictReader(io.StringIO(fetch(OWID))))
    population = {r["Year"]: int(float(r["Population"])) for r in pop_rows
                  if r.get("Entity") == "World" and int(r["Year"]) >= 1700}

    doc = {
        "retrieved": dt.date.today().isoformat(),
        "cpi": {
            "years": {str(y): v for y, v in sorted(cpi.items())},
            "latest": {"date": latest_d, "value": latest_v},
            "source": source("CPIAUCNS"),
        },
        "items": items,
        "population": {
            "years": population,
            "source": {
                "name": "Population (HYDE 3.3; Gapminder; UN World Population Prospects)",
                "publisher": "Our World in Data",
                "url": "https://ourworldindata.org/grapher/population",
                "license": "CC BY 4.0",
            },
        },
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"prices.json: CPI {min(cpi)}-{max(cpi)}, {len(items)} items, "
          f"population {min(population)}-{max(population)}, latest CPI {latest_d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
