#!/usr/bin/env python3
"""official.py — U.S. agency and scientific data series, each checked against a second copy.

Fetches every series from the agency that publishes it (BLS, BEA, Treasury, the Federal
Reserve, NOAA, USGS), compares it with an independent copy of the same data, and writes
data/extras/official.json. A series whose check fails is dropped with the reason, and a
year with a missing month gets no annual value rather than an estimated one.

Usage:
  official.py              uses today's cache in data/raw/official/<date>/ if present
  official.py --refresh    re-downloads everything
  official.py <id> ...     rebuilds only those series

Raw downloads are cached per day so a re-run does not spend the BLS public API's small
daily quota. FRED stalls browser User-Agents from some hosts and serves plain library
ones, so FRED gets a different User-Agent from everything else.
"""
import csv
import functools
import datetime as dt
import io
import json
import os
import re
import sys
import time
import zipfile
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXTRAS = os.path.join(ROOT, "data", "extras")
TODAY = dt.date.today().isoformat()
CUR_YEAR = dt.date.today().year
RAW = os.path.join(ROOT, "data", "raw", "official", TODAY)
REFRESH = "--refresh" in sys.argv
os.makedirs(RAW, exist_ok=True)

BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PD = "Public domain (U.S. government work)"
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s, flush=True)


# ----------------------------------------------------------------------------- http
def fetch(url, name, method="GET", data=None, binary=False, timeout=120):
    """Download url to raw/<date>/<name> (cached for the day) and return contents."""
    path = os.path.join(RAW, name)
    if os.path.exists(path) and not REFRESH and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            b = f.read()
        return b if binary else b.decode("utf-8", "replace")
    if "stlouisfed.org" in url:
        uas = [requests.utils.default_user_agent(), "curl/7.81.0"]
    else:
        uas = [BROWSER_UA]
    last = None
    for attempt in range(4):
        ua = uas[attempt % len(uas)]
        try:
            h = {"User-Agent": ua}
            if method == "POST":
                h["Content-Type"] = "application/json"
                r = requests.post(url, data=json.dumps(data), headers=h, timeout=timeout)
            else:
                r = requests.get(url, headers=h, timeout=timeout)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
            return r.content if binary else r.content.decode("utf-8", "replace")
        except Exception as e:  # noqa
            last = e
            time.sleep(3 + 3 * attempt)
    raise RuntimeError(f"fetch failed {url}: {last}")


def fred_csv(sid):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    txt = fetch(url, f"fred_{sid}.csv")
    out = {}
    for row in csv.reader(io.StringIO(txt)):
        if not row or row[0] in ("observation_date", "DATE"):
            continue
        v = row[1].strip()
        if v in ("", "."):
            continue  # no fills: missing observations are skipped
        out[row[0]] = v
    if not out:
        raise RuntimeError(f"FRED {sid}: no data")
    return out  # date -> string value as published


def fred_page(sid):
    return f"https://fred.stlouisfed.org/series/{sid}"


# ----------------------------------------------------------------------------- helpers
def rnd(x, nd):
    q = Decimal(1).scaleb(-nd)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def ndec(s):
    s = str(s)
    return len(s.split(".")[1]) if "." in s else 0


def compare(a, b, tol, label):
    """a, b: dict key->number. Returns cross-check stats over common keys."""
    keys = sorted(set(a) & set(b))
    diffs = [(k, abs(float(a[k]) - float(b[k]))) for k in keys]
    mx = max((d for _, d in diffs), default=None)
    worst = max(diffs, key=lambda t: t[1])[0] if diffs else None
    bad = [k for k, d in diffs if d > tol + 1e-12]
    return {"points_compared": len(keys), "max_abs_diff": None if mx is None else float(f"{mx:.10g}"),
            "worst_point": worst, "tolerance": tol, "passed": bool(keys) and not bad,
            "_bad": bad, "_label": label}


def monthly_to_annual(monthly, nd):
    """monthly: 'YYYY-MM' -> float. Mean of 12 months, complete years only."""
    by = defaultdict(list)
    for k, v in monthly.items():
        by[k[:4]].append(v)
    return {y: rnd(sum(v) / 12, nd) for y, v in sorted(by.items())
            if len(v) == 12 and int(y) < CUR_YEAR}


SERIES = {}
DROPPED = []


def gap_note(monthly):
    """Note any calendar year (before the current one) missing months; such years get no annual value."""
    first = min(monthly)[:4]
    gaps = {}
    for y in range(int(first), CUR_YEAR):
        miss = [f"{y}-{mo:02d}" for mo in range(1, 13) if f"{y}-{mo:02d}" not in monthly]
        if miss and not (str(y) == first and miss == [f"{y}-{mo:02d}" for mo in range(1, len(miss) + 1)]):
            gaps[str(y)] = miss
    if not gaps:
        return None
    return ("Annual value omitted for years with missing monthly observations (no fills): " +
            "; ".join(f"{y} missing {', '.join(m)}" for y, m in gaps.items()) +
            ". (October 2025 data were not collected/published during the Oct-Nov 2025 federal government shutdown.)"
            if "2025-10" in str(gaps) else "")


