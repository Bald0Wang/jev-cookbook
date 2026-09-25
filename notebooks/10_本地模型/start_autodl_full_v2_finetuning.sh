#!/usr/bin/env bash
set -euo pipefail

AUTODL_ROOT="${AUTODL_ROOT:-/root/autodl-tmp}"
PROJECT_ROOT="${LAYA_PROJECT_ROOT:-$AUTODL_ROOT/laya-training-project}"
PYTHON="${LAYA_PYTHON:-$AUTODL_ROOT/laya-venv/bin/python}"
NOTEBOOK="${LAYA_NOTEBOOK:-$AUTODL_ROOT/full_v2_finetuning.ipynb}"
CANDIDATES="${LAYA_CANDIDATES_PATH:-$AUTODL_ROOT/datasets/laya-datasets/sharegpt_zh_38k/v2/laya_candidates.jsonl}"
MODEL_DIR="${LAYA_MODEL_DIR:-$AUTODL_ROOT/models/laya/multilingual}"
OUTPUT_DIR="${LAYA_OUTPUT_DIR:-$AUTODL_ROOT/experiments/laya}"

required_files=(
  "$PROJECT_ROOT/laya/finetune_reviewed_jsonl.py"
  "$PROJECT_ROOT/laya/finetune_variant_jsonl.py"
  "$PROJECT_ROOT/laya/finetune_rlcd_official_jsonl.py"
  "$NOTEBOOK"
  "$CANDIDATES"
  "$MODEL_DIR/model.safetensors"
  "$MODEL_DIR/rl_agent_config.json"
)
required_dirs=("$MODEL_DIR/encoder" "$MODEL_DIR/tokenizer")

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    printf 'Missing required file: %s\n' "$path" >&2
    exit 1
  fi
done

for path in "${required_dirs[@]}"; do
  if [[ ! -d "$path" ]]; then
    printf 'Missing required directory: %s\n' "$path" >&2
    exit 1
  fi
done

if [[ ! -x "$PYTHON" ]]; then
  printf 'Python environment not found: %s\n' "$PYTHON" >&2
  exit 1
fi

if ! "$PYTHON" -m jupyterlab --version >/dev/null 2>&1; then
  printf 'JupyterLab is not installed in %s\n' "$PYTHON" >&2
  exit 1
fi

export LAYA_PROJECT_ROOT="$PROJECT_ROOT"
export LAYA_CANDIDATES_PATH="$CANDIDATES"
export LAYA_MODEL_DIR="$MODEL_DIR"
export LAYA_OUTPUT_DIR="$OUTPUT_DIR"
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$OUTPUT_DIR"
cd "$AUTODL_ROOT"

exec "$PYTHON" -m jupyterlab \
  --no-browser \
  --ip=127.0.0.1 \
  --port="${JUPYTER_PORT:-8888}" \
  --ServerApp.root_dir="$AUTODL_ROOT" \
  "$NOTEBOOK"
