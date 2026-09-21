"""
Round 2 of ATS discovery -- narrows down the three companies round 1 couldn't
resolve (DLR, VRT, ETN). Round 1 got HTTP 422 from Workday, which means the
tenant hostname resolved but the site path was wrong, so this sweeps tenant
and site-name variants. Also re-fetches careers pages with browser-like
headers, since two of them refused the plain request entirely.
"""
import json
import re
import pathlib
import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 25

CAREERS_URLS = {
    "DLR": ["https://www.digitalrealty.com/careers", "https://careers.digitalrealty.com/",
            "https://www.digitalrealty.com/about/careers"],
    "VRT": ["https://www.vertiv.com/en-us/about/career-center/", "https://careers.vertiv.com/"],
    "ETN": ["https://www.eaton.com/us/en-us/company/careers.html", "https://careers.eaton.com/",
            "https://jobs.eaton.com/"],
}

TENANTS = {
    "DLR": ["digitalrealty", "digitalrealtytrust", "dlr"],
    "VRT": ["vertiv", "vertivco", "vertivgroup"],
    "ETN": ["eaton", "eatoncorp", "eatoncorporation"],
}

WD_HOSTS = ["wd1", "wd3", "wd5", "wd12", "wd103"]

SITE_NAMES = [
    "External", "Careers", "External_Careers", "ExternalCareers",
    "Global_Careers", "GlobalCareers", "US_Careers", "Professional",
    "Digital_Realty_Careers", "DigitalRealty", "DLR_Careers",
    "Vertiv_Careers", "VertivCareers", "Vertiv",
    "Eaton_Careers", "EatonCareers", "Eaton", "eaton_careers",
]

WORKDAY_RE = re.compile(r"([a-zA-Z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-zA-Z-]{2,5})?/([a-zA-Z0-9_-]+)")
OTHER_ATS = {
    "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/([a-zA-Z0-9_-]+)",
    "smartrecruiters": r"careers\.smartrecruiters\.com/([a-zA-Z0-9_-]+)",
    "icims": r"([a-zA-Z0-9_-]+)\.icims\.com",
    "successfactors": r"career\d*\.successfactors\.(?:com|eu)",
    "phenom": r"([a-zA-Z0-9_-]+)\.phenompeople\.com",
    "avature": r"([a-zA-Z0-9_-]+)\.avature\.net",
}


def sniff(urls):
    out = []
    for u in urls:
        rec = {"url": u}
        try:
            r = requests.get(u, headers=UA, timeout=TIMEOUT, allow_redirects=True)
            rec["status"] = r.status_code
            rec["final_url"] = r.url
            hay = r.text + " " + r.url
            m = WORKDAY_RE.search(hay)
            if m:
                rec["workday"] = list(m.groups())
            for name, pat in OTHER_ATS.items():
                mm = re.search(pat, hay)
                if mm:
                    rec[name] = mm.group(0)
        except Exception as e:
            rec["error"] = str(e)[:120]
        out.append(rec)
    return out


def try_workday(tenant, wd, site):
    url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = requests.post(url, headers={**UA, "Content-Type": "application/json",
                                        "Accept": "application/json"},
                          json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""},
                          timeout=15)
        if r.status_code == 200:
            return {"works": True, "endpoint": url, "job_count": r.json().get("total")}
    except Exception:
        pass
    return None


def main():
    results = {}
    for tk in ["DLR", "VRT", "ETN"]:
        print(f"\n=== {tk} ===")
        entry = {"sniff": sniff(CAREERS_URLS[tk]), "working": []}
        for s in entry["sniff"]:
            print("  page:", s.get("status"), str(s.get("final_url"))[:70],
                  "| workday:", s.get("workday"), "| other:",
                  {k: v for k, v in s.items() if k in OTHER_ATS})

        # If a page revealed a Workday triple, try it first.
        for s in entry["sniff"]:
            if s.get("workday"):
                t, w, site = s["workday"]
                hit = try_workday(t, w, site)
                if hit:
                    entry["working"].append(hit)
                    print("  [WORKS from page]", hit["endpoint"], hit["job_count"])

        if not entry["working"]:
            print("  sweeping tenant/site combinations...")
            for tenant in TENANTS[tk]:
                for wd in WD_HOSTS:
                    for site in SITE_NAMES:
                        hit = try_workday(tenant, wd, site)
                        if hit:
                            entry["working"].append(hit)
                            print("  [WORKS]", hit["endpoint"], "jobs:", hit["job_count"])
                    if entry["working"]:
                        break
                if entry["working"]:
                    break

        if not entry["working"]:
            print("  no Workday endpoint found")
        results[tk] = entry

    out = pathlib.Path(__file__).resolve().parent.parent / "data" / "ats_probe2.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
