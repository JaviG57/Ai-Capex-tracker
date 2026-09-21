"""
Company headcount from annual SEC filings -- the authoritative anchor.

US companies disclose employee count in the 10-K ("Human Capital" section);
foreign issuers (TSMC, ASML, often Arm) use the 20-F. It's audited-adjacent
and definitive, but only updates once a year, so each value carries an
`as_of` date and the dashboard shows it as such -- never as a daily number.

Method, in order:
  1. XBRL `dei:EntityNumberOfEmployees` from SEC companyfacts, when tagged
     (structured, reliable -- but many US filers don't tag it).
  2. Text extraction from the filing's primary document: find the Human
     Capital / Employees section and pull the headline employee figure.
     The matched sentence is saved as `evidence` so every number can be
     checked by eye rather than trusted blindly.

Caching: keyed by the filing's accession number. A daily run costs one small
metadata request per company; the (multi-MB) filing itself is only
downloaded again when a NEW annual report is filed.

Output: data/headcount_10k.json
"""
import datetime
import html
import json
import os
import pathlib
import re
import time

import requests

CONTACT_EMAIL = os.environ.get("SEC_CONTACT_EMAIL", "set-SEC_CONTACT_EMAIL@example.com")
HEADERS = {"User-Agent": f"AI Capex Tracker ({CONTACT_EMAIL})"}
ANNUAL_FORMS = ("10-K", "20-F", "40-F")
CACHE = pathlib.Path(__file__).resolve().parent.parent / "data" / "headcount_10k.json"

NUM = r"(\d{1,3}(?:,\d{3})+|\d{4,7})"
# Headline phrasings seen across these filers, e.g.
#   "we had approximately 228,000 full-time employees"
#   "we employed approximately 36,000 people"
#   "a total of 1,556,000 full-time and part-time employees"
PATTERNS = [
    re.compile(r"(?:had|employed|employ|have|approximately|total of|workforce of|headcount of)"
               r"[^.]{0,60}?" + NUM + r"[^.]{0,40}?(?:employees|people|individuals|staff)", re.I),
    re.compile(NUM + r"\s+(?:full[- ]time\s+)?(?:employees|people)", re.I),
]
SECTION_MARKERS = re.compile(r"human capital|our employees|employees\s*\n|item\s*6\.?\s*directors, senior management and employees", re.I)


def _get(url, **kw):
    r = requests.get(url, headers=HEADERS, timeout=60, **kw)
    r.raise_for_status()
    time.sleep(0.15)  # stay well under SEC's 10 req/s guidance
    return r


def _latest_annual(cik: str) -> dict | None:
    recent = _get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form in ANNUAL_FORMS:
            return {"form": form, "accession": recent["accessionNumber"][i],
                    "primary_doc": recent["primaryDocument"][i],
                    "filing_date": recent["filingDate"][i],
                    "report_date": recent["reportDate"][i]}
    return None


def _from_xbrl(cik: str, accession: str) -> int | None:
    try:
        facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json").json()
        units = facts.get("facts", {}).get("dei", {}).get("EntityNumberOfEmployees", {}).get("units", {})
        for vals in units.values():
            for v in vals:
                if v.get("accn") == accession and v.get("val"):
                    return int(v["val"])
    except Exception:
        pass
    return None


def _strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v\xa0]+", " ", text)


def _from_text(cik: str, filing: dict) -> tuple[int | None, str | None]:
    acc = filing["accession"].replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{filing['primary_doc']}"
    text = _strip_html(_get(url).text)

    # Search the Human Capital / Employees section first; fall back to whole doc.
    windows = []
    for m in SECTION_MARKERS.finditer(text):
        windows.append(text[m.start():m.start() + 12000])
    windows.append(text)

    for window in windows:
        candidates = []
        for pat in PATTERNS:
            for m in pat.finditer(window):
                n = int(m.group(1).replace(",", ""))
                if 100 <= n <= 3_000_000:
                    start = max(0, m.start() - 60)
                    candidates.append((n, window[start:m.end() + 40].strip()))
        if candidates:
            # The headline total is the largest figure in the section; smaller
            # ones are sub-breakdowns ("of which 12,000 are in the US").
            n, evidence = max(candidates, key=lambda c: c[0])
            return n, re.sub(r"\s+", " ", evidence)[:240]
    return None, None


def load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text())
    except Exception:
        return {}


def fetch_all(companies: list[dict], cik_map: dict) -> dict:
    cache = load_cache()
    for c in companies:
        t = c["ticker"]
        cik = cik_map.get(t)
        if not cik:
            continue
        try:
            filing = _latest_annual(cik)
            if not filing:
                continue
            cached = cache.get(t, {})
            if cached.get("accession") == filing["accession"] and cached.get("headcount"):
                continue  # unchanged since last annual report -- skip the big download

            n, method, evidence = _from_xbrl(cik, filing["accession"]), "xbrl", None
            if not n:
                n, evidence = _from_text(cik, filing)
                method = "text"
            cache[t] = {
                "headcount": n,
                "as_of": filing["report_date"],
                "form": filing["form"],
                "filing_date": filing["filing_date"],
                "accession": filing["accession"],
                "method": method if n else "not_found",
                "evidence": evidence,
                "checked_at": datetime.date.today().isoformat(),
            }
            print(f"[10-K] {t}: {n} ({filing['form']} as of {filing['report_date']}, via {method})")
        except Exception as e:
            print(f"[10-K] {t} failed: {e}")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=2))
    return cache


if __name__ == "__main__":
    import companies as cm
    import fetch_sec_edgar
    result = fetch_all(cm.COMPANIES, fetch_sec_edgar.get_cik_map())
    for t, v in result.items():
        print(f"{t:6} {str(v.get('headcount')):>10}  {v.get('form')} {v.get('as_of')}  [{v.get('method')}]")
        if v.get("evidence"):
            print("       ", v["evidence"][:150])
