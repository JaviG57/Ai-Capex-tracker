"""
Round 5: targeted probes based on what round 4's fingerprints revealed.

  MSFT, ETN -> Eightfold (403 on the naive call; try the company's own
               host, several domain params, and a Referer header)
  DELL      -> Oracle Cloud Recruiting at enterpriseplatform.dell.com
  AMD, ARM  -> iCIMS
  GOOGL     -> retry the careers API with fuller params
  TSM, ASML, DLR, VRT, SMCI -> deeper HTML inspection for an embedded ATS
"""
import json
import pathlib
import re
import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
T = 30
results = {}


def try_eightfold(host, domain, referer):
    url = f"https://{host}/api/apply/v2/jobs"
    for params in [
        {"domain": domain, "start": 0, "num": 10, "exclude_pid": "", "sort_by": "relevance"},
        {"domain": domain, "start": 0, "num": 10, "query": "", "location": ""},
        {"domain": domain, "num": 10},
    ]:
        try:
            r = requests.get(url, headers={**UA, "Referer": referer}, params=params, timeout=T)
            if r.status_code == 200:
                d = r.json()
                return {"ats": "eightfold", "endpoint": url, "params": params,
                        "works": True, "job_count": d.get("count")}
        except Exception:
            continue
    return {"ats": "eightfold", "endpoint": url, "works": False, "status": "403/err all variants"}


def try_oracle(host):
    url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    for site in ["CX_1", "CX_2", "CX_3", "CX_1001", "CX_45001"]:
        try:
            r = requests.get(url, headers=UA, timeout=T,
                             params={"onlyData": "true", "expand": "requisitionList",
                                     "finder": f"findReqs;siteNumber={site},limit=1"})
            if r.status_code == 200:
                items = r.json().get("items", [])
                tot = items[0].get("TotalJobsCount") if items else None
                if tot:
                    return {"ats": "oraclecloud", "endpoint": url, "site": site,
                            "works": True, "job_count": tot}
        except Exception:
            continue
    return {"ats": "oraclecloud", "endpoint": url, "works": False}


def try_icims(sub):
    for url in [f"https://{sub}.icims.com/jobs/search",
                f"https://careers-{sub}.icims.com/jobs/search"]:
        try:
            r = requests.get(url, headers={**UA, "Accept": "text/html,*/*"}, timeout=T,
                             params={"pr": 0, "in_iframe": 1, "searchRelation": "keyword_all"})
            if r.status_code == 200:
                m = re.search(r"of\s*<strong>\s*([\d,]+)\s*</strong>", r.text) or \
                    re.search(r"([\d,]+)\s+(?:Job|Result)s?\s+(?:Found|match)", r.text, re.I) or \
                    re.search(r'"totalCount"\s*:\s*(\d+)', r.text)
                if m:
                    return {"ats": "icims", "endpoint": url, "works": True,
                            "job_count": int(m.group(1).replace(",", ""))}
                return {"ats": "icims", "endpoint": url, "works": False,
                        "status": "200 but no count parsed", "sample": r.text[:200]}
        except Exception as e:
            return {"ats": "icims", "endpoint": url, "works": False, "error": str(e)[:80]}
    return {"ats": "icims", "endpoint": sub, "works": False}


def try_google():
    out = []
    for url in ["https://careers.google.com/api/v3/search/",
                "https://www.google.com/about/careers/applications/api/v3/search/"]:
        try:
            r = requests.get(url, headers={**UA, "Referer": "https://www.google.com/about/careers/applications/"},
                             params={"page_size": 20, "page": 1}, timeout=T)
            out.append({"url": url, "status": r.status_code, "body": r.text[:150]})
            if r.status_code == 200:
                d = r.json()
                return {"ats": "google_careers", "endpoint": url, "works": True,
                        "job_count": d.get("count") or d.get("total_size")}
        except Exception as e:
            out.append({"url": url, "error": str(e)[:80]})
    return {"ats": "google_careers", "works": False, "attempts": out}


