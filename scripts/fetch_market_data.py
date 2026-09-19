"""
Daily close price per ticker, via the `yfinance` package. No API key needed.

IMPORTANT -- market-closed days:
Yahoo returns the most recent TRADING day's bar. On a weekend or holiday
that's Friday's (or the last open day's) close, not today's. We therefore
record the bar's own date as `price_date` so the rest of the pipeline can
tell a genuinely new close from a stale one carried over from the last
open session. Without this, a Saturday run looks like "prices unchanged
today" when in fact no trading happened at all.

Volume is deliberately NOT collected. It added noise without signal: runs
at different times of day capture partial vs. full sessions, producing
enormous fake day-over-day "changes" that swamped the daily summary.
"""
import yfinance as yf


def fetch_all(companies: list[dict]) -> dict:
    tickers = [c["ticker"] for c in companies]
    results = {}
    try:
        data = yf.download(
            tickers=tickers, period="5d", interval="1d",
            group_by="ticker", progress=False, threads=True,
        )
    except Exception as e:
        print(f"[market] bulk download failed: {e}")
        return results

    for c in companies:
        t = c["ticker"]
        try:
            series = data[t].dropna()
            row = series.iloc[-1]
            bar_date = series.index[-1].date().isoformat()
            results[t] = {
                "stock_price": round(float(row["Close"]), 2),
                "price_date": bar_date,
            }
        except Exception as e:
            print(f"[market] no data for {t}: {e}")
    return results
