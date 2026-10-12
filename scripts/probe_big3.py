"""Find free job-count endpoints for MSFT, GOOGL and META -- the three
biggest AI capex spenders, all currently missing hiring data.

Earlier rounds failed: Microsoft's Eightfold returns "Not authorized",
Google's careers API now 404s, Meta is GraphQL-only. This round scrapes the
careers pages for the API calls their own front-ends make, then tries them.
"""
import json, pathlib, re, requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
      "Accept": "text/html,application/json,*/*", "Accept-Language": "en-US,en;q=0.9"}
T = 30
out = {}

def discover(label, page_urls, patterns):
    """Pull candidate API URLs out of the page HTML and its JS bundles."""
    found = set()
    for u in page_urls:
        try:
            r = requests.get(u, headers=UA, timeout=T, allow_redirects=True)
            html = r.text
            found.update(m.group(0)[:200] for p in patterns for m in re.finditer(p, html))
            # follow same-origin JS bundles, where the real endpoints usually live
            for m in list(re.finditer(r'src="(/[^"]+\.js)"', html))[:6]:
                try:
                    j = requests.get(r.url.split("/")[0] + "//" + r.url.split("/")[2] + m.group(1),
                                     headers=UA, timeout=T)
                    found.update(x.group(0)[:200] for p in patterns for x in re.finditer(p, j.text))
                except Exception:
                    pass
        except Exception as e:
            found.add(f"ERR {str(e)[:60]}")
    return sorted(found)[:14]

API_PAT = [r'https?://[a-z0-9.\-]+/[^"\'\s]{0,60}(?:api|search|jobs)[^"\'\s]{0,60}',
           r'"/api/[^"\']{3,70}"']

print("=== MSFT ===")
msft_try = [
    ("https://gcsservices.careers.microsoft.com/search/api/v1/search",
     {"l": "en_us", "pg": 1, "pgSz": 20, "o": "Relevance", "flt": "true"}),
    ("https://jobs.careers.microsoft.com/global/en/search", {"pg": 1, "pgSz": 20}),
]
msft = []
for url, params in msft_try:
    try:
        r = requests.get(url, headers=UA, params=params, timeout=T)
        body = r.text[:200]
        n = None
        if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            d = r.json()
            n = (d.get("operationResult", {}).get("result", {}) or {}).get("totalJobs")
        msft.append({"url": url, "status": r.status_code, "total": n, "body": body})
        print(f"  {r.status_code} total={n} {url}")
    except Exception as e:
        msft.append({"url": url, "error": str(e)[:100]})
        print(f"  ERR {url} {str(e)[:70]}")
out["MSFT"] = {"tries": msft,
               "discovered": discover("msft", ["https://jobs.careers.microsoft.com/global/en/search"], API_PAT)}

print("=== GOOGL ===")
g = []
for url, params in [
    ("https://www.google.com/about/careers/applications/api/v3/search/", {"page_size": 20}),
    ("https://careers.google.com/api/v3/search/", {"page_size": 20}),
    ("https://www.google.com/about/careers/applications/api/v2/jobs/search", {"page_size": 20}),
]:
    try:
        r = requests.get(url, headers=UA, params=params, timeout=T)
        g.append({"url": url, "status": r.status_code, "body": r.text[:150]})
        print(f"  {r.status_code} {url}")
    except Exception as e:
        g.append({"url": url, "error": str(e)[:90]})
out["GOOGL"] = {"tries": g,
                "discovered": discover("googl",
                    ["https://www.google.com/about/careers/applications/jobs/results/"], API_PAT)}

print("=== META ===")
m = []
for url, params in [
    ("https://www.metacareers.com/jobs", {}),
    ("https://www.metacareers.com/api/jobs", {}),
]:
    try:
        r = requests.get(url, headers=UA, params=params, timeout=T)
        m.append({"url": url, "status": r.status_code, "body": r.text[:150]})
        print(f"  {r.status_code} {url}")
    except Exception as e:
        m.append({"url": url, "error": str(e)[:90]})
out["META"] = {"tries": m,
               "discovered": discover("meta", ["https://www.metacareers.com/jobs/"], API_PAT)}

for k, v in out.items():
    print(f"\n--- {k} discovered endpoints ---")
    for u in v["discovered"]:
        print("   ", u[:150])

pathlib.Path(__file__).resolve().parent.parent.joinpath("data/big3_probe.json").write_text(
    json.dumps(out, indent=2, default=str))
