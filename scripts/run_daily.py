"""
Entry point for the daily GitHub Action. Fetches every data source, merges
results into today's record, appends it to data/history.json, generates
the daily summary, and saves. The Action workflow commits the updated file.
"""
import datetime

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
    jobs = fetch_jobs_theirstack.fetch_all(companies)

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
    summary = generate_summary.generate(deltas)
    history[-1]["summary"] = summary

    storage.save_history(history)
    print("Done. data/history.json updated.")
    print("\n--- Summary preview ---\n" + summary)


if __name__ == "__main__":
    main()
