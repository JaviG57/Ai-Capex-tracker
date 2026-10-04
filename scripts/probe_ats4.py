"""
Round 4: find a free, direct job-board endpoint for the 16 companies still
dependent on TheirStack (which keeps exhausting its free credit allowance).

Three families are tried per company:
  1. Custom career-site APIs the big platforms run (Microsoft, Amazon,
     Google each expose a public JSON search endpoint).
  2. Standard ATS APIs -- Workday, Greenhouse, Lever, Ashby,
     SmartRecruiters, Oracle Cloud Recruiting, Eightfold.
  3. Fingerprint sniffing of the careers page itself, to discover the ATS
     when a guess doesn't land.

Writes data/ats_probe4.json. Run via the probe-ats workflow; this is
discovery only and never part of the daily pipeline.
"""
import json
import pathlib
import re

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
T = 30

FINGERPRINTS = {
    "workday": r"([a-zA-Z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-zA-Z-]{2,6})?/([a-zA-Z0-9_-]+)",
    "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_-]+)",
    "lever": r"jobs\.lever\.co/([a-zA-Z0-9_-]+)",
    "ashby": r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)",
    "smartrecruiters": r"careers\.smartrecruiters\.com/([a-zA-Z0-9_-]+)",
    "oraclecloud": r"([a-zA-Z0-9.-]*\.oraclecloud\.com)",
    "eightfold": r"([a-zA-Z0-9_-]+)\.eightfold\.ai",
    "icims": r"([a-zA-Z0-9_-]+)\.icims\.com",
    "successfactors": r"([a-zA-Z0-9]+)\.successfactors\.(?:com|eu)",
    "phenom": r"([a-zA-Z0-9_-]+)\.phenompeople\.com",
    "avature": r"([a-zA-Z0-9_-]+)\.avature\.net",
    "jobvite": r"jobs\.jobvite\.com/([a-zA-Z0-9_-]+)",
}

# Careers pages to sniff, plus Workday tenant/site guesses to try directly.
TARGETS = {
    "MSFT":  {"pages": ["https://jobs.careers.microsoft.com/global/en/search"], "custom": "microsoft"},
    "GOOGL": {"pages": ["https://www.google.com/about/careers/applications/jobs/results/"], "custom": "google"},
    "AMZN":  {"pages": ["https://www.amazon.jobs/en/search"], "custom": "amazon"},
    "META":  {"pages": ["https://www.metacareers.com/jobs"]},
    "NVDA":  {"pages": ["https://www.nvidia.com/en-us/about-nvidia/careers/"],
              "workday": [("nvidia", "wd5", "NVIDIAExternalCareerSite"), ("nvidia", "wd5", "External")]},
    "AVGO":  {"pages": ["https://www.broadcom.com/company/careers"],
              "workday": [("broadcom", "wd1", "External_Career"), ("broadcom", "wd1", "External"),
                          ("broadcom", "wd5", "External_Career")]},
    "AMD":   {"pages": ["https://careers.amd.com/"],
              "workday": [("amd", "wd1", "External"), ("amd", "wd5", "External"),
                          ("amd", "wd1", "AMD_External")]},
    "TSM":   {"pages": ["https://www.tsmc.com/english/careers", "https://careers.tsmc.com/careers"]},
    "ASML":  {"pages": ["https://www.asml.com/en/careers/find-your-job"]},
    "ARM":   {"pages": ["https://careers.arm.com/", "https://www.arm.com/careers"],
              "workday": [("arm", "wd3", "External"), ("arm", "wd1", "External"),
                          ("arm", "wd3", "ARM_External")]},
    "ORCL":  {"pages": ["https://careers.oracle.com/jobs/"],
              "oracle_hosts": ["eeho.fa.us2.oraclecloud.com"]},
    "DELL":  {"pages": ["https://jobs.dell.com/"],
              "workday": [("dell", "wd1", "External"), ("dell", "wd1", "ExternalCareerSite"),
                          ("dell", "wd5", "External")]},
    "SMCI":  {"pages": ["https://www.supermicro.com/en/about/careers"],
              "greenhouse": ["supermicro"],
              "workday": [("supermicro", "wd1", "External"), ("smci", "wd1", "External")]},
    "DLR":   {"pages": ["https://careers.digitalrealty.com/", "https://www.digitalrealty.com/careers"]},
    "VRT":   {"pages": ["https://www.vertiv.com/en-us/about/career-center/", "https://careers.vertiv.com/"]},
    "ETN":   {"pages": ["https://eaton.eightfold.ai/careers"], "eightfold": [("eaton", "eaton.com")]},
}


