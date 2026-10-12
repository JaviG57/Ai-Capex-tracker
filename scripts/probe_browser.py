"""
Render MSFT and META careers pages in a real browser (Playwright/Chromium)
and extract job counts.

Why a browser: both pages are JavaScript applications. Plain HTTP returns a
near-empty shell -- the listings are fetched and rendered client-side, so
there is literally nothing in the HTML to parse. Executing the page is the
only way to see what a human sees.

Both are ALLOWED by their robots.txt (checked in probe_big3b). Neither has a
CAPTCHA on these pages. This renders the page as a browser would, at human
pace, and reads the public result count. Google is deliberately EXCLUDED:
its robots.txt disallows the careers results path.

Also captures the XHR calls the page makes, since a stable JSON endpoint
would be far better than scraping rendered text day after day.
"""
import json, pathlib, re

from playwright.sync_api import sync_playwright

TARGETS = {
    "MSFT": {"url": "https://jobs.careers.microsoft.com/global/en/search",
             "ai_url": "https://jobs.careers.microsoft.com/global/en/search?q=%22machine%20learning%22"},
    "META": {"url": "https://www.metacareers.com/jobs",
             "ai_url": "https://www.metacareers.com/jobs?q=%22machine%20learning%22"},
}

COUNT_RE = [
    r"([\d,]+)\s*(?:\+)?\s*(?:results?|jobs?|openings?|positions?)\b",
    r"(?:of|about)\s+([\d,]+)\b",
    r"Showing\s+[\d,]+\s*(?:-|–|to)\s*[\d,]+\s+of\s+([\d,]+)",
]


def harvest(page, label):
    text = page.inner_text("body")[:6000]
    cands = []
    for p in COUNT_RE:
        for m in re.finditer(p, text, re.I):
            try:
                cands.append((int(m.group(1).replace(",", "")), text[max(0, m.start()-60):m.end()+30]))
            except ValueError:
                pass
    cands = [c for c in cands if 10 <= c[0] <= 100000]
    return {"text_head": re.sub(r"\s+", " ", text[:500]), "candidates": cands[:6]}


def main():
    out = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        for tk, cfg in TARGETS.items():
            out[tk] = {}
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 900}, locale="en-US")
            page = ctx.new_page()
            xhr = []
            page.on("response", lambda r: xhr.append((r.request.method, r.url, r.status))
                    if any(k in r.url for k in ("/api/", "search", "jobs", "graphql"))
                    and r.request.resource_type in ("xhr", "fetch") else None)
            for key in ("url", "ai_url"):
                try:
                    page.goto(cfg[key], wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(4000)
                    out[tk][key] = harvest(page, tk)
                    print(f"\n--- {tk} {key} ---")
                    print("  head:", out[tk][key]["text_head"][:200])
                    for n, ctxt in out[tk][key]["candidates"]:
                        print(f"   candidate {n}: ...{re.sub(r's+', ' ', ctxt)[-70:]}")
                except Exception as e:
                    out[tk][key] = {"error": str(e)[:150]}
                    print(f"  {tk} {key} ERROR {str(e)[:100]}")
            seen, uniq = set(), []
            for meth, u, st in xhr:
                base = u.split("?")[0]
                if base not in seen:
                    seen.add(base); uniq.append((meth, u[:150], st))
            out[tk]["xhr"] = uniq[:12]
            print(f"  XHR endpoints seen for {tk}:")
            for meth, u, st in uniq[:12]:
                print(f"    {meth} {st} {u}")
            ctx.close()
        browser.close()
    pathlib.Path(__file__).resolve().parent.parent.joinpath("data/browser_probe.json").write_text(
        json.dumps(out, indent=2, default=str))
    print("\nwrote data/browser_probe.json")


if __name__ == "__main__":
    main()
