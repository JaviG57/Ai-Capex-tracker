"""
Actual quarterly capital expenditure from SEC XBRL -- the primary measure of
whether AI capex is accelerating or decelerating.

Everything else this project tracks (job postings, 8-K counts, share prices,
commits) is a PROXY. This is the real number companies report: cash paid for
property, plant and equipment, which is what data centres, chips, land and
power actually cost.

Four complications the probe (scripts/probe_capex.py) exposed, all handled:

1. Companies switch tags. Amazon and NVIDIA both moved from
   PaymentsToAcquirePropertyPlantAndEquipment to PaymentsToAcquireProductiveAssets;
   picking the tag with the most data points returns figures from 2017. We
   therefore pick the tag with the most RECENT quarterly data.
2. Cash-flow figures are often year-to-date. A "6mo" value at Q2 is H1
   cumulative, not the quarter. We prefer true 3-month entries and derive the
   quarter by differencing consecutive YTD values when that's all there is.
3. Amended filings repeat a period. We keep the most recently filed value.
4. Not everyone reports in USD (ASML in EUR, TSMC in TWD). The unit is stored
   alongside, and growth rates -- which are currency-neutral -- are what the
   dashboard compares across companies.

Quarterly by nature, so it's cached and refreshed cheaply each day.
Output: data/capex.json
"""
import json
import os
import pathlib
import time
from datetime import date

import requests

HDRS = {"User-Agent": f"AI Capex Tracker ({os.environ.get('SEC_CONTACT_EMAIL', 'x@example.com')})"}
CACHE = pathlib.Path(__file__).resolve().parent.parent / "data" / "capex.json"

CAPEX_TAGS = [
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquirePropertyPlantAndEquipmentExcludingFinanceLease",
    "PaymentsForCapitalImprovements",
    "PaymentsToDevelopRealEstateAssets",
    "PaymentsToAcquireRealEstate",
    "PaymentsToAcquireCommercialRealEstate",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    "PaymentsToAcquireBuildings",
    "PaymentsToAcquireMachineryAndEquipment",
    "PurchaseOfPropertyPlantAndEquipment",
    "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
]


def _days(e):
    return (date.fromisoformat(e["end"]) - date.fromisoformat(e["start"])).days


def _companyfacts(cik, retries=3):
    for i in range(retries):
        try:
            r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                             headers=HDRS, timeout=120)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    return None


def _collect(facts):
    """Return {tag_key: {unit: [entries]}} for every capex-ish tag present."""
    found = {}
    for tax, tags in facts.get("facts", {}).items():
        for tag in CAPEX_TAGS:
            node = tags.get(tag)
            if not node:
                continue
            for unit, entries in node.get("units", {}).items():
                rows = [e for e in entries if e.get("start") and e.get("end")]
                if rows:
                    found.setdefault(f"{tax}:{tag}", {})[unit] = rows
    return found


def _quarterly_from(rows):
    """Build {end_date: value} of TRUE quarterly figures.
    Prefers native 3-month entries; derives the rest by differencing
    year-to-date values within a fiscal year."""
    best = {}
    for e in rows:  # amended filings repeat periods -- keep the latest filed
        key = (e["start"], e["end"])
        if key not in best or (e.get("filed", "") > best[key].get("filed", "")):
            best[key] = e
    rows = list(best.values())

    quarterly = {}
    for e in rows:
        if 80 <= _days(e) <= 100:
            quarterly[e["end"]] = e["val"]

    # Fill gaps by differencing cumulative values that share a period start.
    # The chain must include the 3-month entry (Q2 = H1 - Q1), so group by
    # start date rather than only looking at entries longer than a quarter.
    by_start = {}
    for e in rows:
        by_start.setdefault(e["start"], []).append((e["end"], e["val"], _days(e)))
    for start, items in by_start.items():
        items.sort(key=lambda x: x[2])
        for i, (end, val, d) in enumerate(items):
            if end in quarterly:
                continue
            if i == 0:
                if 80 <= d <= 100:
                    quarterly[end] = val
            else:
                prev_end, prev_val, prev_d = items[i - 1]
                if 80 <= (d - prev_d) <= 100:
                    quarterly[end] = val - prev_val
    return quarterly


def extract_capex(facts):
    """Choose the tag whose quarterly series runs most recently, not the one
    with the most history -- that's what catches Amazon's and NVIDIA's switch."""
    candidates = []
    for tag_key, units in _collect(facts).items():
        for unit, rows in units.items():
            q = _quarterly_from(rows)
            if q:
                candidates.append({"tag": tag_key, "unit": unit, "quarters": q,
                                   "latest": max(q)})
    if not candidates:
        return None
    best = max(candidates, key=lambda c: (c["latest"], len(c["quarters"])))
    series = sorted(best["quarters"].items())[-13:]
    return {"tag": best["tag"], "unit": best["unit"],
            "quarters": [{"end": k, "value": v} for k, v in series]}


def fetch_all(companies, cik_map) -> dict:
    out = {}
    for c in companies:
        t = c["ticker"]
        cik = cik_map.get(t)
        if not cik:
            continue
        try:
            data = extract_capex(_companyfacts(cik))
            if not data:
                print(f"[capex] {t:6} no usable capex tag")
                out[t] = {"error": "no_tag"}
                continue
            qs = data["quarters"]
            latest = qs[-1]
            yoy = None
            if len(qs) >= 5 and qs[-5]["value"]:
                yoy = round((latest["value"] - qs[-5]["value"]) / abs(qs[-5]["value"]) * 100, 1)
            qoq = None
            if len(qs) >= 2 and qs[-2]["value"]:
                qoq = round((latest["value"] - qs[-2]["value"]) / abs(qs[-2]["value"]) * 100, 1)
            out[t] = {**data, "latest_end": latest["end"], "latest_value": latest["value"],
                      "yoy_pct": yoy, "qoq_pct": qoq,
                      "checked_at": date.today().isoformat()}
            unit = data["unit"]
            print(f"[capex] {t:6} {latest['end']} {latest['value']/1e9:>8.2f}B {unit} "
                  f"QoQ={qoq}% YoY={yoy}%  ({data['tag'].split(':')[1][:38]})")
        except Exception as e:
            print(f"[capex] {t:6} FAILED {e}")
            out[t] = {"error": str(e)[:120]}
        time.sleep(0.25)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    import companies as cm, fetch_sec_edgar
    fetch_all(cm.COMPANIES, fetch_sec_edgar.get_cik_map())
