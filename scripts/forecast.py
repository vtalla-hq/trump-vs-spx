"""Walk-back forecaster and prediction ledger → public/data/forecast.json, new ledger rows on stdout.

- p(walk-back): L2 logistic regression on resolved deadlines (data/deadlines.json), one row per trading day a
  deadline was pending (weights sum to 1 per deadline). Walk-forward backtest vs the past base rate.
- Expected move: bootstrap 80% intervals of S&P abnormal returns by topic / tag / resolution outcome.
- Ledger: data/predictions.jsonl is append-only. This script never writes it: it prints new rows (predictions,
  resolutions, move results) as JSON lines, and the daily workflow appends and commits each one separately.
Run: python3 scripts/forecast.py >> data/predictions.jsonl   (logs go to stderr)
"""
import json, os, sys, datetime as dt
import numpy as np
import requests
from event_study import load_prices, spx_ar

MODEL_VERSION = "wb-logit-l2-v1/move-boot-v1"
LAMBDA = 1.0          # L2 penalty on standardized coefficients
MIN_TRAIN = 4         # resolved deadlines needed before the model forecasts at all
N_BOOT, SEED = 2000, 7
WALKBACK = {"walked_back", "extended"}  # TACO: dropping or delaying both count
FEATURES = ["is_tariff", "log_threat", "days_to_deadline", "car_since", "d10y_bps", "dvix", "prior_wb_same_target"]
ROOT = os.path.join(os.path.dirname(__file__), "..")
P = lambda *a: os.path.join(ROOT, *a)
log = lambda *a: print(*a, file=sys.stderr)
r4 = lambda x: None if x is None or not np.isfinite(x) else round(float(x), 4)


def fit_logit(X, y, w, lam=LAMBDA):
    """Weighted L2 logistic regression by Newton steps; intercept unpenalized; X standardized."""
    X1 = np.c_[np.ones(len(X)), X]
    pen = np.r_[0.0, np.full(X.shape[1], lam)]
    b = np.zeros(X1.shape[1])
    for _ in range(100):
        p = 1 / (1 + np.exp(-X1 @ b))
        step = np.linalg.solve((X1 * (w * p * (1 - p))[:, None]).T @ X1 + np.diag(pen), X1.T @ (w * (p - y)) + pen * b)
        b -= step
        if np.abs(step).max() < 1e-10:
            break
    return b