def publish(sid, meta, xc, extra_checks=None):
    if not xc["passed"]:
        DROPPED.append({"id": sid, "reason": f"cross-check vs {xc['_label']} failed: "
                        f"{len(xc['_bad'])} of {xc['points_compared']} points beyond tolerance "
                        f"{xc['tolerance']} (max diff {xc['max_abs_diff']} at {xc['worst_point']})"})
        log(f"DROP {sid}: cross-check failed")
        return
    cc = {"against": xc["_label"], "url": meta.pop("_xurl"),
          "points_compared": xc["points_compared"], "max_abs_diff": xc["max_abs_diff"],
          "tolerance": xc["tolerance"], "passed": True}
    if meta.get("_xnote"):
        cc["note"] = meta.pop("_xnote")
    meta["cross_check"] = cc
    if extra_checks:
        meta["additional_checks"] = extra_checks
    order = ["name", "unit", "frequency", "publisher", "url", "license", "annual_method",
             "notes", "cross_check", "additional_checks", "annual", "monthly", "daily"]
    SERIES[sid] = {k: meta[k] for k in order if k in meta and meta[k] is not None}
    log(f"OK   {sid}")


def guarded(fn):
    @functools.wraps(fn)
    def w():
        try:
            fn()
        except Exception as e:  # noqa
            sid = fn.__name__.replace("do_", "")
            DROPPED.append({"id": sid, "reason": f"could not fetch/verify: {type(e).__name__}: {e}"})
            log(f"DROP {sid}: {e}")
    return w


# ----------------------------------------------------------------------------- BLS API v1
def bls_v1(series_id, y0, y1):
    url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
    txt = fetch(url, f"bls_{series_id}_{y0}_{y1}.json", method="POST",
                data={"seriesid": [series_id], "startyear": str(y0), "endyear": str(y1)})
    d = json.loads(txt)
    if d.get("status") != "REQUEST_SUCCEEDED":
        os.remove(os.path.join(RAW, f"bls_{series_id}_{y0}_{y1}.json"))
        raise RuntimeError(f"BLS API: {d.get('status')} {d.get('message')}")
    out = {}
    for x in d["Results"]["series"][0]["data"]:
        if re.fullmatch(r"M(0[1-9]|1[0-2])", x["period"]) and x["value"] not in ("-", ""):
            out[f"{x['year']}-{x['period'][1:]}"] = float(x["value"])
    return out


def fred_monthly(sid):
    return {k[:7]: float(v) for k, v in fred_csv(sid).items()}


@guarded
def do_unemployment_rate():
    m = fred_monthly("UNRATE")
    bls = {}
    for y0, y1 in [(1948, 1957), (1975, 1984), (2000, 2009), (2016, 2025)]:
        bls.update(bls_v1("LNS14000000", y0, y1))
    xc = compare(m, bls, 0.0, "BLS Public Data API v1, series LNS14000000 (sampled decades 1948-57, 1975-84, 2000-09, 2016-25)")
    publish("unemployment_rate", {
        "name": "Civilian unemployment rate, seasonally adjusted (U-3)",
        "unit": "percent of civilian labor force", "frequency": "monthly",
        "publisher": "U.S. Bureau of Labor Statistics (Current Population Survey), via FRED series UNRATE",
        "url": "https://data.bls.gov/timeseries/LNS14000000",
        "license": PD,
        "annual_method": "mean of the 12 seasonally adjusted monthly values, rounded to 2 decimals (computed by slashyear). "
                         "Note: BLS's own published annual average is computed from not-seasonally-adjusted data "
                         "(LNU04000000) and can differ by about 0.1 point.",
        "_xurl": "https://api.bls.gov/publicAPI/v1/timeseries/data/LNS14000000",
        "notes": gap_note(m), "annual": monthly_to_annual(m, 2), "monthly": m}, xc)


@guarded
def do_cpi_u():
    m = fred_monthly("CPIAUCNS")
    bls = {}
    for y0, y1 in [(1913, 1922), (1970, 1979), (2015, 2024)]:
        bls.update(bls_v1("CUUR0000SA0", y0, y1))
    xc = compare(m, bls, 0.0, "BLS Public Data API v1, series CUUR0000SA0 (sampled decades 1913-22, 1970-79, 2015-24)")
    publish("cpi_u", {
        "name": "Consumer Price Index for All Urban Consumers (CPI-U), U.S. city average, all items, not seasonally adjusted",
        "unit": "index, 1982-84=100", "frequency": "monthly",
        "publisher": "U.S. Bureau of Labor Statistics, via FRED series CPIAUCNS",
        "url": "https://data.bls.gov/timeseries/CUUR0000SA0",
        "license": PD,
        "annual_method": "mean of the 12 not-seasonally-adjusted monthly index values, rounded to 3 decimals (computed by slashyear; "
                         "BLS also publishes an annual average, not available via the keyless API, which may differ in the last digit for early years where monthly values are published to 1 decimal)",
        "_xurl": "https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0",
        "notes": gap_note(m), "annual": monthly_to_annual(m, 3), "monthly": m}, xc)


