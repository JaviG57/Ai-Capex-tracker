"""
ONE-OFF DISCOVERY PROBE -- not part of the daily run.

TheirStack returns 0 open roles for CRWV, DLR, EQIX, VRT and ETN, which is a
coverage gap rather than a real hiring freeze. This script finds a direct
source for those five by:

  1. Fetching each company's careers page and looking for the fingerprint of
     a known applicant tracking system (ATS) in the HTML/redirect chain.
  2. Probing candidate ATS API endpoints directly.

We target ATS JSON APIs rather than scraping rendered HTML because the APIs
are public, stable, and return structured counts -- HTML scraping breaks on
every site redesign, and most of these careers pages render their listings
client-side anyway (so there'd be nothing in the HTML to parse).

Run via the probe-ats workflow; results land in data/ats_probe.json.
"""
import json
import re
import pathlib
import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; ai-capex-tracker/1.0)"}
TIMEOUT = 25

TARGETS = [
    {"ticker": "CRWV", "name": "CoreWeave", "careers": "https://www.coreweave.com/careers"},
    {"ticker": "DLR", "name": "Digital Realty", "careers": "https://careers.digitalrealty.com"},
    {"ticker": "EQIX", "name": "Equinix", "careers": "https://careers.equinix.com"},
    {"ticker": "VRT", "name": "Vertiv", "careers": "https://www.vertiv.com/en-us/about/careers/"},
    {"ticker": "ETN", "name": "Eaton", "careers": "https://www.eaton.com/us/en-us/company/careers.html"},
]

# Fingerprints that reveal which ATS a careers page is backed by.
ATS_PATTERNS = {
    "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_-]+)",
    "lever": r"jobs\.lever\.co/([a-zA-Z0-9_-]+)",
    "ashby": r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)",
    "smartrecruiters": r"careers\.smartrecruiters\.com/([a-zA-Z0-9_-]+)",
    "workday": r"([a-zA-Z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-zA-Z-]{2,5})?/([a-zA-Z0-9_-]+)",
    "icims": r"([a-zA-Z0-9_-]+)\.icims\.com",
    "successfactors": r"([a-zA-Z0-9_-]+)\.successfactors\.com",
}

# Direct guesses to try even if the HTML gives nothing away.
GREENHOUSE_GUESSES = {"CRWV": ["coreweave"]}
WORKDAY_GUESSES = {
    "DLR": [("digitalrealty", "wd1", "Digital_Realty_Careers"), ("digitalrealty", "wd1", "External"),
            ("digitalrealty", "wd5", "Digital_Realty_Careers")],
    "EQIX": [("equinix", "wd1", "EQXCareers"), ("equinix", "wd1", "External"),
             ("equinix", "wd5", "EQXCareers"), ("equinix", "wd1", "Equinix_Careers")],
    "VRT": [("vertiv", "wd5", "Vertiv_Careers"), ("vertiv", "wd1", "Vertiv_Careers"),
            ("vertiv", "wd5", "External"), ("vertiv", "wd1", "External")],
    "ETN": [("eaton", "wd1", "Eaton_Careers"), ("eaton", "wd1", "External"),
            ("eaton", "wd5", "Eaton_Careers"), ("eaton", "wd1", "EatonCareers")],
}


def sniff_careers_page(url: str) -> dict:
    out = {"url": url, "ok": False, "final_url": None, "found": {}}
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
        out["ok"] = r.status_code == 200
        out["status"] = r.status_code
        out["final_url"] = r.url
        haystack = r.text + " " + r.url
        for ats, pattern in ATS_PATTERNS.items():
            m = re.search(pattern, haystack)
            if m:
                out["found"][ats] = list(m.groups())
    except Exception as e:
        out["error"] = str(e)
    return out


def try_greenhouse(token: str) -> dict:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            return {"ats": "greenhouse", "endpoint": url, "works": True,
                    "job_count": len(data.get("jobs", []))}
        return {"ats": "greenhouse", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "greenhouse", "endpoint": url, "works": False, "error": str(e)}


def try_workday(tenant: str, wd: str, site: str) -> dict:
    url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = requests.post(url, headers={**UA, "Content-Type": "application/json",
                                        "Accept": "application/json"},
                          json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""},
                          timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            return {"ats": "workday", "endpoint": url, "works": True,
                    "job_count": data.get("total")}
        return {"ats": "workday", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "workday", "endpoint": url, "works": False, "error": str(e)}


def try_smartrecruiters(token: str) -> dict:
    url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, params={"limit": 10})
        if r.status_code == 200:
            return {"ats": "smartrecruiters", "endpoint": url, "works": True,
                    "job_count": r.json().get("totalFound")}
        return {"ats": "smartrecruiters", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "smartrecruiters", "endpoint": url, "works": False, "error": str(e)}


def main():
    results = {}
    for t in TARGETS:
        print(f"\n=== {t['ticker']} ({t['name']}) ===")
        entry = {"name": t["name"], "sniff": sniff_careers_page(t["careers"]), "probes": []}
        print("  careers page:", entry["sniff"].get("status"), "->", entry["sniff"].get("final_url"))
        print("  fingerprints:", entry["sniff"].get("found"))

        # Probe whatever the page revealed
        found = entry["sniff"].get("found", {})
        if "greenhouse" in found:
            entry["probes"].append(try_greenhouse(found["greenhouse"][0]))
        if "smartrecruiters" in found:
            entry["probes"].append(try_smartrecruiters(found["smartrecruiters"][0]))
        if "workday" in found and len(found["workday"]) >= 3:
            tenant, wd, site = found["workday"][0], found["workday"][1], found["workday"][2]
            entry["probes"].append(try_workday(tenant, wd, site))

        # Plus the explicit guesses
        for token in GREENHOUSE_GUESSES.get(t["ticker"], []):
            entry["probes"].append(try_greenhouse(token))
        for tenant, wd, site in WORKDAY_GUESSES.get(t["ticker"], []):
            entry["probes"].append(try_workday(tenant, wd, site))

        for p in entry["probes"]:
            flag = "OK  " if p.get("works") else "FAIL"
            print(f"  [{flag}] {p['ats']:16} jobs={p.get('job_count')} {p.get('status', '')} {p['endpoint'][:90]}")
        results[t["ticker"]] = entry

    out = pathlib.Path(__file__).resolve().parent.parent / "data" / "ats_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
