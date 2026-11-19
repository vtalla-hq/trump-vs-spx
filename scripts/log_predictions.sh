#!/usr/bin/env bash
# Runs forecast.py and appends each new ledger row to data/predictions.jsonl in its own commit,
# so every forecast's timestamp is pinned by git history. Past rows are never edited.
set -euo pipefail
cd "$(dirname "$0")/.."
touch data/predictions.jsonl
git diff --quiet HEAD -- data/predictions.jsonl 2>/dev/null || { echo "predictions.jsonl has uncommitted edits" >&2; exit 1; }
new=$(mktemp)
python3 scripts/forecast.py > "$new"
while IFS= read -r row; do
  printf '%s\n' "$row" >> data/predictions.jsonl
  git add data/predictions.jsonl
  git commit -q -m "Ledger: $(python3 -c 'import json,sys; r=json.loads(sys.argv[1]); print(r["type"], r["id"], r.get("date") or r.get("resolved_on") or "", ("p_walkback=%s" % r["p_walkback"]) if r.get("p_walkback") is not None else "")' "$row")"
done < "$new"
echo "$(wc -l < "$new") ledger rows committed" >&2