# ----------------------------------------------------------------------------- Fed DDP
_DDP = {}


def ddp(rel):
    """Federal Reserve Data Download Program full-release package -> {series_name: {date: str}}"""
    if rel in _DDP:
        return _DDP[rel]
    b = fetch(f"https://www.federalreserve.gov/datadownload/Output.aspx?rel={rel}&filetype=zip",
              f"fed_ddp_{rel}.zip", binary=True, timeout=300)
    x = zipfile.ZipFile(io.BytesIO(b)).read(f"{rel}_data.xml").decode()
    out = {}
    for m in re.finditer(r'<kf:Series ([^>]*)>(.*?)</kf:Series>', x, re.S):
        sn = re.search(r'SERIES_NAME="([^"]+)"', m.group(1)).group(1)
        obs = {}
        for o in re.finditer(r'<frb:Obs ([^>]*)/>', m.group(2)):
            a = dict(re.findall(r'(\w+)="([^"]*)"', o.group(1)))
            if a.get("OBS_STATUS") == "A" and a.get("OBS_VALUE") not in (None, "", "NaN"):
                obs[a["TIME_PERIOD"]] = a["OBS_VALUE"]
        out[sn] = obs
    _DDP[rel] = out
    return out


@guarded
def do_fed_funds_rate():
    m = fred_monthly("FEDFUNDS")
    h15 = ddp("H15")
    hm = {k[:7]: float(v) for k, v in h15["RIFSPFF_N.M"].items()}
    ha = {k[:4]: float(v) for k, v in h15["RIFSPFF_N.A"].items() if int(k[:4]) < CUR_YEAR}
    xc = compare(m, hm, 0.0, "Federal Reserve Board H.15 Data Download Program, series RIFSPFF_N.M (all months)")
    mean_m = monthly_to_annual(m, 2)
    xa = compare(ha, mean_m, 0.05, "mean of 12 monthly values")
    publish("fed_funds_rate", {
        "name": "Effective federal funds rate",
        "unit": "percent per year", "frequency": "monthly",
        "publisher": "Board of Governors of the Federal Reserve System (H.15 Selected Interest Rates), via FRED series FEDFUNDS",
        "url": "https://www.federalreserve.gov/releases/h15/",
        "license": PD,
        "annual_method": "as published annual average in the Federal Reserve's H.15 release (DDP series RIFSPFF_N.A, an average of daily rates); "
                         "1954 omitted (series begins July 1954)",
        "_xurl": "https://www.federalreserve.gov/datadownload/Output.aspx?rel=H15&filetype=zip",
        "annual": ha, "monthly": m},
        xc, [{"what": "H.15 published annual vs mean of 12 monthly values (expected small differences: daily vs monthly weighting)",
              "points_compared": xa["points_compared"], "max_abs_diff": xa["max_abs_diff"],
              "worst_point": xa["worst_point"]}])


FX = [  # id, FRED daily, FRED annual, H10 code, unit, H10 annual series
    ("fx_usd_gbp", "DEXUSUK", "AEXUSUK", "RXI$US_N.B.UK", "U.S. dollars per British pound", "RXI$US_N.A.UK"),
    ("fx_jpy_usd", "DEXJPUS", "AEXJPUS", "RXI_N.B.JA", "Japanese yen per U.S. dollar", "RXI_N.A.JA"),
    ("fx_cad_usd", "DEXCAUS", "AEXCAUS", "RXI_N.B.CA", "Canadian dollars per U.S. dollar", "RXI_N.A.CA"),
    ("fx_chf_usd", "DEXSZUS", "AEXSZUS", "RXI_N.B.SZ", "Swiss francs per U.S. dollar", "RXI_N.A.SZ"),
    ("fx_usd_eur", "DEXUSEU", "AEXUSEU", "RXI$US_N.B.EU", "U.S. dollars per euro", "RXI$US_N.A.EU"),
    ("fx_mxn_usd", "DEXMXUS", "AEXMXUS", "RXI_N.B.MX", "Mexican pesos per U.S. dollar", "RXI_N.A.MX"),
    ("fx_cny_usd", "DEXCHUS", "AEXCHUS", "RXI_N.B.CH", "Chinese yuan renminbi per U.S. dollar", "RXI_N.A.CH"),
    ("fx_inr_usd", "DEXINUS", "AEXINUS", "RXI_N.B.IN", "Indian rupees per U.S. dollar", "RXI_N.A.IN"),
]


