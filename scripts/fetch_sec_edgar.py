"""
Counts today's 8-K filings per company via SEC EDGAR's official, documented
submissions API (data.sec.gov). No API key needed, but SEC requires a
descriptive User-Agent with contact info -- set SEC_CONTACT_EMAIL or edit
the default below before running this at any real volume.

This does NOT tell you what an 8-K says (that needs the full-text search
API or downloading the filing itself) -- it's a pure daily count, useful
as a "did something material happen today" signal.
"""
import os
import requests

CONTACT_EMAIL = os.environ.get("SEC_CONTACT_EMAIL", "set-SEC_CONTACT_EMAIL-env-var@example.com")
HEADERS = {"User-Agent": f"AI Capex Tracker ({CONTACT_EMAIL})"}

_CIK_MAP_CACHE = None


def get_cik_map() -> dict:
    global _CIK_MAP_CACHE
    if _CIK_MAP_CACHE is not None:
        return _CIK_MAP_CACHE
    resp = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    _CIK_MAP_CACHE = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in raw.values()}
    return _CIK_MAP_CACHE


def fetch_all(companies: list[dict], today_str: str) -> dict:
    """today_str: 'YYYY-MM-DD', matched against SEC's filingDate field."""
    results = {}
    try:
        cik_map = get_cik_map()
    except Exception as e:
        print(f"[sec] failed to load ticker->CIK map: {e}")
        return results

    for c in companies:
        cik = cik_map.get(c["ticker"])
        if not cik:
            print(f"[sec] no CIK found for {c['ticker']}, skipping")
            continue
        try:
            resp = requests.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=HEADERS, timeout=30,
            )
            resp.raise_for_status()
            recent = resp.json().get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            count_today = sum(1 for f, d in zip(forms, dates) if f == "8-K" and d == today_str)
            results[c["ticker"]] = {"sec_8k_filings_today": count_today}
        except Exception as e:
            print(f"[sec] failed for {c['ticker']}: {e}")
    return results