def deep_sniff(name, urls):
    """Look for an embedded ATS in page HTML, including inside iframes."""
    found = {}
    for u in urls:
        try:
            r = requests.get(u, headers={**UA, "Accept": "text/html,*/*"}, timeout=T, allow_redirects=True)
            hay = r.text + " " + r.url
            for pat_name, pat in {
                "workday": r"([a-zA-Z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-zA-Z-]{2,6})?/([a-zA-Z0-9_-]+)",
                "icims": r"([a-zA-Z0-9_-]+)\.icims\.com",
                "successfactors": r"([a-zA-Z0-9]+)\.successfactors\.(?:com|eu)",
                "oracle_orc": r"([a-zA-Z0-9.-]+)/hcmUI/CandidateExperience",
                "phenom": r"([a-zA-Z0-9_-]+)\.phenompeople\.com",
                "eightfold": r"([a-zA-Z0-9_.-]+)\.eightfold\.ai",
                "smartrecruiters": r"smartrecruiters\.com/([a-zA-Z0-9_-]+)",
                "greenhouse": r"greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_-]+)",
                "iframe": r'<iframe[^>]+src=["\']([^"\']{10,160})["\']',
                "jobs_api": r'["\'](https?://[^"\']*(?:/api/|/jobs/search|search\.json)[^"\']{0,80})["\']',
            }.items():
                for m in re.finditer(pat, hay):
                    found.setdefault(pat_name, set()).add(m.group(0)[:120])
        except Exception as e:
            found.setdefault("errors", set()).add(str(e)[:60])
    return {k: sorted(v)[:4] for k, v in found.items()}


print("=== Eightfold (MSFT, ETN) ===")
results["MSFT"] = [
    try_eightfold("apply.careers.microsoft.com", "microsoft.com", "https://apply.careers.microsoft.com/careers"),
    try_eightfold("app.eightfold.ai", "microsoft.com", "https://apply.careers.microsoft.com/careers"),
]
results["ETN"] = [
    try_eightfold("eaton.eightfold.ai", "eaton.com", "https://eaton.eightfold.ai/careers"),
    try_eightfold("app.eightfold.ai", "eaton.com", "https://eaton.eightfold.ai/careers"),
]
print("=== Oracle Cloud (DELL) ===")
results["DELL"] = [try_oracle("enterpriseplatform.dell.com")]
print("=== iCIMS (AMD, ARM) ===")
results["AMD"] = [try_icims("internal-amd"), try_icims("amd")]
results["ARM"] = [try_icims("earlycareers-arm"), try_icims("arm")]
print("=== Google ===")
results["GOOGL"] = [try_google()]

print("=== deep sniff ===")
deep = {
    "TSM": ["https://careers.tsmc.com/en_US/careers"],
    "ASML": ["https://www.asml.com/en/careers/find-your-job"],
    "DLR": ["https://www.digitalrealty.com/careers", "https://digitalrealty.com/careers"],
    "VRT": ["https://www.vertiv.com/en-us/about/career-center/"],
    "SMCI": ["https://www.supermicro.com/en/about/careers", "https://jobs.supermicro.com/"],
    "META": ["https://www.metacareers.com/jobs/", "https://www.metacareers.com/"],
}
sniffs = {k: deep_sniff(k, v) for k, v in deep.items()}

for tk, probes in results.items():
    for p in probes:
        print(f"{tk:6} [{'WORKS' if p.get('works') else 'fail '}] {p['ats']:15} jobs={p.get('job_count')}")
print()
for tk, s in sniffs.items():
    print(f"{tk}: { {k: v for k, v in s.items() if k != 'errors'} }")

out = pathlib.Path(__file__).resolve().parent.parent / "data" / "ats_probe5.json"
out.write_text(json.dumps({"probes": results, "sniffs": sniffs}, indent=2, default=str))
print(f"\nwrote {out}")