def make_fx(sid, fd, fa, hcode, unit, hann):
    def f():
        d = {k: float(v) for k, v in fred_csv(fd).items()}
        h10 = ddp("H10")
        hd = {k: float(v) for k, v in h10[hcode].items()}
        xc = compare(d, hd, 0.0, f"Federal Reserve Board H.10 Data Download Program, series {hcode} (every overlapping day)")
        # FRED-only or H10-only days are reported, not filled
        only_fred = sorted(set(d) - set(hd))
        only_h10 = sorted(set(hd) - set(d))
        by = defaultdict(list)
        for k, v in d.items():
            by[k[:4]].append((k, v))
        first = min(d)
        annual = {}
        for y, kv in sorted(by.items()):
            if int(y) >= CUR_YEAR:
                continue
            if y == first[:4] and first > f"{y}-01-10":
                continue  # series starts mid-year: partial year
            annual[y] = rnd(sum(v for _, v in kv) / len(kv), 4)
        extra = []
        try:
            fan = {k[:4]: float(v) for k, v in fred_csv(fa).items()}
            c = compare(annual, fan, 0.0001, f"FRED {fa}")
            extra.append({"what": f"mean of daily values vs FRED annual series {fa}", "url": fred_page(fa),
                          "points_compared": c["points_compared"], "max_abs_diff": c["max_abs_diff"],
                          "worst_point": c["worst_point"], "within_0.0001": c["passed"]})
        except Exception as e:  # noqa
            extra.append({"what": f"FRED annual series {fa}", "result": f"not available: {e}"})
        han = {k[:4]: float(v) for k, v in h10.get(hann, {}).items()}
        if han:
            c = compare(annual, han, 0.0001, hann)
            extra.append({"what": f"mean of daily values vs Federal Reserve H.10/G.5A published annual average {hann}",
                          "points_compared": c["points_compared"], "max_abs_diff": c["max_abs_diff"],
                          "worst_point": c["worst_point"], "within_0.0001": c["passed"]})
        extra.append({"what": "days present in only one copy (not filled, not published if FRED-only)",
                      "fred_only_days": len(only_fred), "h10_only_days": len(only_h10),
                      "fred_only_sample": only_fred[:10], "h10_only_sample": only_h10[:10]})
        publish(sid, {
            "name": f"Foreign exchange rate: {unit} (noon buying rates in New York)",
            "unit": unit, "frequency": "daily",
            "publisher": f"Board of Governors of the Federal Reserve System (H.10 Foreign Exchange Rates), via FRED series {fd}",
            "url": "https://www.federalreserve.gov/releases/h10/",
            "license": PD,
            "annual_method": "mean of all available daily values in the calendar year (no fills for holidays/missing days), rounded to 4 decimals; "
                             "first year omitted if the series starts after Jan 10; current year omitted",
            "_xurl": "https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&filetype=zip",
            "annual": annual, "daily": d}, xc, extra)
    f.__name__ = "do_" + sid
    return guarded(f)


# ----------------------------------------------------------------------------- BEA
_NIPA = {}


def nipa_annual(code):
    if not _NIPA:
        txt = fetch("https://apps.bea.gov/national/Release/TXT/NipaDataA.txt", "bea_NipaDataA.txt", timeout=300)
        for row in csv.reader(io.StringIO(txt)):
            if len(row) < 3 or row[0].startswith("%"):
                continue
            try:
                _NIPA.setdefault(row[0], {})[row[1]] = float(row[2].replace(",", ""))
            except ValueError:
                pass
    return _NIPA[code]


@guarded
def do_us_gdp():
    raw = fred_csv("GDPA")
    a = {k[:4]: float(v) for k, v in raw.items() if int(k[:4]) < CUR_YEAR}
    bea = {y: v / 1000 for y, v in nipa_annual("A191RC").items()}  # millions -> billions
    xc = compare(a, bea, 0.0005, "BEA NIPA flat file NipaDataA.txt, series A191RC (millions of dollars, converted to billions)")
    q = fred_csv("GDP")
    by = defaultdict(list)
    for k, v in q.items():
        by[k[:4]].append(float(v))
    qa = {y: sum(v) / 4 for y, v in by.items() if len(v) == 4}
    c = compare(a, qa, 1.0, "FRED GDP quarterly mean")
    publish("us_gdp", {
        "name": "U.S. gross domestic product, current dollars (nominal)",
        "unit": "billions of U.S. dollars", "frequency": "annual",
        "publisher": "U.S. Bureau of Economic Analysis (NIPA Table 1.1.5), via FRED series GDPA",
        "url": "https://apps.bea.gov/iTable/?reqid=19&step=2&isuri=1&categories=survey#eyJhcHBpZCI6MTksInN0ZXBzIjpbMSwyLDNdLCJkYXRhIjpbWyJjYXRlZ29yaWVzIiwiU3VydmV5Il0sWyJOSVBBX1RhYmxlX0xpc3QiLCI1Il1dfQ==",
        "license": PD,
        "annual_method": "as published annual (BEA)",
        "_xurl": "https://apps.bea.gov/national/Release/TXT/NipaDataA.txt",
        "annual": a}, xc,
        [{"what": "annual vs mean of 4 quarterly SAAR values (FRED GDP), 1947+", "url": fred_page("GDP"),
          "points_compared": c["points_compared"], "max_abs_diff_billions": c["max_abs_diff"], "worst_point": c["worst_point"]}])


