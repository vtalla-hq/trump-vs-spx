"""Event study on public/data/events.json using public/data/daily.json → public/data/study.json.

SPX: constant-mean model. Sectors: market model vs SPX. Estimation window [-120, -11] trading days.
Run: python3 scripts/event_study.py
"""
import json, os, datetime as dt
import numpy as np
import pandas as pd

D = os.path.join(os.path.dirname(__file__), "..", "public", "data") + "/"
EST = (-120, -11)
WINDOWS = {"0,0": 0, "0,1": 1, "0,5": 5}
SECTORS = ["XLE", "ITA", "SOXX", "FXI"]
TOPICS = ["Tariffs", "Iran war", "Fed"]
N_PERM, SEED = 10_000, 7
# Threat day → the event where he walked it back. e21 was walked back the same day, e24 never: both exit after 5 days.
WALKBACK = {"e02": "e05", "e23": "e08", "e09": "e10", "e11": "e12"}
MAX_HOLD = 5


def load_prices():
    df = pd.DataFrame(json.load(open(D + "daily.json"))).set_index("date").sort_index()
    return df, df.pct_change()


def spx_ar(rets):
    """Constant-mean AR and standardized AR for every day (NaN until 120 days of history)."""
    r = rets["^GSPC"]
    est = r.shift(-EST[1]).rolling(EST[1] - EST[0] + 1)  # window ending at t-11
    mu, sd = est.mean(), est.std()
    ar = r - mu
    return pd.DataFrame({"ret": r, "mu": mu, "sd": sd, "ar": ar, "sar": ar / sd})


def r4(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 4)


def event_row(e, i, rets, px, A):
    lo, hi = i + EST[0], i + EST[1]
    assert lo >= 1, f"{e['id']}: not enough history for estimation window"
    a = A.iloc[i]
    assert abs(a.mu - rets["^GSPC"].iloc[lo:hi + 1].mean()) < 1e-12, "rolling window misaligned"
    car = lambda s, k: r4(s.iloc[i:i + k + 1].sum() * 100) if i + k < len(s) else None
    out = {"id": e["id"], "date": e["date"], "topic": e["topic"],
           "spx": {"ret": r4(a.ret * 100), "ar": r4(a.ar * 100), "sar": r4(a.sar),
                   "car": {w: car(A.ar, k) for w, k in WINDOWS.items()}},
           "vix_chg": r4(px["^VIX"].iloc[i] - px["^VIX"].iloc[i - 1]),
           "tnx_bps": r4((px["^TNX"].iloc[i] - px["^TNX"].iloc[i - 1]) * 100),  # ^TNX is yield in %
           "sectors": {}}
    m = rets["^GSPC"].iloc[lo:hi + 1]
    for t in SECTORS:
        y = rets[t].iloc[lo:hi + 1]
        beta, alpha = np.polyfit(m, y, 1)
        ar = rets[t] - (alpha + beta * rets["^GSPC"])
        out["sectors"][t] = {"alpha": r4(alpha * 100), "beta": r4(beta), "ar": r4(ar.iloc[i] * 100),
                             "car": {w: car(ar, k) for w, k in WINDOWS.items()}}
    return out


def permutation(abs_ar, event_idx, pool, rng):
    """Mean |AR| of the event days vs N_PERM random draws of the same number of non-event days."""
    n = len(event_idx)
    obs = abs_ar[event_idx].mean()
    null = np.array([abs_ar[rng.choice(pool, n, replace=False)].mean() for _ in range(N_PERM)])
    counts, edges = np.histogram(null, bins=40)
    return {"n": n, "event_mean_abs_ar": r4(obs * 100), "null_mean_abs_ar": r4(null.mean() * 100),
            "null_p95": r4(np.percentile(null, 95) * 100),
            "p_value": r4((np.sum(null >= obs) + 1) / (N_PERM + 1)),
            "hist": {"edges": [r4(x * 100) for x in edges], "counts": counts.tolist()}}


def backtest(events, idx, px):
    close, trades = px["^GSPC"], []
    for e in (e for e in events if e.get("threat_day")):
        i = idx[e["date"]]
        wb = WALKBACK.get(e["id"])
        j = idx[next(x["date"] for x in events if x["id"] == wb)] if wb else i + MAX_HOLD
        if j >= len(close):
            continue  # still open
        hold = j - i
        # Baseline: mean SPX return over every same-length holding period in the sample.
        base = (close.shift(-hold) / close - 1).dropna().mean()
        ret = close.iloc[j] / close.iloc[i] - 1
        trades.append({"id": e["id"], "entry": e["date"], "exit": close.index[j], "walkback": wb, "hold_days": hold,
                       "ret": r4(ret * 100), "baseline": r4(base * 100), "excess": r4((ret - base) * 100)})
    r = np.array([t["ret"] for t in trades]) / 100
    hold = np.mean([t["hold_days"] for t in trades])
    sharpe = r.mean() / r.std(ddof=1) * np.sqrt(252 / hold) if len(r) > 1 else None
    return {"rule": "Long SPX at the threat-day close; exit at the walk-back day's close, or after 5 trading days if none.",
            "n": len(trades), "trades": trades, "hit_rate": r4((r > 0).mean()), "avg_ret": r4(r.mean() * 100),
            "avg_baseline": r4(np.mean([t["baseline"] for t in trades])), "avg_hold_days": r4(hold),
            "sharpe_annualized": r4(sharpe),
            "caveat": f"n={len(trades)} trades. Annualized Sharpe from {len(trades)} points is noise, not evidence."}


def main():
    events = json.load(open(D + "events.json"))
    px, rets = load_prices()
    A = spx_ar(rets)
    idx = {d: k for k, d in enumerate(px.index)}
    for e in events:
        assert e["date"] in idx, f"{e['id']} {e['date']} is not a trading day"

    rows = [event_row(e, idx[e["date"]], rets, px, A) for e in events]

    abs_ar = A.ar.abs().to_numpy()
    ev_idx = np.array([idx[e["date"]] for e in events])
    pool = np.setdiff1d(np.where(np.isfinite(abs_ar))[0], ev_idx)
    rng = np.random.default_rng(SEED)
    perm = {"overall": permutation(abs_ar, ev_idx, pool, rng), "pool_days": len(pool), "draws": N_PERM}
    perm["by_topic"] = {t: permutation(abs_ar, np.array([idx[e["date"]] for e in events if e["topic"] == t]), pool, rng)
                        for t in TOPICS}

    study = {"generated": str(dt.date.today()), "last_price_date": px.index[-1],
             "method": {"estimation_window": list(EST), "spx_model": "constant mean", "sector_model": "market model vs ^GSPC (OLS)",
                        "windows": list(WINDOWS), "units": "AR/CAR in %, vix_chg in points, tnx_bps in basis points"},
             "events": rows, "permutation": perm, "backtest": backtest(events, idx, px)}
    json.dump(study, open(D + "study.json", "w"), ensure_ascii=False, indent=1)
    p, b = perm["overall"], study["backtest"]
    print(f"events n={p['n']}: mean|AR| {p['event_mean_abs_ar']}% vs null {p['null_mean_abs_ar']}%  p={p['p_value']}")
    print(f"TACO n={b['n']}: avg {b['avg_ret']}% (baseline {b['avg_baseline']}%), hit {b['hit_rate']}, Sharpe {b['sharpe_annualized']}")


if __name__ == "__main__":
    main()
