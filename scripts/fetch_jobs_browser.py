"""
Job counts for companies whose listings only exist after JavaScript runs.

Both MSFT and META serve a near-empty HTML shell and render listings
client-side, so plain HTTP sees nothing. Both are ALLOWED by their
robots.txt, and neither page carries a CAPTCHA -- we simply render the page
as a browser does and read public numbers.

MSFT: the page's own front-end calls apply.careers.microsoft.com/api/pcsx/search.
Called directly from a server that endpoint returns 429, but inside the page's
session it returns 200 -- so we run the request from within the page, which
also means titles can be paginated and filtered with the SAME AI-title rule
used for every other source.

META: its GraphQL call isn't safely replayable without reverse-engineering
query ids, so we read the result-page count the site displays. That yields an
APPROXIMATE figure (pages x page size), flagged as such rather than presented
as exact.

GOOGL is deliberately absent: google.com/robots.txt disallows the careers
results path, so it is not fetched at all.
"""
import datetime
import json

from fetch_jobs_theirstack import AI_JOB_TITLE_TERMS

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
META_PAGE_SIZE = 20  # metacareers shows 20 results per page


def _is_ai_title(title: str) -> bool:
    t = (title or "").lower()
    return any(all(w in t for w in term.lower().split()) for term in AI_JOB_TITLE_TERMS)


def _fetch_microsoft(page) -> dict | None:
    page.goto("https://jobs.careers.microsoft.com/global/en/search",
              wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    # Run the search from inside the page so its session/cookies apply.
    titles = page.evaluate("""async () => {
        const out = []; let start = 0, total = null;
        while (start < 4000) {
            const u = 'https://apply.careers.microsoft.com/api/pcsx/search'
                    + '?domain=microsoft.com&query=&location=&start=' + start
                    + '&num=100&sort_by=relevance';
            const r = await fetch(u, { credentials: 'include' });
            if (!r.ok) break;
            const d = await r.json();
            if (total === null) total = d.count ?? d.total ?? null;
            const rows = d.positions || d.jobs || [];
            if (!rows.length) break;
            for (const p of rows) out.push(p.name || p.title || '');
            start += rows.length;
            if (total !== null && start >= total) break;
            await new Promise(s => setTimeout(s, 300));
        }
        return { titles: out, total };
    }""")
    if not titles or not titles.get("titles"):
        return None
    ts = titles["titles"]
    total = titles.get("total") or len(ts)
    return {"jobs_overall": total,
            "jobs_ai": sum(1 for t in ts if _is_ai_title(t)),
            "jobs_source": "ms_careers_browser",
            "jobs_approx": False}


def _meta_count(page, url) -> int | None:
    import re
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3500)
    m = re.search(r"Page\s+1\s+of\s+([\d,]+)", page.inner_text("body"))
    return int(m.group(1).replace(",", "")) if m else None


def _fetch_meta(page) -> dict | None:
    pages_all = _meta_count(page, "https://www.metacareers.com/jobs")
    if not pages_all:
        return None
    ai_pages = 0
    for term in ["machine learning", "artificial intelligence"]:
        n = _meta_count(page, f"https://www.metacareers.com/jobs?q=%22{term.replace(' ', '%20')}%22")
        ai_pages = max(ai_pages, n or 0)   # max, not sum: the result sets overlap
    return {"jobs_overall": pages_all * META_PAGE_SIZE,
            "jobs_ai": ai_pages * META_PAGE_SIZE,
            "jobs_source": "metacareers_browser",
            "jobs_approx": True}


def fetch_all(companies) -> dict:
    tickers = {c["ticker"] for c in companies}
    results = {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[browser] playwright not installed -- skipping")
        return results

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900},
                                  locale="en-US")
        page = ctx.new_page()
        for tk, fn in (("MSFT", _fetch_microsoft), ("META", _fetch_meta)):
            if tk not in tickers:
                continue
            try:
                res = fn(page)
                if res:
                    results[tk] = res
                    flag = " (approx)" if res.get("jobs_approx") else ""
                    print(f"[browser] {tk}: {res['jobs_overall']} roles, "
                          f"{res['jobs_ai']} AI-titled{flag}")
                else:
                    print(f"[browser] {tk}: no data extracted")
            except Exception as e:
                print(f"[browser] {tk} failed: {str(e)[:140]}")
        ctx.close()
        browser.close()
    return results


if __name__ == "__main__":
    import pathlib
    import companies as cm
    res = fetch_all(cm.COMPANIES)
    pathlib.Path(__file__).resolve().parent.parent.joinpath(
        "data/browser_jobs_test.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2))