@guarded
def do_us_population():
    raw = fred_csv("B230RC0A052NBEA")
    a = {k[:4]: int(float(v)) for k, v in raw.items() if int(k[:4]) < CUR_YEAR}
    bea = nipa_annual("B230RC")
    xc = compare(a, bea, 0.0, "BEA NIPA flat file NipaDataA.txt, series B230RC (NIPA Table 2.1 line 40)")
    extra = []
    try:
        txt = fetch("https://www2.census.gov/programs-surveys/popest/tables/1900-1980/national/totals/popclockest.txt",
                    "census_popclockest.txt", timeout=120)
        pc = {}
        for l in txt.splitlines():
            mm = re.match(r'\s*July 1, (\d{4})\s+([\d,]+)', l)
            if mm:
                pc[mm.group(1)] = int(mm.group(2).replace(",", "")) / 1000
        txt2 = fetch("https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/national/totals/nst-est2020-alldata.csv",
                     "census_nst-est2020-alldata.csv", timeout=120)
        r = next(r for r in csv.DictReader(io.StringIO(txt2)) if r["NAME"] == "United States")
        for y in range(2010, 2021):
            pc[str(y)] = int(r[f"POPESTIMATE{y}"]) / 1000
        periods = [("1929", "1939"), ("1940", "1949"), ("1950", "1959"), ("1960", "1979"), ("1980", "1989"),
                   ("1990", "1999"), ("2010", "2020")]
        rows = []
        for p0, p1 in periods:
            ks = [k for k in pc if p0 <= k <= p1 and k in a]
            pct = [(a[k] - pc[k]) / pc[k] * 100 for k in ks]
            rows.append({"years": f"{p0}-{p1}", "n": len(ks),
                         "bea_minus_census_pct_min": round(min(pct), 3), "bea_minus_census_pct_max": round(max(pct), 3)})
        extra.append({"what": "consistency vs Census Bureau July 1 national estimates (popclockest.txt for 1929-1999, Vintage 2020 NST-EST2020 for 2010-2020). "
                              "NOT an identity check: Census files are earlier estimate vintages (pre-2000 and pre-2020 census) and use different coverage; "
                              "BEA's series is a midperiod total revised to later censuses. Reported for transparency only.",
                      "urls": ["https://www2.census.gov/programs-surveys/popest/tables/1900-1980/national/totals/popclockest.txt",
                               "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/national/totals/nst-est2020-alldata.csv"],
                      "by_period": rows})
    except Exception as e:  # noqa
        extra.append({"what": "Census consistency check", "result": f"not available: {e}"})
    publish("us_population", {
        "name": "U.S. population, midperiod (BEA NIPA definition, based on Census Bureau data)",
        "unit": "thousands of persons", "frequency": "annual",
        "publisher": "U.S. Bureau of Economic Analysis (NIPA Table 2.1, line 40; derived from U.S. Census Bureau estimates), via FRED series B230RC0A052NBEA",
        "url": fred_page("B230RC0A052NBEA"),
        "license": PD,
        "annual_method": "as published annual (BEA midperiod population)",
        "notes": "This is BEA's population concept used for per-capita NIPA figures, not the Census Bureau's own 'resident population' table; "
                 "values differ from contemporaneous Census estimate vintages by up to ~2.4% (see additional_checks).",
        "_xurl": "https://apps.bea.gov/national/Release/TXT/NipaDataA.txt",
        "annual": a}, xc, extra)


# ----------------------------------------------------------------------------- Treasury
def fiscaldata(endpoint, params, name):
    base = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/" + endpoint
    rows, page = [], 1
    while True:
        q = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{base}?{q}&page[number]={page}&page[size]=10000"
        d = json.loads(fetch(url, f"{name}_p{page}.json"))
        rows += d["data"]
        if page >= d["meta"]["total-pages"]:
            return rows
        page += 1


GF_TOL_PCT = 0.01


