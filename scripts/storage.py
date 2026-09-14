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
    """Replace today's entry if the workflow re-runs same-day, else append."""
    today = today_record["date"]
    history = [h for h in history if h["date"] != today]
    history.append(today_record)
    history.sort(key=lambda h: h["date"])
    return history


def _pct_change(old, new):
    if old in (None, 0) or new is None:
        return None
    return round((new - old) / old * 100, 1)


def compute_deltas(history: list[dict], lookback_days: tuple = (1, 7, 30)) -> dict:
    """
    Returns a compact structure of {entity: {metric: {current, d1, d7, d30}}}
    for every company + macro metric, comparing today's values against the
    entries `lookback_days` ago. This is what gets sent to Claude for the
    daily summary -- NOT the full raw history -- to keep input tokens small.
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
            for metric, by_date in metrics.items():
                current = by_date.get(today["date"])
                if current is None:
                    continue
                key = f"{section}.{entity}.{metric}"
                row = {"current": current}
                for n in lookback_days:
                    idx = len(dates) - 1 - n
                    if idx >= 0:
                        past_value = by_date.get(dates[idx])
                        row[f"d{n}"] = _pct_change(past_value, current)
                deltas[key] = row
    return deltas