def sniff(url):
    rec = {"url": url}
    try:
        r = requests.get(url, headers=UA, timeout=T, allow_redirects=True)
        rec["status"] = r.status_code
        rec["final_url"] = r.url
        hay = r.text + " " + r.url
        rec["hits"] = {n: m.group(0) for n, p in FINGERPRINTS.items() if (m := re.search(p, hay))}
    except Exception as e:
        rec["error"] = str(e)[:120]
    return rec


def probe_workday(tenant, wd, site):
    url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = requests.post(url, headers={**UA, "Content-Type": "application/json"}, timeout=T,
                          json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""})
        if r.status_code == 200:
            return {"ats": "workday", "endpoint": url, "works": True, "job_count": r.json().get("total")}
        return {"ats": "workday", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "workday", "endpoint": url, "works": False, "error": str(e)[:80]}


def probe_greenhouse(board):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    try:
        r = requests.get(url, headers=UA, timeout=T)
        if r.status_code == 200:
            return {"ats": "greenhouse", "endpoint": url, "works": True,
                    "job_count": len(r.json().get("jobs", []))}
        return {"ats": "greenhouse", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "greenhouse", "endpoint": url, "works": False, "error": str(e)[:80]}


def probe_microsoft():
    url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
    try:
        r = requests.get(url, headers=UA, timeout=T,
                         params={"l": "en_us", "pg": 1, "pgSz": 20, "o": "Relevance", "flt": "true"})
        if r.status_code == 200:
            d = r.json()
            total = (d.get("operationResult", {}).get("result", {}) or {}).get("totalJobs")
            return {"ats": "ms_careers", "endpoint": url, "works": total is not None, "job_count": total}
        return {"ats": "ms_careers", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "ms_careers", "endpoint": url, "works": False, "error": str(e)[:80]}


def probe_amazon():
    url = "https://www.amazon.jobs/search.json"
    try:
        r = requests.get(url, headers=UA, timeout=T,
                         params={"result_limit": 10, "offset": 0, "sort": "recent"})
        if r.status_code == 200:
            d = r.json()
            return {"ats": "amazon_jobs", "endpoint": url, "works": "hits" in d, "job_count": d.get("hits")}
        return {"ats": "amazon_jobs", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "amazon_jobs", "endpoint": url, "works": False, "error": str(e)[:80]}


def probe_google():
    for url, params, key in [
        ("https://careers.google.com/api/v3/search/", {"page_size": 20}, "count"),
        ("https://www.google.com/about/careers/applications/api/v3/search/", {"page_size": 20}, "count"),
    ]:
        try:
            r = requests.get(url, headers=UA, timeout=T, params=params)
            if r.status_code == 200:
                d = r.json()
                return {"ats": "google_careers", "endpoint": url, "works": key in d, "job_count": d.get(key)}
        except Exception:
            continue
    return {"ats": "google_careers", "endpoint": "careers.google.com api", "works": False}


