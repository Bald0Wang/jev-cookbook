#!/usr/bin/env bash
# run_notebook.sh — execute notebooks/laya_vs_jev.ipynb end-to-end via nbconvert.
#
# Pre-conditions:
#   - Laya serve is up (./scripts/start_laya_serve.sh)
#   - .env is in place (cp ../llm_eval/.env .env)
#   - tasks/public_all.jsonl exists (./scripts/fetch_public_tasks.sh + convert)
#
# Outputs:
#   - notebooks/laya_vs_jev_executed.ipynb  (executed cells with outputs)
#   - runs/notebook-demo/real/{laya-local,jev}/summary.json
#   - runs/notebook-demo/multi/{compare.json, compare.md, charts/*.png}

set -euo pipefail

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"

NOTEBOOK="$PROJ/notebooks/laya_vs_jev.ipynb"
OUTPUT="$PROJ/notebooks/laya_vs_jev_executed.ipynb"
TIMEOUT=1800

# Load .env so the notebook cell 12 has TYPESAFE_API_KEY
if [ -f "$PROJ/.env" ]; then
    echo "=== loading .env ==="
    set -a
    while IFS='=' read -r key val; do
        case "$key" in ''|\#*) continue ;; esac
        val="${val#"${val%%[![:space:]]*}"}"
        val="${val%"${val##*[![:space:]]}"}"
        export "$key=$val"
    done < "$PROJ/.env"
    set +a
else
    echo "=== no .env file — Jev runner will be skipped ==="
fi

if [ ! -f "$NOTEBOOK" ]; then
    echo "ERROR: $NOTEBOOK not found — generate it first." >&2
    exit 1
fi

# Quick liveness check
if ! curl -sf http://127.0.0.1:8811/healthz > /dev/null 2>&1; then
    echo "WARNING: Laya serve at 127.0.0.1:8811 not responding — Laya runner will error."
    echo "         Run ./scripts/start_laya_serve.sh first."
fi

echo "=== executing notebook ==="
echo "    notebook: $NOTEBOOK"
echo "    output:   $OUTPUT"
echo "    timeout:  ${TIMEOUT}s"

# Find a working nbconvert: prefer the user-site install (Python 3.14 ships
# jupyter under ~/Library/Python/3.14/bin/jupyter-nbconvert).
NBCONVERT=""
for cand in \
    "$HOME/Library/Python/3.14/bin/jupyter-nbconvert" \
    "$(command -v jupyter-nbconvert 2>/dev/null)" \
    "$PROJ/venv/bin/jupyter-nbconvert"; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then
        NBCONVERT="$cand"; break
    fi
done
if [ -z "$NBCONVERT" ]; then
    echo "ERROR: jupyter-nbconvert not found." >&2
    echo "  try: python3 -m pip install --user nbconvert" >&2
    exit 1
fi
echo "    nbconvert: $NBCONVERT"

"$NBCONVERT" --to notebook --execute "$NOTEBOOK" \
    --output "$OUTPUT" \
    --ExecutePreprocessor.timeout="$TIMEOUT"

echo
echo "=== done ==="
echo "产物："
echo "  - $OUTPUT"
echo "  - runs/notebook-demo/real/{laya-local,jev}/summary.json"
echo "  - runs/notebook-demo/multi/charts/main_score.png"
echo "  - runs/notebook-demo/multi/charts/4dim_compare.png"
echo
echo "看 main-score 图："
echo "  open runs/notebook-demo/multi/charts/main_score.png"