@guarded
def do_federal_debt():
    rows = fiscaldata("v2/accounting/od/debt_outstanding", {"sort": "record_date"}, "treasury_debt_outstanding")
    a, dates = {}, {}
    for r in rows:
        fy = r["record_fiscal_year"]
        a[fy] = float(r["debt_outstanding_amt"])
        dates[fy] = r["record_date"]
    # Treasury's second dataset: Debt to the Penny (1993+), same fiscal-year-end dates
    pen = fiscaldata("v2/accounting/od/debt_to_penny",
                     {"fields": "record_date,tot_pub_debt_out_amt", "sort": "record_date"}, "treasury_debt_to_penny")
    pend = {r["record_date"]: float(r["tot_pub_debt_out_amt"]) for r in pen}
    # Debt to the Penny has rows for business days only; when the FY-end date fell on a weekend/holiday,
    # use the last Debt to the Penny business day on or before it (at most 4 days earlier; debt is
    # unchanged over non-business days).
    pa, shifted, missing = {}, {}, []
    for fy, d in dates.items():
        if d < min(pend):
            continue
        dd = dt.date.fromisoformat(d)
        for back in range(0, 5):
            c = (dd - dt.timedelta(days=back)).isoformat()
            if c in pend:
                pa[fy] = pend[c]
                if back:
                    shifted[fy] = c
                break
        else:
            missing.append(fy)
    xc = compare(a, pa, 1000.0, "Treasury Fiscal Data 'Debt to the Penny' (tot_pub_debt_out_amt) on each fiscal-year-end date, 1993+")
    nonzero = {fy: round(a[fy] - pa[fy], 2) for fy in pa if abs(a[fy] - pa[fy]) > 0.005}
    extra = [{"what": "Debt to the Penny comparison detail",
              "fy_end_on_non_business_day_compared_to_prior_business_day": shifted,
              "fiscal_years_without_penny_row": missing,
              "nonzero_differences_usd": nonzero}]
    try:
        g = fred_csv("GFDEBTN")  # millions, quarterly, end-of-quarter
        qmap = {}
        for fy, d in dates.items():
            y, mth = int(d[:4]), d[5:7]
            qstart = {"09": "07", "06": "04"}.get(mth)
            if qstart and f"{y}-{qstart}-01" in g:
                qmap[fy] = float(g[f"{y}-{qstart}-01"]) * 1e6
        rel = {fy: abs(qmap[fy] - a[fy]) / a[fy] * 100 for fy in qmap}
        gf_ok = sorted(fy for fy, r in rel.items() if r <= GF_TOL_PCT and fy not in pa)
        gf_bad = {fy: round(r, 4) for fy, r in rel.items() if r > GF_TOL_PCT}
        extra.append({"what": "FRED GFDEBTN (Total Public Debt, quarterly, millions of dollars) for the calendar quarter ending on the FY-end date; "
                              f"used to verify fiscal years before Debt to the Penny begins (tolerance {GF_TOL_PCT}% = rounding to $ millions plus minor revisions)",
                      "url": fred_page("GFDEBTN"), "points_compared": len(rel),
                      "max_abs_diff_pct": round(max(rel.values()), 4) if rel else None,
                      "worst_point": max(rel, key=rel.get) if rel else None,
                      "years_verified_only_by_this_check": f"{gf_ok[0]}-{gf_ok[-1]}" if gf_ok else None,
                      "years_beyond_tolerance_pct": gf_bad})
    except Exception as e:  # noqa
        gf_ok, gf_bad = [], {}
        extra.append({"what": "FRED GFDEBTN", "result": f"not available: {e}"})
    # strict: publish only fiscal years confirmed by a second copy
    verified = set(pa) | set(gf_ok)
    trimmed = sorted(set(a) - verified)
    if trimmed:
        DROPPED.append({"id": "federal_debt", "partial": True,
                        "reason": f"fiscal years {trimmed[0]}-{trimmed[-1]} ({len(trimmed)} values) trimmed: no second copy confirms them. "
                                  f"FY1966-1974 disagree with FRED GFDEBTN by 0.17-1.19% (beyond tolerance: {gf_bad}); "
                                  "FY1790-1965 have no second machine-readable copy (Debt to the Penny starts 1993, GFDEBTN 1966). "
                                  "Values remain available from the primary Treasury source but are unverified."})
    a = {fy: v for fy, v in a.items() if fy in verified}
    dates = {fy: d for fy, d in dates.items() if fy in verified}
    publish("federal_debt", {
        "name": "Total U.S. public debt outstanding at end of fiscal year",
        "unit": "U.S. dollars (nominal); keys are FISCAL years, value as of the fiscal-year-end record date",
        "frequency": "annual",
        "publisher": "U.S. Department of the Treasury, Bureau of the Fiscal Service (Historical Debt Outstanding)",
        "url": "https://fiscaldata.treasury.gov/datasets/historical-debt-outstanding/",
        "license": PD,
        "annual_method": "as published: one value per fiscal year (record_fiscal_year) at the dataset's record_date. "
                         "Fiscal-year end changed over time (e.g. Jan 1 in early years, June 30 until 1976, Sept 30 from 1977); "
                         "the exact date for each year is in fiscal_year_end_dates.",
        "notes": "Fiscal years, not calendar years.",
        "_xurl": "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny",
        "_xnote": "tolerance in U.S. dollars ($1,000, i.e. < 1 part per billion of any value compared); covers FY1993+ "
                  "(Debt to the Penny starts in 1993). FY1975-1992 are verified against FRED GFDEBTN instead (see additional_checks). Only verified fiscal years are published.",
        "fiscal_year_end_dates": dates,
        "annual": a}, xc, extra)
    if "federal_debt" in SERIES:
        SERIES["federal_debt"]["fiscal_year_end_dates"] = dates