def brier(p, y):
    return r4(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def logloss(p, y):
    p, y = np.clip(np.asarray(p, float), 1e-3, 1 - 1e-3), np.asarray(y)
    return r4(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


# Self-checks: the penalized gradient is zero at the fit, and a perfect forecast scores 0.
_X = np.array([[0.], [1.], [2.], [3.]]); _y = np.array([0., 0., 1., 1.]); _w = np.ones(4); _b = fit_logit(_X, _y, _w)
_p = 1 / (1 + np.exp(-(_b[0] + _b[1] * _X[:, 0])))
assert abs(np.sum(_p - _y)) < 1e-8 and abs(_X[:, 0] @ (_p - _y) + LAMBDA * _b[1]) < 1e-8
assert brier([1, 0], [1, 0]) == 0 and logloss([.5], [1]) == r4(np.log(2))


class Market:
    """Prices, ARs and the date index, loaded once."""
    def __init__(self):
        self.px, rets = load_prices()
        self.ar = spx_ar(rets).ar.to_numpy() * 100
        self.dates = np.array(self.px.index)
        self.vix, self.tnx = self.px["^VIX"].to_numpy(), self.px["^TNX"].to_numpy()

    def idx(self, date):
        """First trading day on or after date, or None if it isn't in the data yet."""
        i = int(np.searchsorted(self.dates, date))
        return i if i < len(self.dates) else None


def features(d, t, m, deadlines):
    """Features for deadline d as of trading-day index t (close-to-close, known at that close)."""
    a = m.idx(d["announced"])
    target = (d["target"] or "").lower()
    prior = sum(x["status"] in WALKBACK for x in deadlines
                if x is not d and (x["target"] or "").lower() == target and x["resolved_on"] and x["resolved_on"] < d["announced"])
    return {"is_tariff": float(d["topic"] == "Tariffs"), "log_threat": float(np.log1p(d.get("threat_size") or 0)),
            "days_to_deadline": float((dt.date.fromisoformat(d["deadline"]) - dt.date.fromisoformat(m.dates[t])).days),
            "car_since": float(np.nansum(m.ar[a:t + 1])), "d10y_bps": float((m.tnx[t] - m.tnx[a - 1]) * 100),
            "dvix": float(m.vix[t] - m.vix[a - 1]), "prior_wb_same_target": float(prior)}


def panel(resolved, m, deadlines):
    """One row per trading day each resolved deadline was pending (always at least its announcement day)."""
    X, y, w = [], [], []
    for d in resolved:
        a = m.idx(d["announced"])
        days = [t for t in range(a, len(m.dates)) if m.dates[t] < d["resolved_on"] and m.dates[t] <= d["deadline"]] or [a]
        for t in days:
            X.append([features(d, t, m, deadlines)[f] for f in FEATURES]); y.append(d["status"] in WALKBACK); w.append(1 / len(days))
    return np.array(X), np.array(y, float), np.array(w)


def train(resolved, m, deadlines):
    X, y, w = panel(resolved, m, deadlines)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1  # e.g. every training deadline is a tariff
    return {"b": fit_logit((X - mu) / sd, y, w), "mu": mu, "sd": sd, "n": len(resolved), "base": float(y @ w / w.sum())}


def predict(model, f):
    z = (np.array([f[k] for k in FEATURES]) - model["mu"]) / model["sd"]
    return float(1 / (1 + np.exp(-(model["b"][0] + model["b"][1:] @ z))))


def backtest(resolved, m, deadlines):
    """Walk-forward: forecast each deadline on its announcement day using only deadlines resolved before then."""
    preds = []
    for d in sorted(resolved, key=lambda x: x["announced"]):
        past = [x for x in resolved if x["resolved_on"] < d["announced"]]
        if len(past) < MIN_TRAIN:
            continue
        model = train(past, m, deadlines)
        preds.append({"id": d["id"], "announced": d["announced"], "y": int(d["status"] in WALKBACK), "n_train": len(past),
                      "p": r4(predict(model, features(d, m.idx(d["announced"]), m, deadlines))), "base": r4(model["base"])})
    p, b, y = [x["p"] for x in preds], [x["base"] for x in preds], [x["y"] for x in preds]
    out = {"n": len(preds), "n_resolved": len(resolved), "min_train": MIN_TRAIN, "preds": preds, "calibration": calibration(p, y)}
    if preds:
        out |= {"brier": {"model": brier(p, y), "base": brier(b, y)}, "logloss": {"model": logloss(p, y), "base": logloss(b, y)}}
        out["beats_base"] = out["brier"]["model"] < out["brier"]["base"] and out["logloss"]["model"] < out["logloss"]["base"]
    return out


def calibration(p, y, edges=(0, .2, .4, .6, .8, 1.0001)):
    p, y = np.asarray(p, float), np.asarray(y, float)
    return [{"lo": lo, "hi": min(hi, 1), "n": int(k.sum()), "mean_p": r4(p[k].mean()), "observed": r4(y[k].mean())}
            for lo, hi in zip(edges, edges[1:]) if (k := (p >= lo) & (p < hi)).any()]


def interval(values, rng):
    """Mean with a bootstrap 80% CI, plus the 10th-90th percentile range of single moves (the predictive interval)."""
    v = np.asarray(values, float)
    if len(v) == 0:
        return {"n": 0}
    boot = rng.choice(v, (N_BOOT, len(v))).mean(1)
    return {"n": len(v), "mean": r4(v.mean()), "mean_lo": r4(np.percentile(boot, 10)), "mean_hi": r4(np.percentile(boot, 90)),
            "lo": r4(np.percentile(v, 10)), "hi": r4(np.percentile(v, 90))}


def mixture(p, wb, ft, rng):
    """Resolution-day move: draw from walk-back days with prob p, else from follow-through days."""
    if not len(wb) or not len(ft):
        return None
    draws = np.where(rng.random(N_BOOT) < p, rng.choice(wb, N_BOOT), rng.choice(ft, N_BOOT))
    return {"mean": r4(p * np.mean(wb) + (1 - p) * np.mean(ft)), "lo": r4(np.percentile(draws, 10)), "hi": r4(np.percentile(draws, 90)),
            "n_wb": len(wb), "n_ft": len(ft)}


def market_odds(mk):
    """Implied p(walk-back) from a public Kalshi or Polymarket market (mid of bid/ask), or None."""
    if not mk:
        return None
    try:
        if mk["venue"] == "kalshi":
            x = requests.get(f"https://api.elections.kalshi.com/trade-api/v2/markets/{mk['id']}", timeout=30).json()["market"]
            bid, ask = float(x["yes_bid_dollars"]), float(x["yes_ask_dollars"])
            vol = float(x.get("volume_fp") or 0)
        else:  # polymarket gamma API, market slug
            x = requests.get("https://gamma-api.polymarket.com/markets", params={"slug": mk["id"]}, timeout=30).json()[0]
            bid, ask, vol = float(x["bestBid"]), float(x["bestAsk"]), float(x.get("volume") or 0)
        yes = (bid + ask) / 2
        return {**mk, "bid": bid, "ask": ask, "volume": vol, "p_walkback": r4(yes if mk["yes_means_walkback"] else 1 - yes)}
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        log(f"  market {mk['id']}: {e}")
        return None


def main():
    load = lambda p, d: json.load(open(p)) if os.path.exists(p) else d
    m, rng = Market(), np.random.default_rng(SEED)
    deadlines = load(P("data", "deadlines.json"), [])
    for d in deadlines:  # what the model can see for this deadline must already be in the price data
        assert d["deadline"] >= d["announced"], d["id"]
    ledger = [json.loads(l) for l in open(P("data", "predictions.jsonl"))] if os.path.exists(P("data", "predictions.jsonl")) else []
    session, now = m.dates[-1], dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    resolved = [d for d in deadlines if d["status"] != "pending" and d["resolved_on"] and m.idx(d["announced"]) is not None]
    pending = [d for d in deadlines if d["status"] == "pending" and m.idx(d["announced"]) is not None]

    # Expected-move tables from the event study (hand + auto events) and from deadline resolutions.
    study = load(P("public", "data", "study.json"), {"events": []})
    tags = {e["id"]: e["tag"] for e in load(P("public", "data", "events.json"), []) + load(P("public", "data", "auto_events.json"), [])}
    evs = [e for e in study["events"] if e["spx"]["ar"] is not None]
    groups = lambda key: {g: interval([e["spx"]["ar"] for e in evs if key(e) == g], rng) for g in sorted({key(e) for e in evs})}
    res_ar = lambda d: m.ar[i] if (i := m.idx(d["resolved_on"])) is not None else np.nan
    wb = [a for d in resolved if d["status"] in WALKBACK and np.isfinite(a := res_ar(d))]
    ft = [a for d in resolved if d["status"] not in WALKBACK and np.isfinite(a := res_ar(d))]
    cover = []  # walk-forward coverage of the topic interval
    for k, e in enumerate(sorted(evs, key=lambda e: e["date"])):
        prior = [x["spx"]["ar"] for x in sorted(evs, key=lambda e: e["date"])[:k] if x["topic"] == e["topic"]]
        if len(prior) >= 5:
            cover.append(np.percentile(prior, 10) <= e["spx"]["ar"] <= np.percentile(prior, 90))
    moves = {"by_topic": groups(lambda e: e["topic"]), "by_tag": groups(lambda e: tags.get(e["id"], "?")),
             "resolution_day": {"walked_back": interval(wb, rng), "followed_through": interval(ft, rng)},
             "coverage": {"n": len(cover), "hit_rate": r4(np.mean(cover)) if cover else None, "target": 0.8}}

    model = train(resolved, m, deadlines) if len(resolved) >= MIN_TRAIN else None
    new = []

    # 1. Daily forecast for every pending deadline (one row per deadline per session).
    done = {(r["id"], r["date"]) for r in ledger if r["type"] == "prediction"}
    out_pending = []
    for d in sorted(pending, key=lambda d: d["deadline"]):
        f = features(d, len(m.dates) - 1, m, deadlines)
        p = predict(model, f) if model else None
        row = {"type": "prediction", "kind": "deadline", "ts": now, "date": session, "id": d["id"], "model_version": MODEL_VERSION,
               "inputs": {k: r4(v) for k, v in f.items()}, "n_train": model and model["n"],
               "p_walkback": r4(p), "p_base": r4(model["base"]) if model else None, "market": market_odds(d.get("market")),
               "move": mixture(p, wb, ft, rng) if p is not None else None, "move_target": "S&P AR on the day it resolves (%)"}
        if (d["id"], session) not in done:
            new.append(row)
        out_pending.append({**{k: d.get(k) for k in ("id", "said", "target", "topic", "announced", "deadline", "source_url", "origin")}, **row})

    # 2. A move forecast for each new market-relevant post since the last close, for the next session.
    seen = {r["id"] for r in ledger if r.get("kind") == "statement"}
    nxt = str(np.busday_offset(np.datetime64(session), 1, roll="forward"))
    for post in load(P("data", "posts.json"), []):
        c = post.get("cls") or {}
        if c.get("market_relevant") and c.get("topic") in moves["by_topic"] and post["ts"][:10] >= session and "s" + post["id"] not in seen:
            new.append({"type": "prediction", "kind": "statement", "ts": now, "date": session, "id": "s" + post["id"], "model_version": MODEL_VERSION,
                        "inputs": {"topic": c["topic"], "target": c["target"], "threat_size": c["threat_size"], "deadline": c["deadline"],
                                   "summary": c["summary"], "url": post["url"]},
                        "target_date": nxt, "move": moves["by_topic"][c["topic"]], "move_target": "S&P AR on target_date (%)"})

    # 3. Resolutions and move results, appended once the outcome is in the data.
    first = {}
    for r in ledger + new:
        if r["type"] == "prediction":
            first.setdefault(r["id"], r)
    closed = {r["id"] for r in ledger if r["type"] in ("resolution", "move_result")}
    for d in resolved:
        if d["id"] in first and d["id"] not in closed and (i := m.idx(d["resolved_on"])) is not None:
            mv = first[d["id"]].get("move") or {}
            new.append({"type": "resolution", "ts": now, "id": d["id"], "status": d["status"], "walked_back": d["status"] in WALKBACK,
                        "resolved_on": d["resolved_on"], "actual_ar": r4(m.ar[i]),
                        "move_hit": mv.get("lo") is not None and mv["lo"] <= m.ar[i] <= mv["hi"]})
    for r in [r for r in first.values() if r["kind"] == "statement" and r["id"] not in closed]:
        if (i := m.idx(r["target_date"])) is not None:
            new.append({"type": "move_result", "ts": now, "id": r["id"], "date": m.dates[i], "actual_ar": r4(m.ar[i]),
                        "move_hit": r["move"]["lo"] <= m.ar[i] <= r["move"]["hi"]})

    # Live track record: score each deadline's FIRST logged forecast (the one made furthest from the outcome).
    rows = ledger + new
    res = {r["id"]: r for r in rows if r["type"] == "resolution"}
    track = [{"id": i, "date": first[i]["date"], "p": first[i]["p_walkback"], "base": first[i]["p_base"],
              "market": (first[i].get("market") or {}).get("p_walkback"), "y": int(res[i]["walked_back"]), "status": res[i]["status"],
              "actual_ar": res[i]["actual_ar"], "move_hit": res[i]["move_hit"]} for i in res if first.get(i, {}).get("p_walkback") is not None]
    mk = [t for t in track if t["market"] is not None]
    live = {"track": track, "n": len(track), "n_market": len(mk),
            "brier": {"model": brier([t["p"] for t in track], [t["y"] for t in track]) if track else None,
                      "base": brier([t["base"] for t in track], [t["y"] for t in track]) if track else None,
                      "market": brier([t["market"] for t in mk], [t["y"] for t in mk]) if mk else None,
                      "model_on_market_n": brier([t["p"] for t in mk], [t["y"] for t in mk]) if mk else None},
            "calibration": calibration([t["p"] for t in track], [t["y"] for t in track]),
            "statements": [r for r in rows if r["type"] == "move_result"][-20:],
            "ledger_rows": len(rows)}

    bt = backtest(resolved, m, deadlines)
    coef = dict(zip(["intercept"] + FEATURES, map(r4, model["b"]))) if model else None
    json.dump({"generated": now, "model_version": MODEL_VERSION, "last_price_date": session, "n_resolved": len(resolved),
               "base_rate": r4(model["base"]) if model else None, "coef": coef, "pending": out_pending,
               "statements": [r for r in rows if r.get("kind") == "statement"][-10:], "backtest": bt, "moves": moves, "live": live},
              open(P("public", "data", "forecast.json"), "w"), ensure_ascii=False, indent=1)
    for r in new:
        print(json.dumps(r, ensure_ascii=False))
    b = bt.get("brier", {})
    log(f"{len(pending)} pending; p(walk-back) " + ", ".join(f"{d['id']}={d['p_walkback']}" for d in out_pending)
        + f"; backtest n={bt['n']} Brier model {b.get('model')} vs base {b.get('base')}; {len(new)} new ledger rows")


if __name__ == "__main__":
    main()
