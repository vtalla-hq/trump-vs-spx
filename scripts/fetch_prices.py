"""Pulls daily closes for SPX, VIX, 10Y and sector ETFs into public/data/daily.json.
Run: python3 scripts/fetch_prices.py
"""
import json, os, datetime as dt
import yfinance as yf

TICKERS = ["^GSPC", "^VIX", "^TNX", "XLE", "ITA", "SOXX", "FXI"]
OUT = os.path.join(os.path.dirname(__file__), "..", "public", "data", "daily.json")

df = yf.download(TICKERS, start="2024-01-01", end=str(dt.date.today() + dt.timedelta(days=1)),
                 auto_adjust=True, progress=False)["Close"].dropna(subset=["^GSPC"])
assert len(df) > 200 and not df.empty, "yfinance returned too little data"
rows = [{"date": str(d.date()), **{t: (None if v != v else round(float(v), 4)) for t, v in r.items()}}
        for d, r in df[TICKERS].iterrows()]
json.dump(rows, open(OUT, "w"), indent=0)
print(f"{len(rows)} days, {rows[0]['date']} → {rows[-1]['date']}")