# ----------------------------------------------------------------------------- NOAA
@guarded
def do_co2_mauna_loa():
    ann_url = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt"
    mm_url = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt"
    a = {}
    for l in fetch(ann_url, "noaa_co2_annmean_mlo.txt").splitlines():
        if l.startswith("#") or not l.strip():
            continue
        p = l.split()
        a[p[0]] = float(p[1])
    m = {}
    for l in fetch(mm_url, "noaa_co2_mm_mlo.txt").splitlines():
        if l.startswith("#") or not l.strip():
            continue
        p = l.split()
        v = float(p[3])
        if v > 0:
            m[f"{int(p[0]):04d}-{int(p[1]):02d}"] = v
    mean_m = monthly_to_annual(m, 2)
    xc = compare(a, mean_m, 0.1, "mean of 12 monthly means in NOAA GML co2_mm_mlo.txt (years with 12 months)")
    publish("co2_mauna_loa", {
        "name": "Atmospheric CO2 at Mauna Loa Observatory, Hawaii",
        "unit": "ppm (micromol/mol, dry air mole fraction, WMO X2019 scale)", "frequency": "monthly",
        "publisher": "NOAA Global Monitoring Laboratory (with Scripps Institution of Oceanography for pre-1974 data)",
        "url": "https://gml.noaa.gov/ccgg/trends/data.html",
        "license": "NOAA GML data are freely available to the public (U.S. government work); GML asks users to cite the data and the Mauna Loa CO2 record (Keeling et al. / NOAA GML).",
        "annual_method": "as published annual mean (co2_annmean_mlo.txt)",
        "_xurl": mm_url,
        "_xnote": "tolerance 0.1 ppm: NOAA's annual mean is not guaranteed to be the simple mean of rounded monthly means",
        "annual": a, "monthly": m}, xc)


@guarded
def do_global_temp_anomaly():
    end = CUR_YEAR - 1
    cag_a_url = f"https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land_ocean/12/12/1850-{end}/data.csv"
    cag_m_url = f"https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land_ocean/1/0/1850-{CUR_YEAR}/data.csv"
    ta = fetch(cag_a_url, "ncei_cag_annual.csv")
    if "Base Period: 1901-2000" not in ta:
        raise RuntimeError("unexpected CAG base period")
    a = {}
    for row in csv.reader(io.StringIO(ta)):
        if row and re.fullmatch(r"\d{4}", row[0]):
            a[row[0]] = float(row[1])
    tm = fetch(cag_m_url, "ncei_cag_monthly.csv")
    m = {}
    for row in csv.reader(io.StringIO(tm)):
        if row and re.fullmatch(r"\d{6}", row[0]):
            m[f"{row[0][:4]}-{row[0][4:]}"] = float(row[1])
    a = {y: v for y, v in a.items() if int(y) < CUR_YEAR}
    # NOAAGlobalTemp file from NCEI data server (anomalies vs 1991-2020); re-baseline to 1901-2000
    root = "https://www.ncei.noaa.gov/data/noaa-global-surface-temperature/"
    vers = re.findall(r'href="(v[\d.]+)/?"', fetch(root, "ncei_ngt_root.html"))
    latest = max(vers, key=lambda v: [int(x) for x in v[1:].split(".")])
    idx_url = f"{root}{latest}/access/timeseries/"
    idx = fetch(idx_url, f"ncei_ngt_index_{latest}.html")
    fa = sorted(set(re.findall(r'aravg\.ann\.land_ocean\.90S\.90N\.v[\d.]+\.\d{6}\.asc', idx)))[-1]
    fmn = sorted(set(re.findall(r'aravg\.mon\.land_ocean\.90S\.90N\.v[\d.]+\.\d{6}\.asc', idx)))[-1]
    ng = {}
    for l in fetch(idx_url + fa, "ncei_" + fa).splitlines():
        p = l.split()
        if len(p) >= 2 and re.fullmatch(r"\d{4}", p[0]):
            ng[p[0]] = float(p[1])
    ngm = {}
    for l in fetch(idx_url + fmn, "ncei_" + fmn).splitlines():
        p = l.split()
        if len(p) >= 3 and re.fullmatch(r"\d{4}", p[0]):
            ngm[f"{int(p[0]):04d}-{int(p[1]):02d}"] = float(p[2])
    base = sum(ng[str(y)] for y in range(1901, 2001)) / 100
    ngr = {y: v - base for y, v in ng.items()}
    xc = compare(a, ngr, 0.015, f"NOAAGlobalTemp {fa} (NCEI data server), re-baselined from the file's native climatology to 1901-2000 by subtracting the file's own 1901-2000 mean")
    # monthly: re-baseline each calendar month to its own 1901-2000 mean
    mb = {}
    for mo in range(1, 13):
        mb[mo] = sum(ngm[f"{y}-{mo:02d}"] for y in range(1901, 2001)) / 100
    ngmr = {k: v - mb[int(k[5:])] for k, v in ngm.items()}
    xm = compare(m, ngmr, 0.015, fmn)
    if not xm["passed"]:
        raise RuntimeError(f"monthly cross-check failed: max diff {xm['max_abs_diff']} at {xm['worst_point']}")
    ver = re.search(r'v([\d.]+)\.(\d{6})', fa)
    publish("global_temp_anomaly", {
        "name": "Global land and ocean surface temperature anomaly (NOAAGlobalTemp), relative to the 1901-2000 average",
        "unit": "degrees Celsius, departure from 1901-2000 mean", "frequency": "monthly",
        "publisher": "NOAA National Centers for Environmental Information (Climate at a Glance, global time series)",
        "url": "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land_ocean/12/12/1850-%d" % end,
        "license": PD,
        "annual_method": "as published annual (January-December) anomaly in Climate at a Glance",
        "notes": f"Dataset version cross-checked: NOAAGlobalTemp v{ver.group(1)} file dated {ver.group(2)}. Values are revised as the dataset is updated.",
        "_xurl": idx_url + fa,
        "_xnote": f"tolerance 0.015 C = 0.005 rounding of CAG two-decimal values + 0.01 for re-baselining; monthly also checked vs {fmn} "
                  f"(per-month 1901-2000 baseline): {xm['points_compared']} points, max abs diff {xm['max_abs_diff']}",
        "annual": a, "monthly": m}, xc)