def probe_oracle(host, site="CX_1"):
    url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    try:
        r = requests.get(url, headers={**UA, "Accept": "application/json"}, timeout=T,
                         params={"onlyData": "true", "expand": "requisitionList",
                                 "finder": f"findReqs;siteNumber={site},limit=1"})
        if r.status_code == 200:
            items = r.json().get("items", [])
            total = items[0].get("TotalJobsCount") if items else None
            return {"ats": "oraclecloud", "endpoint": url, "site": site,
                    "works": total is not None, "job_count": total}
        return {"ats": "oraclecloud", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "oraclecloud", "endpoint": url, "works": False, "error": str(e)[:80]}


def probe_eightfold(sub, domain):
    url = f"https://{sub}.eightfold.ai/api/apply/v2/jobs"
    try:
        r = requests.get(url, headers=UA, timeout=T,
                         params={"domain": domain, "start": 0, "num": 10,
                                 "exclude_pid": "", "sort_by": "relevance"})
        if r.status_code == 200:
            return {"ats": "eightfold", "endpoint": url, "works": True, "job_count": r.json().get("count")}
        return {"ats": "eightfold", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "eightfold", "endpoint": url, "works": False, "error": str(e)[:80]}


def main():
    results = {}
    for tk, cfg in TARGETS.items():
        print(f"\n=== {tk} ===")
        entry = {"sniff": [], "probes": []}

        for u in cfg.get("pages", []):
            s = sniff(u)
            entry["sniff"].append(s)
            print(f"  page {s.get('status')} {str(s.get('final_url'))[:58]} hits={list((s.get('hits') or {}).keys())}")

        custom = cfg.get("custom")
        if custom == "microsoft":
            entry["probes"].append(probe_microsoft())
        elif custom == "amazon":
            entry["probes"].append(probe_amazon())
        elif custom == "google":
            entry["probes"].append(probe_google())

        for args in cfg.get("workday", []):
            entry["probes"].append(probe_workday(*args))
        for b in cfg.get("greenhouse", []):
            entry["probes"].append(probe_greenhouse(b))
        for h in cfg.get("oracle_hosts", []):
            for site in ["CX_1", "CX_2"]:
                p = probe_oracle(h, site)
                entry["probes"].append(p)
                if p.get("works") and p.get("job_count"):
                    break
        for sub, dom in cfg.get("eightfold", []):
            entry["probes"].append(probe_eightfold(sub, dom))

        # Anything the page fingerprints revealed that we haven't already tried
        hits = {}
        for s in entry["sniff"]:
            hits.update(s.get("hits") or {})
        if "workday" in hits and not any(p["ats"] == "workday" and p.get("works") for p in entry["probes"]):
            m = re.search(FINGERPRINTS["workday"], hits["workday"])
            if m:
                entry["probes"].append(probe_workday(*m.groups()))
        if "greenhouse" in hits:
            m = re.search(FINGERPRINTS["greenhouse"], hits["greenhouse"])
            if m:
                entry["probes"].append(probe_greenhouse(m.group(1)))
        if "oraclecloud" in hits and not cfg.get("oracle_hosts"):
            entry["probes"].append(probe_oracle(hits["oraclecloud"]))
        if "eightfold" in hits and not cfg.get("eightfold"):
            sub = hits["eightfold"].split(".")[0]
            entry["probes"].append(probe_eightfold(sub, f"{sub}.com"))

        for p in entry["probes"]:
            mark = "WORKS" if p.get("works") else "fail "
            print(f"  [{mark}] {p['ats']:16} jobs={p.get('job_count')} {p.get('status', '')}")
        results[tk] = entry

    out = pathlib.Path(__file__).resolve().parent.parent / "data" / "ats_probe4.json"
    out.write_text(json.dumps(results, indent=2, default=str))

    print("\n===== SUMMARY =====")
    for tk, e in results.items():
        w = [p for p in e["probes"] if p.get("works")]
        print(f"{tk:6} {'OK  ' if w else 'MISS'} " +
              (f"{w[0]['ats']} ({w[0].get('job_count')} jobs)" if w else
               "  hints: " + ",".join(sorted({k for s in e['sniff'] for k in (s.get('hits') or {})}))))


if __name__ == "__main__":
    main()
