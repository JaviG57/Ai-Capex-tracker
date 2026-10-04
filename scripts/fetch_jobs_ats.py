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
import datetime
import json
import pathlib
import time

import requests

from fetch_jobs_theirstack import AI_JOB_TITLE_TERMS

# Several job boards refuse to report a total beyond a fixed ceiling
# (Workday stops at 2000, amazon.jobs at 10000). Hitting the ceiling means
# the figure is a FLOOR, not a count: the trend line would sit flat forever,
# and for a "most recent N" window the set slides daily, which would
# manufacture huge fake posting churn. We detect it, label it, and skip churn.
KNOWN_CAPS = {"workday": 2000, "amazon_jobs": 10000, "oracle": None, "greenhouse": None}

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 30

ATS_SOURCES = {
    "CRWV": {"type": "greenhouse", "board": "coreweave"},
    "EQIX": {"type": "workday", "tenant": "equinix", "wd": "wd1", "site": "External"},
    "NVDA": {"type": "workday", "tenant": "nvidia", "wd": "wd5", "site": "NVIDIAExternalCareerSite"},
    "AVGO": {"type": "workday", "tenant": "broadcom", "wd": "wd1", "site": "External_Career"},
    "ORCL": {"type": "oracle", "host": "eeho.fa.us2.oraclecloud.com", "site": "CX_1"},
    "DELL": {"type": "oracle", "host": "enterpriseplatform.dell.com", "site": "CX_1"},
    "VRT":  {"type": "oracle", "host": "egup.fa.us2.oraclecloud.com", "site": "CX_1"},
    "AMZN": {"type": "amazon"},
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
            "_ids": [str(j.get("id")) for j in jobs if j.get("id") is not None],
            "_complete": True,
        }
    except Exception as e:
        print(f"[ats] greenhouse {board} failed: {e}")
        return None


def fetch_workday(tenant: str, wd: str, site: str) -> dict | None:
    """Workday's CXS endpoint pages at 20 per request, so we walk it. Capped
    at 2000 postings so a misconfigured tenant can't spin forever."""
    url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    headers = {**UA, "Content-Type": "application/json"}
    titles, ids, offset, total = [], [], 0, None
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
            ids.extend(p.get("externalPath", "") for p in postings if p.get("externalPath"))
            offset += len(postings)
            if total is not None and offset >= total:
                break
            time.sleep(0.4)
        # Only trust the ID set for churn if we actually walked (nearly) all
        # of it. A partial list would make unfetched postings look "closed".
        complete = total is not None and len(ids) >= 0.98 * total
        return {
            "jobs_overall": total if total is not None else len(titles),
            "jobs_ai": sum(1 for t in titles if _is_ai_title(t)),
            "jobs_source": "workday",
            "_ids": ids,
            "_complete": complete,
        }
    except Exception as e:
        print(f"[ats] workday {tenant}/{site} failed: {e}")
        return None


def fetch_oracle(host: str, site: str, max_jobs: int = 6000) -> dict | None:
    """Oracle Cloud Recruiting (ORCL, DELL, VRT). The first page carries
    TotalJobsCount; pages of 200 then walk the list to collect titles."""
    url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    titles, ids, offset, total = [], [], 0, None
    try:
        while offset < max_jobs:
            r = requests.get(url, headers=UA, timeout=TIMEOUT, params={
                "onlyData": "true", "expand": "requisitionList",
                "finder": f"findReqs;siteNumber={site},limit=200,offset={offset}"})
            r.raise_for_status()
            items = r.json().get("items", [])
            if not items:
                break
            if total is None:
                total = items[0].get("TotalJobsCount")
            reqs = items[0].get("requisitionList") or []
            if not reqs:
                break
            titles += [q.get("Title", "") for q in reqs]
            ids += [str(q.get("Id")) for q in reqs if q.get("Id")]
            offset += len(reqs)
            if total is not None and offset >= total:
                break
            time.sleep(0.25)
        complete = total is not None and len(titles) >= 0.98 * min(total, max_jobs)
        return {"jobs_overall": total if total is not None else len(titles),
                "jobs_ai": sum(1 for t in titles if _is_ai_title(t)),
                "jobs_source": "oracle", "_ids": ids, "_complete": complete}
    except Exception as e:
        print(f"[ats] oracle {host} failed: {e}")
        return None