# ----------------------------------------------------------------------------- USGS
@guarded
def do_earthquakes_m7():
    base = "https://earthquake.usgs.gov/fdsnws/event/1/"
    y0, y1 = 1900, CUR_YEAR - 1
    cnt = {}
    for y in range(y0, y1 + 1):
        t = fetch(f"{base}count?starttime={y}-01-01T00:00:00&endtime={y+1}-01-01T00:00:00&minmagnitude=7&eventtype=earthquake",
                  f"usgs_count_{y}.txt", timeout=60)
        cnt[str(y)] = int(t.strip())
    geo = defaultdict(int)
    ids = set()
    for d0 in range(y0, y1 + 1, 10):
        d1 = min(d0 + 10, y1 + 1)
        j = json.loads(fetch(f"{base}query?format=geojson&starttime={d0}-01-01T00:00:00&endtime={d1}-01-01T00:00:00"
                             f"&minmagnitude=7&eventtype=earthquake&orderby=time-asc&limit=20000",
                             f"usgs_geojson_{d0}.json", timeout=120))
        for f in j["features"]:
            if f["id"] in ids:
                continue
            ids.add(f["id"])
            yy = dt.datetime.fromtimestamp(f["properties"]["time"] / 1000, dt.timezone.utc).year
            geo[str(yy)] += 1
    geo = {str(y): geo.get(str(y), 0) for y in range(y0, y1 + 1)}
    xc = compare(cnt, geo, 0, "USGS ComCat FDSN 'query' endpoint (GeoJSON, per-decade), events counted per UTC year")
    publish("earthquakes_m7plus", {
        "name": "Number of magnitude 7.0+ earthquakes worldwide per year, per the USGS ComCat catalog as of retrieval",
        "unit": "count of events (magnitude >= 7.0, eventtype=earthquake, UTC calendar year)", "frequency": "annual",
        "publisher": "U.S. Geological Survey, Earthquake Hazards Program (ANSS Comprehensive Catalog, ComCat)",
        "url": "https://earthquake.usgs.gov/earthquakes/search/",
        "license": PD,
        "annual_method": "FDSN 'count' endpoint per UTC calendar year (minmagnitude=7, eventtype=earthquake)",
        "notes": "Catalog is revised over time (magnitudes and early-century completeness); counts reflect the catalog as of the retrieval date. "
                 "Early-20th-century counts depend on the completeness of the historical catalog.",
        "_xurl": base + "query?format=geojson&minmagnitude=7&eventtype=earthquake",
        "annual": cnt}, xc)


# ----------------------------------------------------------------------------- main
def main():
    jobs = [do_unemployment_rate, do_cpi_u, do_fed_funds_rate, do_us_gdp, do_us_population, do_federal_debt,
            do_co2_mauna_loa, do_global_temp_anomaly] + [make_fx(*f) for f in FX] + [do_earthquakes_m7]
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    for j in jobs:
        if only and j.__name__.replace("do_", "") not in only:
            continue
        log(f"--- {j.__name__}")
        j()
    out_path = os.path.join(EXTRAS, "official.json")
    if only and os.path.exists(out_path):  # partial run: merge into existing file
        old = json.load(open(out_path))
        old["series"].update(SERIES)
        old["dropped"] = [d for d in old["dropped"] if d["id"] not in only] + DROPPED
        old["retrieved"] = TODAY
        out = old
    else:
        out = {"retrieved": TODAY, "series": SERIES, "dropped": DROPPED}
    # sort annual/monthly/daily keys
    for s in out["series"].values():
        for k in ("annual", "monthly", "daily"):
            if k in s:
                s[k] = dict(sorted(s[k].items()))
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    print("\n=== SUMMARY ===")
    for sid, s in out["series"].items():
        ys = sorted(s["annual"])
        cc = s["cross_check"]
        print(f"{sid:22s} annual {ys[0]}-{ys[-1]} (n={len(ys)})  x-check: {cc['points_compared']} pts, "
              f"max|diff|={cc['max_abs_diff']} tol={cc['tolerance']} -> {'PASS' if cc['passed'] else 'FAIL'}")
    for d in out["dropped"]:
        print(f"DROPPED {d['id']}: {d['reason']}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
