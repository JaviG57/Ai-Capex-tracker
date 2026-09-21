"""
Round 3 of ATS discovery. Round 2 revealed:
  ETN -> Eightfold AI (eaton.eightfold.ai)
  DLR -> Oracle Cloud Recruiting (per job-aggregator metadata)
  VRT -> careers page loads but lists jobs client-side, ATS still unknown

This probes those specific platforms plus a broadened fingerprint sweep.
"""
import json
import re
import pathlib
import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
T = 25

FINGERPRINTS = {
    "oraclecloud": r"([a-zA-Z0-9-]+)\.(?:fa\.)?([a-z0-9]+)\.oraclecloud\.com",
    "eightfold": r"([a-zA-Z0-9_-]+)\.eightfold\.ai",
    "workday": r"([a-zA-Z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-zA-Z-]{2,5})?/([a-zA-Z0-9_-]+)",
    "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/([a-zA-Z0-9_-]+)",
    "smartrecruiters": r"careers\.smartrecruiters\.com/([a-zA-Z0-9_-]+)",
    "icims": r"([a-zA-Z0-9_-]+)\.icims\.com",
    "phenom": r"([a-zA-Z0-9_-]+)\.phenompeople\.com",
    "successfactors": r"([a-zA-Z0-9]+)\.successfactors\.(?:com|eu)",
    "avature": r"([a-zA-Z0-9_-]+)\.avature\.net",
    "taleo": r"([a-zA-Z0-9_-]+)\.taleo\.net",
    "jobvite": r"jobs\.jobvite\.com/([a-zA-Z0-9_-]+)",
}

PAGES = {
    "DLR": ["https://careers.digitalrealty.com/", "https://www.digitalrealty.com/about/careers",
            "https://careers.digitalrealty.com/search"],
    "VRT": ["https://www.vertiv.com/en-us/about/career-center/", "https://careers.vertiv.com/",
            "https://jobs.vertiv.com/"],
    "ETN": ["https://eaton.eightfold.ai/careers"],
}


def sniff(url):
    rec = {"url": url}
    try:
        r = requests.get(url, headers=UA, timeout=T, allow_redirects=True)
        rec["status"] = r.status_code
        rec["final_url"] = r.url
        hay = r.text + " " + r.url
        hits = {}
        for name, pat in FINGERPRINTS.items():
            m = re.search(pat, hay)
            if m:
                hits[name] = m.group(0)
        rec["hits"] = hits
    except Exception as e:
        rec["error"] = str(e)[:150]
    return rec


def try_eightfold(sub, domain):
    url = f"https://{sub}.eightfold.ai/api/apply/v2/jobs"
    try:
        r = requests.get(url, headers=UA, timeout=T,
                         params={"domain": domain, "start": 0, "num": 10, "sort_by": "relevance"})
        if r.status_code == 200:
            d = r.json()
            return {"ats": "eightfold", "endpoint": url, "params": {"domain": domain},
                    "works": True, "job_count": d.get("count")}
        return {"ats": "eightfold", "endpoint": url, "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "eightfold", "endpoint": url, "works": False, "error": str(e)[:100]}


def try_oracle(host, site="CX_1"):
    url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    params = {"onlyData": "true", "expand": "requisitionList.secondaryLocations",
              "finder": f"findReqs;siteNumber={site},limit=1,sortBy=POSTING_DATES_DESC"}
    try:
        r = requests.get(url, headers={**UA, "Accept": "application/json"},
                         params=params, timeout=T)
        if r.status_code == 200:
            d = r.json()
            items = d.get("items", [])
            total = items[0].get("TotalJobsCount") if items else None
            return {"ats": "oraclecloud", "endpoint": url, "site": site,
                    "works": True, "job_count": total}
        return {"ats": "oraclecloud", "endpoint": url, "site": site,
                "works": False, "status": r.status_code}
    except Exception as e:
        return {"ats": "oraclecloud", "endpoint": url, "works": False, "error": str(e)[:100]}


def main():
    results = {}
    for tk, urls in PAGES.items():
        print(f"\n=== {tk} ===")
        entry = {"sniff": [], "probes": []}
        for u in urls:
            s = sniff(u)
            entry["sniff"].append(s)
            print(f"  {s.get('status')} {str(s.get('final_url'))[:60]} hits={s.get('hits')}")

        all_hits = {}
        for s in entry["sniff"]:
            all_hits.update(s.get("hits", {}))

        if tk == "ETN" or "eightfold" in all_hits:
            sub = all_hits.get("eightfold", "eaton.eightfold.ai").split(".")[0]
            for dom in ["eaton.com", f"{sub}.com"]:
                p = try_eightfold(sub, dom)
                entry["probes"].append(p)
                if p.get("works"):
                    break

        if "oraclecloud" in all_hits:
            host = all_hits["oraclecloud"]
            for site in ["CX_1", "CX_2", "CX_1001"]:
                p = try_oracle(host, site)
                entry["probes"].append(p)
                if p.get("works") and p.get("job_count"):
                    break

        if "workday" in all_hits:
            m = re.search(FINGERPRINTS["workday"], all_hits["workday"])
            if m:
                t_, w_, s_ = m.groups()
                url = f"https://{t_}.{w_}.myworkdayjobs.com/wday/cxs/{t_}/{s_}/jobs"
                try:
                    r = requests.post(url, headers={**UA, "Content-Type": "application/json"},
                                      json={"appliedFacets": {}, "limit": 20, "offset": 0,
                                            "searchText": ""}, timeout=T)
                    entry["probes"].append({"ats": "workday", "endpoint": url,
                                            "works": r.status_code == 200,
                                            "job_count": r.json().get("total") if r.status_code == 200 else None,
                                            "status": r.status_code})
                except Exception as e:
                    entry["probes"].append({"ats": "workday", "endpoint": url, "works": False,
                                            "error": str(e)[:100]})

        for p in entry["probes"]:
            print(f"  [{'WORKS' if p.get('works') else 'fail '}] {p['ats']:14} jobs={p.get('job_count')} {p.get('status','')}")
        results[tk] = entry

    out = pathlib.Path(__file__).resolve().parent.parent / "data" / "ats_probe3.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
