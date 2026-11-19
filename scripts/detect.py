"""Flags days where |SPX standardized AR| > 2 since the inauguration → data/candidates.json.
Run: python3 scripts/detect.py
"""
import json, os
from event_study import load_prices, spx_ar

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "candidates.json")
START, THRESH = "2025-01-21", 2.0

px, rets = load_prices()
A = spx_ar(rets)
hits = A[(A.index >= START) & (A.sar.abs() > THRESH)]
rows = [{"date": d, "ret": round(r.ret * 100, 3), "ar": round(r.ar * 100, 3), "sar": round(r.sar, 2)} for d, r in hits.iterrows()]
json.dump(rows, open(OUT, "w"), indent=1)
print(f"{len(rows)} candidate days with |SAR| > {THRESH} since {START}")
