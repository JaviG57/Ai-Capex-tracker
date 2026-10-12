"""Confirm the endpoints the browser revealed:
  MSFT -> apply.careers.microsoft.com/api/pcsx/search (the correct Eightfold
          path; my earlier guess used the wrong one and got 'Not authorized')
  META -> rendered page counts, with and without a search query
"""
import json, pathlib, re, requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*",
      "Referer": "https://apply.careers.microsoft.com/careers",
      "Origin": "https://apply.careers.microsoft.com"}
out = {}

print("=== MSFT pcsx/search ===")
base = "https://apply.careers.microsoft.com/api/pcsx/search"
msft = {}
for label, q in [("all", ""), ("machine learning", "machine learning"),
                 ("artificial intelligence", "artificial intelligence")]:
    try:
        r = requests.get(base, headers=UA, timeout=40, params={
            "domain": "microsoft.com", "query": q, "location": "",
            "start": 0, "num": 10, "sort_by": "relevance"})
        d = r.json() if r.status_code == 200 else {}
        count = d.get("count") or d.get("total") or (d.get("hits") if isinstance(d.get("hits"), int) else None)
        positions = d.get("positions") or d.get("jobs") or []
        msft[label] = {"status": r.status_code, "count": count,
                       "returned": len(positions) if isinstance(positions, list) else None,
                       "keys": sorted(d.keys())[:12] if isinstance(d, dict) else None,
                       "sample_title": (positions[0].get("name") or positions[0].get("title"))
                                       if positions and isinstance(positions[0], dict) else None}
        print(f"  {label:26} status={r.status_code} count={count} returned={msft[label]['returned']}")
        print(f"     keys: {msft[label]['keys']}")
        if msft[label]["sample_title"]:
            print(f"     e.g. {msft[label]['sample_title'][:70]}")
    except Exception as e:
        msft[label] = {"error": str(e)[:120]}
        print(f"  {label}: ERROR {str(e)[:90]}")
out["MSFT"] = msft

print("\n=== META via rendered page ===")
try:
    from playwright.sync_api import sync_playwright
    meta = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(user_agent=UA["User-Agent"], viewport={"width": 1366, "height": 900})
        pg = ctx.new_page()
        for label, url in [
            ("all", "https://www.metacareers.com/jobs"),
            ("machine learning", "https://www.metacareers.com/jobs?q=%22machine%20learning%22"),
            ("ai", "https://www.metacareers.com/jobs?q=%22artificial%20intelligence%22"),
        ]:
            pg.goto(url, wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(4000)
            txt = pg.inner_text("body")
            pages = re.search(r"Page\s+1\s+of\s+([\d,]+)", txt)
            total = re.search(r"([\d,]+)\s+jobs?\b", txt, re.I)
            cards = pg.locator("a[href*='/jobs/']").count()
            meta[label] = {"pages": int(pages.group(1).replace(",", "")) if pages else None,
                           "explicit_total": int(total.group(1).replace(",", "")) if total else None,
                           "links_on_page": cards}
            print(f"  {label:24} pages={meta[label]['pages']} total={meta[label]['explicit_total']} links={cards}")
        ctx.close(); b.close()
    out["META"] = meta
except Exception as e:
    out["META"] = {"error": str(e)[:160]}
    print("  META ERROR", str(e)[:120])

pathlib.Path(__file__).resolve().parent.parent.joinpath("data/final_probe.json").write_text(
    json.dumps(out, indent=2, default=str))
