"""
Daily close price + volume per ticker, via the `yfinance` package.
No API key needed. This is an unofficial wrapper around Yahoo Finance's
public endpoints -- reliable for personal/analytical use, but treat it as
best-effort (Yahoo can change its backend without notice).
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
            row = data[t].dropna().iloc[-1]
            results[t] = {
                "stock_price": round(float(row["Close"]), 2),
                "stock_volume": int(row["Volume"]),
            }
        except Exception as e:
            print(f"[market] no data for {t}: {e}")
    return results
