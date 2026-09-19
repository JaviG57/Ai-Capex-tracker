"""
Entry point for the daily GitHub Action. Fetches every data source, merges
results into today's record, appends it to data/history.json, generates
the daily summary, and saves. The Action workflow commits the updated file.
"""
import datetime
import os
import pathlib
import json
import traceback

import companies as companies_module
import fetch_jobs_theirstack
import fetch_market_data
import fetch_sec_edgar
import fetch_github_activity
import fetch_grid_load
import fetch_cloud_pricing
import storage
import generate_summary


def main():
    today_str = datetime.date.today().isoformat()
    companies = companies_module.COMPANIES
    print(f"=== AI Capex Tracker daily run: {today_str} ===")

    print("-> TheirStack job postings")
    debug_limit = int(os.environ.get("THEIRSTACK_DEBUG_LIMIT", "0"))
    theirstack_companies = companies[:debug_limit] if debug_limit else companies
    debug_path = (pathlib.Path(__file__).resolve().parent.parent / "data" / "debug_theirstack.json")
    try:
        jobs = fetch_jobs_theirstack.fetch_all(theirstack_companies)
        debug_payload = {
            "error": None,
            "companies_queried": [c["ticker"] for c in theirstack_companies],
            "jobs_returned": jobs,
            "request_log": fetch_jobs_theirstack._DEBUG_LOG,
        }
    except Exception as e:
        jobs = {}
        debug_payload = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "companies_queried": [c["ticker"] for c in theirstack_companies],
            "request_log": fetch_jobs_theirstack._DEBUG_LOG,
        }
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(json.dumps(debug_payload, indent=2, default=str))
    print(f"-> wrote debug file to {debug_path} ({debug_path.stat().st_size} bytes)")

    print("-> Market data (price/volume)")
    market = fetch_market_data.fetch_all(companies)

    print("-> SEC EDGAR 8-K filings")
    sec = fetch_sec_edgar.fetch_all(companies, today_str)

    print("-> GitHub AI-repo activity (macro)")
    github_activity = fetch_github_activity.fetch_all(companies_module.GITHUB_AI_REPOS)

    print("-> Grid load (stub)")
    grid = fetch_grid_load.fetch_all()

    print("-> Cloud GPU pricing (stub)")
    cloud = fetch_cloud_pricing.fetch_all()

    # Merge per-company metrics
    per_company = {}
    for c in companies:
        t = c["ticker"]
        merged = {}
        merged.update(jobs.get(t, {}))
        merged.update(market.get(t, {}))
        merged.update(sec.get(t, {}))
        if merged:
            per_company[t] = merged

    # Macro / ecosystem-level metrics (not per-company)
    macro = {}
    for repo, metrics in github_activity.items():
        macro[repo] = metrics
    macro.update(grid)
    macro.update(cloud)

    today_record = {
        "date": today_str,
        "companies": per_company,
        "macro": macro,
    }

    history = storage.load_history()
    history = storage.upsert_today(history, today_record)

    print("-> Computing trend deltas")
    deltas = storage.compute_deltas(history)

    print("-> Generating daily summary (Claude Sonnet 5)")
    # Tell the summary writer when prices are carried over from a prior
    # session, so it doesn't narrate a closed market as a flat trading day.
    price_dates = {m.get("price_date") for m in per_company.values() if m.get("price_date")}
    context_note = ""
    if price_dates and today_str not in price_dates:
        last_close = sorted(price_dates)[-1]
        context_note = (
            f"NOTE: Today is {today_str} and US markets were CLOSED (weekend or holiday). "
            f"All stock prices shown are the last close from {last_close}, carried over. "
            f"Do not describe price levels as today's trading action, and do not treat the "
            f"absence of price movement as a market signal. Focus on non-market metrics."
        )
        print(f"   (markets closed today; prices carried from {last_close})")
    summary = generate_summary.generate(deltas, context_note)
    history[-1]["summary"] = summary

    storage.save_history(history)
    print("Done. data/history.json updated.")

    # Company metadata (name/group) for the dashboard's grouped layout --
    # written fresh each run so it's always in sync with companies.py.
    meta_path = pathlib.Path(__file__).resolve().parent.parent / "data" / "companies_meta.json"
    meta_path.write_text(json.dumps(companies, indent=2))
    print("\n--- Summary preview ---\n" + summary)


if __name__ == "__main__":
    main()
