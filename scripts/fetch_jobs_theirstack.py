"""
Job-posting signals from TheirStack (https://theirstack.com).

Design choice: we run ONE query per company per day, filtered by AI-related
job-title terms. TheirStack's response embeds a `company_object` with:
  - num_jobs             -> ALL open jobs currently tracked for the company
                             (this becomes our "overall hiring" metric)
  - num_jobs_found       -> jobs matching THIS query's filters
                             (this becomes our "AI-related hiring" metric)
  - num_jobs_last_30_days -> recent hiring velocity, unfiltered

So one request gets us both the overall and AI-specific counts, at the cost
of 1 credit (TheirStack bills 1 credit per job returned in `data`, and we
set limit=1 to return the minimum).

CREDIT BUDGET -- read before relying on this daily:
TheirStack's free tier is 200 credits/month. At 1 credit/company/day, the
18-company list above costs 18 credits/day (~540/month), which exhausts
the free tier around day 11 of each month. Options:
  1. Upgrade to TheirStack's paid tier for full-month daily coverage.
  2. Round-robin: track ~6 companies/day on a rotation (see `pick_todays_subset`
     below) to spread 18 companies across 3 days and stay inside 200/month.
  3. Shrink the company list.
This script does NOT decide for you -- it defaults to querying everyone
daily and logs a clear warning once credits run out (HTTP 402) rather than
crashing the rest of the pipeline.
"""
import os
import time
import requests

THEIRSTACK_API_URL = "https://api.theirstack.com/v1/jobs/search"
API_KEY = os.environ.get("THEIRSTACK_API_KEY")

# Matched as whole-word title patterns (job_title_or requires ALL words in
# a phrase to appear, in any order) -- not catalog keyword slugs, so these
# work without first calling GET /v0/catalog/keywords. Edit freely.
AI_JOB_TITLE_TERMS = [
    "machine learning",
    "artificial intelligence",
    "ai engineer",
    "ai research",
    "llm",
    "generative ai",
    "deep learning",
    "ml engineer",
    "ml infrastructure",
]

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def pick_todays_subset(companies: list[dict], day_index: int, batch_size: int) -> list[dict]:
    """Round-robin helper for free-tier credit budgets. Not used by default
    (run_daily.py queries everyone daily) -- wire this in if you need to
    stay under 200 credits/month. `day_index` = e.g. day-of-year."""
    if batch_size >= len(companies):
        return companies
    start = (day_index * batch_size) % len(companies)
    return (companies * 2)[start:start + batch_size]


def _post(payload: dict) -> dict | None:
    resp = requests.post(THEIRSTACK_API_URL, json=payload, headers=HEADERS, timeout=30)
    if resp.status_code == 402:
        print("[theirstack] out of credits for this billing period -- skipping remainder")
        return "OUT_OF_CREDITS"
    if resp.status_code == 422:
        print(f"[theirstack] request rejected: {resp.text[:300]}")
        return None
    resp.raise_for_status()
    return resp.json()


def fetch_company_job_counts(domain: str) -> dict | None:
    if not API_KEY:
        raise RuntimeError("THEIRSTACK_API_KEY not set")

    result = _post({
        "company_domain_or": [domain],
        "job_title_or": AI_JOB_TITLE_TERMS,
        "posted_at_max_age_days": 60,
        "limit": 1,
        "page": 0,
    })
    if result == "OUT_OF_CREDITS":
        return "STOP"
    if result and result.get("data"):
        company = result["data"][0].get("company_object", {})
        return {
            "jobs_overall": company.get("num_jobs"),
            "jobs_ai": company.get("num_jobs_found"),
            "jobs_last_30d": company.get("num_jobs_last_30_days"),
        }

    # No AI-titled job matched -- company_object only comes attached to a
    # returned job, so re-query without the title filter to at least get
    # the overall count, and record zero AI jobs.
    fallback = _post({
        "company_domain_or": [domain],
        "posted_at_max_age_days": 60,
        "limit": 1,
        "page": 0,
    })
    if fallback == "OUT_OF_CREDITS":
        return "STOP"
    if fallback and fallback.get("data"):
        company = fallback["data"][0].get("company_object", {})
        return {
            "jobs_overall": company.get("num_jobs"),
            "jobs_ai": 0,
            "jobs_last_30d": company.get("num_jobs_last_30_days"),
        }
    return {"jobs_overall": 0, "jobs_ai": 0, "jobs_last_30d": 0}


def fetch_all(companies: list[dict]) -> dict:
    results = {}
    for c in companies:
        counts = fetch_company_job_counts(c["domain"])
        if counts == "STOP":
            break
        if counts:
            results[c["ticker"]] = counts
        time.sleep(1)  # be polite to the API
    return results
