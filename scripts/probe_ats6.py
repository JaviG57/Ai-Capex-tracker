"""Round 6: VRT (Oracle host found), SMCI (SuccessFactors), plus retries
for Microsoft and Google with headers closer to a real browser XHR."""
import json, pathlib, re, requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9"}
T = 30
out = {}

def oracle(host):
    url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    for site in ["CX_1", "CX_2", "CX_3", "CX_1001", "CX_2001"]:
        try:
            r = requests.get(url, headers=UA, timeout=T,
                             params={"onlyData": "true", "expand": "requisitionList",
                                     "finder": f"findReqs;siteNumber={site},limit=1"})
            if r.status_code == 200:
                items = r.json().get("items", [])
                tot = items[0].get("TotalJobsCount") if items else None
                if tot:
                    return {"ats": "oraclecloud", "endpoint": url, "site": site, "works": True, "job_count": tot}
        except Exception:
            pass
    return {"ats": "oraclecloud", "endpoint": url, "works": False}

def successfactors(company):
    for base in ["https://career4.successfactors.com/career",
                 "https://performancemanager4.successfactors.com/career"]:
        try:
            r = requests.get(base, headers={**UA, "Accept": "text/html,*/*"}, timeout=T,
                             params={"company": company, "career_ns": "job_listing_summary"})
            if r.status_code == 200 and len(r.text) > 500:
                m = (re.search(r'(\d[\d,]*)\s*(?:jobs?|positions?|results?)\s*(?:found|match)', r.text, re.I)
                     or re.search(r'of\s+(\d[\d,]*)\b', r.text))
                return {"ats": "successfactors", "endpoint": base, "company": company,
                        "works": bool(m), "job_count": int(m.group(1).replace(",", "")) if m else None,
                        "sample": r.text[:160] if not m else None}
        except Exception as e:
            return {"ats": "successfactors", "endpoint": base, "works": False, "error": str(e)[:80]}
    return {"ats": "successfactors", "works": False}

def microsoft():
    tries = []
    for url, params, hdrs in [
        ("https://gcsservices.careers.microsoft.com/search/api/v1/search",
         {"l": "en_us", "pg": 1, "pgSz": 20, "o": "Relevance", "flt": "true"}, {}),
        ("https://apply.careers.microsoft.com/api/apply/v2/jobs",
         {"domain": "microsoft.com", "start": 0, "num": 10, "exclude_pid": "", "sort_by": "relevance",
          "triggerGoButton": "false"},
         {"Referer": "https://apply.careers.microsoft.com/careers", "Origin": "https://apply.careers.microsoft.com"}),
    ]:
        try:
            r = requests.get(url, headers={**UA, **hdrs}, params=params, timeout=T)
            tries.append({"url": url, "status": r.status_code, "body": r.text[:120]})
            if r.status_code == 200:
                d = r.json()
                n = (d.get("operationResult", {}).get("result", {}) or {}).get("totalJobs") or d.get("count")
                if n:
                    return {"ats": "ms", "endpoint": url, "params": params, "works": True, "job_count": n}
        except Exception as e:
            tries.append({"url": url, "error": str(e)[:90]})
    return {"ats": "ms", "works": False, "tries": tries}

def google():
    tries = []
    for url, params in [
        ("https://careers.google.com/api/v3/search/", {"page_size": 20, "page": 1}),
        ("https://www.google.com/about/careers/applications/api/v3/search/", {"page_size": 20, "page": 1}),
        ("https://careers.google.com/api/v2/jobs/search/", {"page_size": 20}),
    ]:
        try:
            r = requests.get(url, headers={**UA, "Referer": "https://www.google.com/about/careers/applications/"},
                             params=params, timeout=T)
            tries.append({"url": url, "status": r.status_code, "body": r.text[:120]})
            if r.status_code == 200:
                d = r.json()
                n = d.get("count") or d.get("total_size") or d.get("estimated_total_size")
                if n:
                    return {"ats": "google", "endpoint": url, "params": params, "works": True, "job_count": n}
        except Exception as e:
            tries.append({"url": url, "error": str(e)[:90]})
    return {"ats": "google", "works": False, "tries": tries}

out["VRT"] = oracle("egup.fa.us2.oraclecloud.com")
out["SMCI"] = successfactors("supermicro")
out["MSFT"] = microsoft()
out["GOOGL"] = google()

for tk, p in out.items():
    print(f"{tk:6} [{'WORKS' if p.get('works') else 'fail '}] {p['ats']:15} jobs={p.get('job_count')}")
    for t in (p.get("tries") or []):
        print("        ", t)
    if p.get("sample"):
        print("         sample:", p["sample"][:130])

pathlib.Path(__file__).resolve().parent.parent.joinpath("data/ats_probe6.json").write_text(
    json.dumps(out, indent=2, default=str))
