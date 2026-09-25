#!/usr/bin/env bash
# fetch_public_tasks.sh — pull JevBench public task JSONLs from upstream.
#
# Source: https://github.com/fstandhartinger/jevbench (MIT)
# Output: benchmark/tasks/{easy,original,hard}.jsonl (raw JevBench format)
#
# After this script runs, run scripts/convert_jevbench.py on each file to
# convert to llm_eval format, then `cat` them into tasks/public_all.jsonl.

set -euo pipefail

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
DST="$PROJ/tasks"
mkdir -p "$DST"

BASE="https://raw.githubusercontent.com/fstandhartinger/jevbench/main/datasets/public"

for tier in easy original hard; do
    out="$DST/${tier}.jsonl"
    echo "[fetch] $tier -> $out"
    curl -fSL --retry 3 -o "$out" "$BASE/${tier}.jsonl"
    n=$(wc -l < "$out" | tr -d ' ')
    echo "[fetch]   $n records"
done

echo
echo "[fetch] done. next steps:"
cat <<'EOF'
    python3 scripts/convert_jevbench.py tasks/easy.jsonl     tasks/easy.llmeval.jsonl
    python3 scripts/convert_jevbench.py tasks/original.jsonl tasks/original.llmeval.jsonl
    python3 scripts/convert_jevbench.py tasks/hard.jsonl     tasks/hard.llmeval.jsonl
    cat tasks/{easy,original,hard}.llmeval.jsonl > tasks/public_all.jsonl
EOF