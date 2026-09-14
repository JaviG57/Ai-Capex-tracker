"""
Daily commit counts for a curated set of major AI infra open-source repos
(scripts/companies.py -> GITHUB_AI_REPOS). This is a macro/ecosystem signal,
not tied to a specific ticker.

Uses the public GitHub REST API. An unauthenticated request is limited to
60/hour, which is plenty for 6 repos/day -- but if you add a GITHUB_TOKEN
repo secret (any token works, no special scopes needed), the workflow will
use it automatically and get a much higher rate limit for free.
"""
import os
import datetime
import requests

HEADERS = {"Accept": "application/vnd.github+json"}
if os.environ.get("GITHUB_TOKEN"):
    HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"


def fetch_all(repos: list[str]) -> dict:
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat() + "Z"
    results = {}
    for repo in repos:
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/commits",
                params={"since": since, "per_page": 100},
                headers=HEADERS, timeout=30,
            )
            resp.raise_for_status()
            results[repo] = {"commits_last_24h": len(resp.json())}
        except Exception as e:
            print(f"[github] failed for {repo}: {e}")
    return results
