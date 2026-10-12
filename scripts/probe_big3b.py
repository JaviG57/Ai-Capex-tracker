"""
Second attempt at MSFT / GOOGL / META, pursuing avenues the last round named
but didn't try:

  GOOGL -> the results page is server-rendered; scrape the visible job count
           from HTML rather than hunting for a JSON API that no longer exists
  MSFT  -> the page loads from static.vscdn.net (Phenom People's CDN), so
           look for a Phenom widgets endpoint; also retry the gcsservices API,
           whose earlier failure was DNS resolution, not a block
  META  -> earlier 429 is rate limiting, not a hard block: slow down, send
           realistic headers, retry

robots.txt is checked first for each. If a path is disallowed we do not
fetch it -- the point is to read public pages politely, not to evade
controls. CAPTCHA and IP-block circumvention are off the table entirely.
"""
import json, pathlib, re, time
import requests
import urllib.robotparser as urp

UA_STR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
UA = {"User-Agent": UA_STR,
      "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9"}
T = 30
out = {}


def robots_ok(url):
    try:
        base = "/".join(url.split("/")[:3])
        rp = urp.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        rp.read()
        allowed = rp.can_fetch(UA_STR, url)
        return allowed, f"{'ALLOWED' if allowed else 'DISALLOWED'} by {base}/robots.txt"
    except Exception as e:
        return True, f"robots.txt unreadable ({str(e)[:40]}) - proceeding politely"


COUNT_PATTERNS = [
    r"of\s+about\s+([\d,]+)\s+job", r"of\s+([\d,]+)\s+job",
    r"([\d,]+)\s+jobs?\s+(?:found|match|available)",
    r'"totalJobs"\s*:\s*(\d+)', r'"total(?:Count|Results|Size)"\s*:\s*(\d+)',
    r"([\d,]+)\s+open\s+(?:roles|positions)",
]


def scrape_count(label, url, extra=None):
    ok, why = robots_ok(url)
    rec = {"url": url, "robots": why}
    if not ok:
        print(f"  [{label}] SKIPPED - {why}")
        rec["skipped"] = True
        return rec
    try:
        r = requests.get(url, headers={**UA, **(extra or {})}, timeout=T, allow_redirects=True)
        rec["status"] = r.status_code
        rec["final_url"] = r.url
        rec["len"] = len(r.text)
        for p in COUNT_PATTERNS:
            m = re.search(p, r.text, re.I)
            if m:
                rec["count"] = int(m.group(1).replace(",", ""))
                rec["pattern"] = p
                break
        # count rendered job cards as a sanity cross-check
        cards = len(re.findall(r'(jobs/results/\d+|data-job-id|job-card|/job/\d+)', r.text))
        rec["job_links_in_html"] = cards
        print(f"  [{label}] {r.status_code} count={rec.get('count')} job_links={cards} len={len(r.text)}")
        if not rec.get("count"):
            rec["sample"] = re.sub(r"\s+", " ", r.text[:300])
    except Exception as e:
        rec["error"] = str(e)[:120]
        print(f"  [{label}] ERROR {str(e)[:80]}")
    return rec


print("=== GOOGL: server-rendered results page ===")
out["GOOGL"] = [
    scrape_count("results", "https://www.google.com/about/careers/applications/jobs/results/"),
    scrape_count("q=ai", "https://www.google.com/about/careers/applications/jobs/results/?q=%22machine%20learning%22"),
]

print("=== MSFT: Phenom endpoint + gcsservices retry ===")
msft = [scrape_count("careers page", "https://jobs.careers.microsoft.com/global/en/search")]
for url, params in [
    ("https://gcsservices.careers.microsoft.com/search/api/v1/search",
     {"l": "en_us", "pg": 1, "pgSz": 20, "o": "Relevance", "flt": "true"}),
    ("https://jobs.careers.microsoft.com/widgets", None),
]:
    ok, why = robots_ok(url)
    if not ok:
        msft.append({"url": url, "robots": why, "skipped": True}); print(f"  SKIPPED {url}"); continue
    for attempt in range(2):
        try:
            r = requests.get(url, headers=UA, params=params, timeout=T)
            n = None
            if "json" in r.headers.get("content-type", ""):
                d = r.json()
                n = ((d.get("operationResult", {}) or {}).get("result", {}) or {}).get("totalJobs") \
                    or d.get("totalCount") or d.get("total")
            msft.append({"url": url, "status": r.status_code, "total": n,
                         "ctype": r.headers.get("content-type", "")[:40], "body": r.text[:200]})
            print(f"  {r.status_code} total={n} {url[:60]}")
            break
        except Exception as e:
            if attempt == 1:
                msft.append({"url": url, "error": str(e)[:120]})
                print(f"  ERROR {url[:60]} {str(e)[:70]}")
            time.sleep(3)
out["MSFT"] = msft

print("=== META: slow + realistic headers ===")
meta = []
for url in ["https://www.metacareers.com/jobs/", "https://www.metacareers.com/jobs"]:
    time.sleep(4)  # 429 last time: back off deliberately
    meta.append(scrape_count("meta", url, extra={"Referer": "https://www.metacareers.com/",
                                                 "Sec-Fetch-Mode": "navigate"}))
out["META"] = meta

pathlib.Path(__file__).resolve().parent.parent.joinpath("data/big3b_probe.json").write_text(
    json.dumps(out, indent=2, default=str))
print("\nwrote data/big3b_probe.json")
