"""
Direct job-board fetcher for companies TheirStack has no coverage for.

TheirStack returns 0 open roles for CRWV, DLR, EQIX, VRT and ETN even though
all five are actively hiring -- a coverage gap, not a hiring freeze. This
module pulls those companies straight from their applicant tracking system
(ATS) instead.

We hit ATS JSON APIs rather than scraping rendered careers pages because the
APIs are public, stable, and return structured data. The careers pages
themselves render listings client-side, so there is nothing useful in the
HTML to parse anyway.

Discovered so far (see scripts/probe_ats*.py and data/ats_probe*.json):
  CRWV -> Greenhouse   (public board API, no auth)
  EQIX -> Workday      (public CXS endpoint, no auth)

Still unresolved -- these fall through and simply return nothing, so the
rest of the pipeline is unaffected:
  DLR  -> careers site blocks automated requests
  VRT  -> ATS not yet identified
  ETN  -> Eightfold AI, but its API returns 403 without a session

AI-role counting is done here, locally, using the SAME title terms the
TheirStack path uses, so the `jobs_ai` numbers are comparable across
sources rather than reflecting two different definitions of "AI role".
"""
import time
import requests

from fetch_jobs_theirstack import AI_JOB_TITLE_TERMS

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 30

ATS_SOURCES = {
    "CRWV": {"type": "greenhouse", "board": "coreweave"},
    "EQIX": {"type": "workday", "tenant": "equinix", "wd": "wd1", "site": "External"},
}


def _is_ai_title(title: str) -> bool:
    """Mirror TheirStack's job_title_or semantics: a term matches when every
    word in that term appears in the title (in any order)."""
    t = (title or "").lower()
    for term in AI_JOB_TITLE_TERMS:
        if all(word in t for word in term.lower().split()):
            return True
    return False


def fetch_greenhouse(board: str) -> dict | None:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        return {
            "jobs_overall": len(jobs),
            "jobs_ai": sum(1 for j in jobs if _is_ai_title(j.get("title", ""))),
            "jobs_source": "greenhouse",
        }
    except Exception as e:
        print(f"[ats] greenhouse {board} failed: {e}")
        return None


def fetch_workday(tenant: str, wd: str, site: str) -> dict | None:
    """Workday's CXS endpoint pages at 20 per request, so we walk it. Capped
    at 2000 postings so a misconfigured tenant can't spin forever."""
    url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    headers = {**UA, "Content-Type": "application/json"}
    titles, offset, total = [], 0, None
    try:
        while offset < 2000:
            r = requests.post(url, headers=headers, timeout=TIMEOUT,
                              json={"appliedFacets": {}, "limit": 20,
                                    "offset": offset, "searchText": ""})
            r.raise_for_status()
            data = r.json()
            if total is None:
                total = data.get("total")
            postings = data.get("jobPostings", [])
            if not postings:
                break
            titles.extend(p.get("title", "") for p in postings)
            offset += len(postings)
            if total is not None and offset >= total:
                break
            time.sleep(0.4)
        return {
            "jobs_overall": total if total is not None else len(titles),
            "jobs_ai": sum(1 for t in titles if _is_ai_title(t)),
            "jobs_source": "workday",
        }
    except Exception as e:
        print(f"[ats] workday {tenant}/{site} failed: {e}")
        return None


def fetch_all(companies: list[dict]) -> dict:
    results = {}
    for c in companies:
        cfg = ATS_SOURCES.get(c["ticker"])
        if not cfg:
            continue
        if cfg["type"] == "greenhouse":
            res = fetch_greenhouse(cfg["board"])
        elif cfg["type"] == "workday":
            res = fetch_workday(cfg["tenant"], cfg["wd"], cfg["site"])
        else:
            res = None
        if res:
            results[c["ticker"]] = res
            print(f"[ats] {c['ticker']}: {res['jobs_overall']} roles, {res['jobs_ai']} AI-titled")
    return results
