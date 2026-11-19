"""Tags scraped market-day stories with Groq (JSON mode, temperature 0), then:
  - calibration: blind run on the hand-labeled event days → public/data/calibration.json
  - routing: valid, trump_related, high-confidence rows → public/data/auto_events.json;
    everything else → data/review_queue.json. Hand-labeled dates always win.
Skips gracefully when GROQ_API_KEY is unset. LLM answers are cached per model+date in data/extracted.json.
Run: python3 scripts/extract.py
"""
import json, os, time, datetime as dt
import requests
from jsonschema import Draft202012Validator

MODEL = "openai/gpt-oss-120b"  # change here; must support response_format json_object on Groq
URL = "https://api.groq.com/openai/v1/chat/completions"
MIN_CONF = 0.8
ROOT = os.path.join(os.path.dirname(__file__), "..")
P = lambda *a: os.path.join(ROOT, *a)

TAGS = ["Followed through", "Walked back", "Didn't check out", "Rhetoric", "False report", "Overruled"]
TOPICS = ["Tariffs", "Iran war", "Fed", "Recession talk", "Other"]
NORM_TAG = {"Report / rumor": "False report"}  # same bucket on the site (format.js normTag)

SCHEMA = {
    "type": "object",
    "required": ["trump_related", "confidence", "said", "did", "tag", "topic", "context", "headline"],
    "properties": {
        "trump_related": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "said": {"type": "string"}, "did": {"type": "string"},
        "tag": {"enum": TAGS}, "topic": {"enum": TOPICS},
        "context": {"type": "string"}, "headline": {"type": "string", "minLength": 1, "maxLength": 80},
    },
    # A Trump-driven day must say what he said and what happened; other days may leave them empty.
    "if": {"properties": {"trump_related": {"const": True}}},
    "then": {"properties": {"said": {"minLength": 1}, "did": {"minLength": 1}}},
}
VALID = Draft202012Validator(SCHEMA)

SYSTEM = f"""You label US stock-market news days for a dataset on how Donald Trump's statements and actions moved the S&P 500.
Read the story and return ONE JSON object with exactly these keys:
- trump_related (bool): was a Trump statement, policy, or a report about him the main driver of the day's move?
- confidence (0-1): how sure you are of the tag and topic.
- said: what Trump said or announced (one sentence; quote him if the story does).
- did: what actually happened with it (one sentence).
- tag: one of {TAGS}.
    Followed through = he did what he said. Walked back = he reversed, paused or softened his own earlier threat.
    Didn't check out = his claim proved false. Rhetoric = talk, a hedge or an attack, not a policy action.
    False report = a false or unconfirmed headline/rumor moved markets. Overruled = a court or other body overrode him.
- topic: one of {TOPICS}.
- context: other things that moved markets that day (jobs data, earnings, oil...), one sentence.
- headline: a short label, at most 8 words.
If the day was not driven by Trump, set trump_related false and still fill every field with your best guess."""


def ask(story, key, tries=6):
    body = {"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": f"Date: {story['date']}\nTitle: {story['title']}\n\n{story['text']}"}]}
    for k in range(tries):
        r = requests.post(URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("retry-after") or 2 ** k)
            print(f"  {story['date']}: HTTP {r.status_code}, retrying in {wait:.0f}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])
    raise RuntimeError(f"{story['date']}: gave up after {tries} tries")


def kappa(a, b):
    """Cohen's kappa for two equal-length label lists."""
    n, labels = len(a), sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


assert kappa(list("aabb"), list("aabb")) == 1.0 and abs(kappa(list("aabb"), list("abab"))) < 1e-12


def agreement(gold, pred, labels):
    labels = [l for l in labels if l in gold or l in pred]
    return {"n": len(gold), "accuracy": round(sum(g == p for g, p in zip(gold, pred)) / len(gold), 3),
            "kappa": round(kappa(gold, pred), 3), "labels": labels,
            "confusion": [[sum(g == lg and p == lp for g, p in zip(gold, pred)) for lp in labels] for lg in labels]}


def main():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        print("GROQ_API_KEY not set: skipping LLM extraction")
        return
    load = lambda p, d: json.load(open(p)) if os.path.exists(p) else d
    stories = [s for s in load(P("data", "headlines.json"), []) if not s.get("missing")]
    gold = {e["date"]: e for e in load(P("public", "data", "events.json"), [])}
    cache = load(P("data", "extracted.json"), {})
    daily = {r["date"]: r["^GSPC"] for r in load(P("public", "data", "daily.json"), [])}
    days = sorted(daily)

    out = {}
    for s in stories:
        ck = f"{MODEL}|{s['date']}"
        if ck not in cache:
            try:
                cache[ck] = ask(s, key)
            except (requests.RequestException, ValueError, RuntimeError) as e:
                print(f"  {s['date']}: {e}")
                continue
            json.dump(cache, open(P("data", "extracted.json"), "w"), ensure_ascii=False, indent=1)
        row = cache[ck]
        errors = [e.message for e in VALID.iter_errors(row)] if isinstance(row, dict) else ["not an object"]
        out[s["date"]] = (s, row, errors)

    # Calibration: blind labels on the hand-labeled days vs the gold labels.
    cal = [(gold[d], row) for d, (s, row, err) in out.items() if d in gold and not err]
    n_gold_scraped = sum(d in gold for d in out)
    calibration = {"model": MODEL, "generated": str(dt.date.today()), "n_gold": len(gold), "n_scraped": n_gold_scraped,
                   "n_valid": len(cal), "n_rejected": n_gold_scraped - len(cal),
                   "text_sources": {src: sum(out[d][0]["source"] == src for d in out if d in gold) for src in {out[d][0]["source"] for d in out if d in gold}},
                   "trump_related_recall": round(sum(r["trump_related"] for _, r in cal) / len(cal), 3) if cal else None,
                   "tag": agreement([NORM_TAG.get(g["tag"], g["tag"]) for g, _ in cal], [r["tag"] for _, r in cal], TAGS) if cal else None,
                   "topic": agreement([g["topic"] if g["topic"] in TOPICS else "Other" for g, _ in cal], [r["topic"] for _, r in cal], TOPICS) if cal else None}
    json.dump(calibration, open(P("public", "data", "calibration.json"), "w"), ensure_ascii=False, indent=1)

    auto, queue = [], []
    for d, (s, row, errors) in out.items():
        if d in gold:
            continue
        i = days.index(d) if d in daily else None
        rec = {**(row if isinstance(row, dict) else {}), "id": "a" + d.replace("-", ""), "date": d,
               "pct": round((daily[d] / daily[days[i - 1]] - 1) * 100, 2) if i else None,
               "close": daily.get(d), "source": s["source"], "url": s["url"], "threat_day": False, "auto": True}
        reason = "; ".join(errors) or (not row["trump_related"] and "not trump_related") \
            or (row["confidence"] < MIN_CONF and f"confidence {row['confidence']} < {MIN_CONF}") or (i is None and "no price")
        (queue if reason else auto).append({**rec, "reason": reason} if reason else rec)
    json.dump(auto, open(P("public", "data", "auto_events.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(queue, open(P("data", "review_queue.json"), "w"), ensure_ascii=False, indent=1)
    t = calibration["tag"] or {}
    print(f"{MODEL}: {len(out)} days tagged, {len(auto)} auto events, {len(queue)} to review; "
          f"calibration n={calibration['n_valid']} tag acc={t.get('accuracy')} kappa={t.get('kappa')}")


if __name__ == "__main__":
    main()
