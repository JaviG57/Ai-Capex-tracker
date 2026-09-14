# AI Capex Signal Tracker

Fully automated daily tracker for AI-capex-related leading indicators
(hiring, spending signals, ecosystem dev activity, market data) across a
tracked list of hyperscalers, chipmakers, infra/OEM, and power/data-center
companies. Runs on a schedule with no manual steps once set up.

## How it's wired together

```
GitHub Actions (daily cron)
  -> scripts/run_daily.py
       -> fetch_jobs_theirstack.py   (TheirStack API)
       -> fetch_market_data.py      (yfinance)
       -> fetch_sec_edgar.py        (SEC EDGAR, official API)
       -> fetch_github_activity.py  (GitHub API)
       -> fetch_grid_load.py        (stub -- not yet implemented)
       -> fetch_cloud_pricing.py    (stub -- not yet implemented)
       -> generate_summary.py       (Claude Sonnet 5, via Anthropic API)
  -> writes data/history.json
  -> commits it back to the repo
GitHub Pages serves /dashboard/index.html, which fetches data/history.json
```

Nothing needs to run on your own machine. Once the repo is set up, the
Action fires daily on its own and the dashboard always reflects the latest
commit.

## One-time setup

1. **Create the repo.** Push this folder to a new GitHub repository.

2. **Get a TheirStack API key.**
   Sign up at https://app.theirstack.com/signup (free tier: 200 credits/month).

3. **Get an Anthropic API key.**
   Create one at https://platform.claude.com (used only for the daily
   summary -- costs roughly $4-5/year at this data volume).

4. **Add repo secrets** (Settings -> Secrets and variables -> Actions):
   - `THEIRSTACK_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `SEC_CONTACT_EMAIL` -- any real contact email; SEC requires a
     descriptive User-Agent on their API, this just fills that in.
   - `GITHUB_TOKEN` is provided automatically by Actions -- no setup needed,
     it's used both to push the daily commit and (optionally) to raise the
     GitHub API rate limit for the ecosystem-activity fetcher.

5. **Enable GitHub Pages.** Settings -> Pages -> Deploy from branch ->
   `main` -> `/ (root)`. Your dashboard will be live at
   `https://<you>.github.io/<repo>/dashboard/`.

6. **Enable the workflow.** It's already scheduled (`.github/workflows/daily-scrape.yml`,
   13:00 UTC daily) -- GitHub Actions is on by default for new repos. You
   can also trigger it manually from the Actions tab any time
   ("Run workflow" button) to test it without waiting for the schedule.

## Important: TheirStack credit budget

Tracking all 18 companies daily costs ~18 TheirStack credits/day (one query
per company). The free tier (200 credits/month) covers about 11 days of
full coverage before running out mid-month. Your options, in
`scripts/fetch_jobs_theirstack.py`:

- Upgrade to TheirStack's paid tier for full-month daily coverage.
- Wire in `pick_todays_subset()` (already written, just not called yet) to
  round-robin a subset of companies each day instead of querying all 18.
- Shrink the company list in `scripts/companies.py`.

The script won't crash when credits run out -- it logs a warning and skips
the rest of that day's job-posting fetch, so every other metric still
updates normally.

## What's stubbed, not yet built

- **Grid/ISO power load** (PJM, ERCOT) -- `fetch_grid_load.py` documents
  the plan and links, but isn't implemented; both feeds need
  provider-specific setup worth verifying against current docs first.
- **Cloud GPU spot pricing** -- `fetch_cloud_pricing.py`, same situation;
  this is also the most scrape-fragile source in the whole list, so it's
  worth building last.
- **LinkedIn headcount, options implied vol, Google Trends** -- discussed
  and intentionally left out of this version; can be added the same way
  as the other fetchers if you want them back in.

## Editing the company list

Edit `scripts/companies.py`. Every fetcher reads from that one file, so
adding/removing a company is a one-line change.

## Editing what counts as an "AI job"

Edit `AI_JOB_TITLE_TERMS` in `scripts/fetch_jobs_theirstack.py`.
