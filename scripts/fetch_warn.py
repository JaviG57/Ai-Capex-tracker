"""
WARN Act layoff notices for tracked companies.

The federal WARN Act requires employers to file notice ~60 days before a
mass layoff or plant closing. There is no national database -- each state
publishes its own, in its own format. We use Stanford Big Local News's
open-source `warn-scraper`, which maintains scrapers for 41 states.

Runs as a SEPARATE workflow (warn-scrape.yml) before the main daily run,
because state government sites are individually flaky; isolating this keeps
one broken state site from ever blocking the main pipeline. The main run
just reads the committed result file.

Matching: every cell of every notice row is searched for each company's
aliases, because column names differ by state (a CA "Company" column is a
TX "JOB_SITE_NAME" column). Exclusions stop false matches like Eaton Vance.

What this does and doesn't tell you: WARN catches large layoffs (generally
50+ people at one site) filed in covered states. It misses ordinary
attrition, small cuts, most layoffs outside the US, and any state not
covered. Treat a notice as a real downside event; treat silence as "no
large reported layoff", not as "no one left".

Output: data/warn_notices.json
"""
import csv
import datetime
import json
import pathlib
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

from companies import COMPANIES

STATE_TIMEOUT_S = 240
LOOKBACK_DAYS = 365
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "warn_notices.json"

DATE_COL_HINTS = ("date", "notice", "received", "effective", "layoff")
COUNT_COL_HINTS = ("employees", "affected", "number", "workers", "jobs", "count", "total")
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d %H:%M:%S",
                "%m/%d/%Y %H:%M", "%B %d, %Y", "%b %d, %Y", "%d-%b-%y", "%m-%d-%Y")


def list_states() -> list[str]:
    import pkgutil
    import warn.scrapers as s
    return sorted(m.name for m in pkgutil.iter_modules(s.__path__))


def scrape_state(state: str, data_dir: str) -> tuple[str, str | None, str]:
    try:
        r = subprocess.run(["warn-scraper", state, "--data-dir", data_dir, "-l", "error"],
                           capture_output=True, text=True, timeout=STATE_TIMEOUT_S)
        path = pathlib.Path(data_dir) / f"{state}.csv"
        if path.exists():
            return state, str(path), "ok"
        return state, None, f"no output (exit {r.returncode}): {r.stderr[-150:]}"
    except subprocess.TimeoutExpired:
        return state, None, "timeout"
    except Exception as e:
        return state, None, f"error: {e}"


def _parse_date(value: str):
    v = (value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(v[:len(fmt) + 8].strip(), fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", v)
    if m:
        mo, d, y = map(int, m.groups())
        y = y + 2000 if y < 100 else y
        try:
            return datetime.date(y, mo, d)
        except ValueError:
            return None
    return None


def _parse_int(value: str):
    m = re.search(r"\d[\d,]*", value or "")
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _compile_matchers():
    out = []
    for c in COMPANIES:
        inc = [re.compile(r"\b" + re.escape(a.lower()) + r"\b") for a in c.get("warn_aliases", [])]
        exc = [e.lower() for e in c.get("warn_exclude", [])]
        out.append((c["ticker"], inc, exc))
    return out


def match_notices(csv_path: str, state: str, matchers, cutoff: datetime.date) -> list[dict]:
    hits = []
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        date_cols = [h for h in headers if any(k in h.lower() for k in DATE_COL_HINTS)]
        count_cols = [h for h in headers if any(k in h.lower() for k in COUNT_COL_HINTS)]
        for row in reader:
            blob = " | ".join(str(v) for v in row.values() if v).lower()
            for ticker, inc, exc in matchers:
                if not any(p.search(blob) for p in inc):
                    continue
                if any(e in blob for e in exc):
                    continue
                notice_date = None
                for col in date_cols:
                    notice_date = _parse_date(row.get(col, ""))
                    if notice_date:
                        break
                if notice_date and notice_date < cutoff:
                    continue
                affected = None
                for col in count_cols:
                    affected = _parse_int(row.get(col, ""))
                    if affected:
                        break
                hits.append({
                    "ticker": ticker,
                    "state": state.upper(),
                    "date": notice_date.isoformat() if notice_date else None,
                    "employees_affected": affected,
                    "raw": dict(list({k: v for k, v in row.items() if v}.items())[:8]),
                })
    return hits


def main():
    states = list_states()
    cutoff = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
    matchers = _compile_matchers()
    status = {}
    notices = []

    with tempfile.TemporaryDirectory() as tmp:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda s: scrape_state(s, tmp), states))
        for state, path, msg in results:
            status[state] = msg
            if path:
                try:
                    notices.extend(match_notices(path, state, matchers, cutoff))
                except Exception as e:
                    status[state] = f"parse error: {e}"

    # De-duplicate: states often re-list amended notices.
    seen, unique = set(), []
    for n in notices:
        key = (n["ticker"], n["state"], n["date"], n["employees_affected"])
        if key not in seen:
            seen.add(key)
            unique.append(n)
    unique.sort(key=lambda n: n["date"] or "", reverse=True)

    ok = sum(1 for v in status.values() if v == "ok")
    payload = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "lookback_days": LOOKBACK_DAYS,
        "states_ok": ok,
        "states_total": len(states),
        "state_status": status,
        "notices": unique,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"WARN: {ok}/{len(states)} states scraped, {len(unique)} matching notices in last {LOOKBACK_DAYS}d")
    for n in unique[:15]:
        print(f"  {n['date']}  {n['ticker']:5} {n['state']}  affected={n['employees_affected']}")


if __name__ == "__main__":
    main()
