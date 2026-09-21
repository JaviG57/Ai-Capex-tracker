"""Read/write data/history.json and compute 1d/7d/30d % deltas per metric."""
import json
import os

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")


def load_history() -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, "r") as f:
        return json.load(f)


def save_history(history: list[dict]) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def upsert_today(history: list[dict], today_record: dict) -> list[dict]:
    """
    Merge today's entry if one already exists, else append.

    MERGE (not replace) matters: if a run fetches only some sources -- a
    rate-limited API, a debug run limited to a few companies, a transient
    outage -- replacing would silently discard metrics an earlier run that
    day already collected successfully. Merging keeps whatever we had and
    layers the new values on top.
    """
    today = today_record["date"]
    existing = next((h for h in history if h["date"] == today), None)
    if existing:
        merged = dict(existing)
        for section in ("companies", "macro"):
            section_merged = dict(existing.get(section, {}))
            for entity, metrics in today_record.get(section, {}).items():
                combined = dict(section_merged.get(entity, {}))
                combined.update({k: v for k, v in metrics.items() if v is not None})
                section_merged[entity] = combined
            merged[section] = section_merged
        for key, value in today_record.items():
            if key not in ("companies", "macro"):
                merged[key] = value
        history = [h for h in history if h["date"] != today]
        history.append(merged)
    else:
        history.append(today_record)
    history.sort(key=lambda h: h["date"])
    return history


def _pct_change(old, new):
    if old in (None, 0) or new is None:
        return None
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
        return None
    return round((new - old) / old * 100, 1)


def compute_deltas(history: list[dict], lookback_days: tuple = (1, 7, 30)) -> dict:
    """
    Returns a compact structure of {entity: {metric: {current, d1, d7, d30}}}
    for every company + macro metric, comparing today's values against the
    entries `lookback_days` ago. This is what gets sent to Claude for the
    daily summary -- NOT the full raw history -- to keep input tokens small.

    `price_date` is excluded from the output (it's bookkeeping, not a
    metric), but it IS used to suppress stale price deltas: on a weekend or
    holiday the price carried over from the last open session would
    otherwise be reported as a real 0% "move today", implying trading
    happened when it didn't.
    """
    if not history:
        return {}
    today = history[-1]
    deltas = {}

    def _get_metric_series(section: str):
        series = {}
        for entry in history:
            for entity, metrics in entry.get(section, {}).items():
                series.setdefault(entity, {})
                for metric, value in metrics.items():
                    series[entity].setdefault(metric, {})[entry["date"]] = value
        return series

    for section in ("companies", "macro"):
        series = _get_metric_series(section)
        dates = [h["date"] for h in history]
        for entity, metrics in series.items():
            price_dates = metrics.get("price_date", {})
            for metric, by_date in metrics.items():
                # Annual 10-K headcount is flat day to day; trending it would
                # just feed the summary a wall of "0% change" noise.
                if metric in ("price_date", "headcount"):
                    continue
                current = by_date.get(today["date"])
                # Only numeric metrics get trend deltas. Labels like
                # jobs_source ("greenhouse") or dates are bookkeeping, and
                # doing arithmetic on them would crash the run.
                if current is None or isinstance(current, bool) or not isinstance(current, (int, float)):
                    continue
                key = f"{section}.{entity}.{metric}"
                row = {"current": current}
                for n in lookback_days:
                    idx = len(dates) - 1 - n
                    if idx < 0:
                        continue
                    past_date = dates[idx]
                    if metric == "stock_price" and price_dates:
                        # Same underlying trading session -> not a real move.
                        if price_dates.get(today["date"]) == price_dates.get(past_date):
                            continue
                    row[f"d{n}"] = _pct_change(by_date.get(past_date), current)
                deltas[key] = row
    return deltas
