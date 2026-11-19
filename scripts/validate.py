"""CI check: validates every data file (JSON and the JSONL ledger) against its schema (fails the build), then checks every
source URL (warns on dead links, never fails). Run: python3 scripts/validate.py [--no-links]
"""
import json, os, sys
import requests
from jsonschema import Draft202012Validator
from extract import SCHEMA as LLM_ROW, TAGS, NORM_TAG

D = os.path.join(os.path.dirname(__file__), "..") + "/"
S, N, B = {"type": "string", "minLength": 1}, {"type": "number"}, {"type": "boolean"}
DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
URL = {"type": "string", "pattern": "^https://"}
NUM_OR_NULL = {"type": ["number", "null"]}

EVENT = {"type": "object", "required": ["id", "date", "pct", "topic", "said", "did", "tag", "context", "source", "url", "headline", "threat_day"],
         "properties": {"id": S, "date": DATE, "pct": N, "close": NUM_OR_NULL, "topic": S, "said": S, "did": S,
                        "tag": {"enum": TAGS + list(NORM_TAG)}, "context": {"type": "string"}, "source": S, "url": URL, "headline": S, "threat_day": B}}
AUTO = {"allOf": [LLM_ROW, EVENT, {"required": ["auto"], "properties": {"auto": {"const": True}}}]}
CAR = {"type": "object", "required": ["0,0", "0,1", "0,5"], "additionalProperties": NUM_OR_NULL}
PERM = {"type": "object", "required": ["n", "event_mean_abs_ar", "null_mean_abs_ar", "p_value", "hist"],
        "properties": {"n": {"type": "integer", "minimum": 1}, "p_value": {"type": "number", "minimum": 0, "maximum": 1}}}
AGREE = {"type": "object", "required": ["n", "accuracy", "kappa", "labels", "confusion"]}

SCHEMAS = {
    "public/data/events.json": {"type": "array", "minItems": 1, "items": EVENT},
    "public/data/auto_events.json": {"type": "array", "items": AUTO},
    "public/data/kobeissi.json": {"type": "array", "items": {"type": "object", "required": ["id", "date", "event_id", "post", "url"],
                                                 "properties": {"date": DATE, "url": URL, "post": S}}},
    "public/data/daily.json": {"type": "array", "minItems": 200, "items": {"type": "object", "required": ["date", "^GSPC", "^VIX", "^TNX"],
                                                                "properties": {"date": DATE, "^GSPC": N},
                                                                "additionalProperties": NUM_OR_NULL}},
    "public/data/study.json": {"type": "object", "required": ["method", "events", "permutation", "backtest"], "properties": {
        "events": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "date", "spx", "vix_chg", "tnx_bps", "sectors"],
                   "properties": {"spx": {"type": "object", "required": ["ret", "ar", "sar", "car"], "properties": {"ar": N, "sar": N, "car": CAR}}}}},
        "permutation": {"type": "object", "required": ["overall", "by_topic", "draws"],
                        "properties": {"overall": PERM, "by_topic": {"additionalProperties": PERM}}},
        "backtest": {"type": "object", "required": ["n", "trades", "hit_rate", "avg_ret", "avg_baseline", "caveat"]}}},
    "public/data/calibration.json": {"type": "object", "required": ["model", "n_gold", "n_valid", "tag", "topic"],
                         "properties": {"model": S, "tag": {"anyOf": [AGREE, {"type": "null"}]}, "topic": {"anyOf": [AGREE, {"type": "null"}]}}},
    "data/deadlines.json": {"type": "array", "items": {"type": "object",
        "required": ["id", "announced", "deadline", "said", "target", "topic", "source_url", "status", "resolved_on", "threat_size"],
        "properties": {"announced": DATE, "deadline": DATE, "said": S, "source_url": URL, "threat_size": {"type": "number", "minimum": 0},
                       "status": {"enum": ["pending", "followed_through", "walked_back", "extended"]},
                       "resolved_on": {"anyOf": [DATE, {"type": "null"}]}},
        "if": {"properties": {"status": {"const": "pending"}}}, "then": {"properties": {"resolved_on": {"type": "null"}}},
        "else": {"properties": {"resolved_on": DATE}}}},
    "data/predictions.jsonl": {"type": "array", "items": {"type": "object", "required": ["type", "ts", "id"],
        "properties": {"type": {"enum": ["prediction", "resolution", "move_result"]},
                       "p_walkback": {"type": ["number", "null"], "minimum": 0, "maximum": 1}}}},
    "public/data/forecast.json": {"type": "object", "required": ["model_version", "pending", "backtest", "moves", "live"]},
}


def main():
    bad, urls = 0, set()
    for name, schema in SCHEMAS.items():
        if not os.path.exists(D + name):
            if name.endswith(("auto_events.json", "calibration.json", "predictions.jsonl")):  # written by the LLM step, which may be skipped
                print(f"skip {name}: not generated yet")
                continue
            print(f"::error::{name} is missing"); bad += 1; continue
        data = [json.loads(l) for l in open(D + name)] if name.endswith(".jsonl") else json.load(open(D + name))
        errs = list(Draft202012Validator(schema).iter_errors(data))
        for e in errs[:10]:
            print(f"::error file={name}::{'/'.join(map(str, e.absolute_path))}: {e.message[:200]}")
        bad += len(errs)
        print(f"{name}: {'OK' if not errs else f'{len(errs)} errors'}")
        if isinstance(data, list):
            urls |= {r.get("url") or r.get("source_url") for r in data if isinstance(r, dict) and (r.get("url") or r.get("source_url"))}
    if "--no-links" not in sys.argv:
        dead = 0
        for u in sorted(urls):
            try:
                code = requests.get(u, headers={"User-Agent": "Mozilla/5.0 (link check)"}, timeout=20, stream=True).status_code
            except requests.RequestException as e:
                code = type(e).__name__
            if not (isinstance(code, int) and code < 400):
                dead += 1
                print(f"::warning::source link {code}{' (maybe bot protection)' if code == 403 else ''}: {u}")
        print(f"links: {len(urls) - dead}/{len(urls)} OK (dead links are warnings, not failures)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