def fetch_amazon(max_jobs: int = 12000) -> dict | None:
    """amazon.jobs search.json, paginated at 100/page so AI titles are counted
    with the same rule as every other source rather than via keyword search."""
    url = "https://www.amazon.jobs/search.json"
    titles, ids, offset, total = [], [], 0, None
    try:
        while offset < max_jobs:
            r = requests.get(url, headers=UA, timeout=TIMEOUT,
                             params={"result_limit": 100, "offset": offset, "sort": "recent"})
            r.raise_for_status()
            data = r.json()
            if total is None:
                total = data.get("hits")
            jobs = data.get("jobs", [])
            if not jobs:
                break
            titles += [j.get("title", "") for j in jobs]
            ids += [str(j.get("id_icims") or j.get("job_path") or j.get("id")) for j in jobs]
            offset += len(jobs)
            if total is not None and offset >= total:
                break
            time.sleep(0.3)
        capped = total is not None and total >= KNOWN_CAPS["amazon_jobs"]
        complete = total is not None and len(titles) >= 0.95 * min(total, max_jobs)
        return {"jobs_overall": total if total is not None else len(titles),
                "jobs_ai": sum(1 for t in titles if _is_ai_title(t)),
                "jobs_source": "amazon_jobs", "jobs_capped": capped,
                "_ids": ids, "_complete": complete and not capped}
    except Exception as e:
        print(f"[ats] amazon failed: {e}")
        return None


SNAPSHOT_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "job_ids"


def compute_churn(ticker: str, ids: list[str], complete: bool, today: str) -> dict:
    """
    Posting churn vs. the previous DAY's snapshot:
      jobs_new    = postings present today that weren't there before
      jobs_closed = postings that were there before and are now gone
                    (filled OR cancelled -- the ATS doesn't say which)

    Snapshots keep the prior day alongside today's, so re-running the
    pipeline twice in one day still compares against yesterday instead of
    against this morning's run (which would show ~zero churn).
    """
    path = SNAPSHOT_DIR / f"{ticker}.json"
    stored = {}
    try:
        stored = json.loads(path.read_text())
    except Exception:
        pass

    baseline = stored.get("prev") if stored.get("date") == today else stored
    churn = {"jobs_new": None, "jobs_closed": None}
    if complete and baseline and baseline.get("ids") is not None and baseline.get("complete"):
        prev_ids, cur_ids = set(baseline["ids"]), set(ids)
        churn = {"jobs_new": len(cur_ids - prev_ids), "jobs_closed": len(prev_ids - cur_ids)}

    if complete:
        prev_for_storage = stored.get("prev") if stored.get("date") == today else (
            {"date": stored.get("date"), "ids": stored.get("ids"), "complete": stored.get("complete")}
            if stored else None)
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"date": today, "ids": sorted(set(ids)),
                                    "complete": True, "prev": prev_for_storage}))
    return churn


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
        elif cfg["type"] == "oracle":
            res = fetch_oracle(cfg["host"], cfg["site"])
        elif cfg["type"] == "amazon":
            res = fetch_amazon()
        else:
            res = None
        if res:
            ids, complete = res.pop("_ids", []), res.pop("_complete", False)
            res.update(compute_churn(c["ticker"], ids, complete, datetime.date.today().isoformat()))
            results[c["ticker"]] = res
            cap = "  [CAPPED by API - floor, not exact; churn skipped]" if res.get("jobs_capped") else ""
            print(f"[ats] {c['ticker']}: {res['jobs_overall']} roles, {res['jobs_ai']} AI-titled, "
                  f"+{res['jobs_new']} new / -{res['jobs_closed']} closed{cap}")
    return results
