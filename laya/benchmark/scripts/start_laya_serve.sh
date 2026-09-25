#!/usr/bin/env bash
# start_laya_serve.sh — launch `python -m laya.serve` in the background.
#
# Writes PID to runs/laya_serve.pid and logs to runs/laya_serve.log.
# Waits up to 60 s for /healthz to respond before exiting.
#
# Env knobs (also read from .env if present):
#   LAYA_MODEL_DIR  default: ../models/multilingual
#   LAYA_DEVICE     default: mps (cuda | mps | cpu)
#   LAYA_HOST       default: 127.0.0.1
#   LAYA_PORT       default: 8811

set -euo pipefail

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
# ROOT = parent of PROJ = laya/, where the laya/ package lives
# UP   = parent of ROOT = jev-docs-zh-upstream/, where `python -m laya.serve` finds the package
ROOT="$(cd "$PROJ/.." && pwd)"
UP="$(cd "$ROOT/.." && pwd)"
mkdir -p "$PROJ/runs"

PID="$PROJ/runs/laya_serve.pid"
LOG="$PROJ/runs/laya_serve.log"

# Load .env if present (without echoing secrets)
if [ -f "$PROJ/.env" ]; then
    set -a
    while IFS='=' read -r key val; do
        case "$key" in ''|\#*) continue ;; esac
        val="${val#"${val%%[![:space:]]*}"}"
        val="${val%"${val##*[![:space:]]}"}"
        case "$key" in
            LAYA_MODEL_DIR|LAYA_DEVICE|LAYA_HOST|LAYA_PORT) export "$key=$val" ;;
        esac
    done < "$PROJ/.env"
    set +a
fi

export LAYA_MODEL_DIR="${LAYA_MODEL_DIR:-$ROOT/models/multilingual}"
export LAYA_DEVICE="${LAYA_DEVICE:-mps}"
export LAYA_HOST="${LAYA_HOST:-127.0.0.1}"
export LAYA_PORT="${LAYA_PORT:-8811}"
export USE_TF=0

PY="$PROJ/venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "[laya_serve] venv not found at $PY — falling back to system python3" >&2
    PY="$(command -v python3)"
fi

echo "[laya_serve] launching:"
echo "    LAYA_MODEL_DIR=$LAYA_MODEL_DIR"
echo "    LAYA_DEVICE=$LAYA_DEVICE"
echo "    LAYA_HOST=$LAYA_HOST  LAYA_PORT=$LAYA_PORT"
echo "    python=$PY"

# Kill any previous instance bound to this PID file
if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "[laya_serve] killing stale pid=$(cat "$PID")"
    kill "$(cat "$PID")" 2>/dev/null || true
    sleep 1
fi

# The serve.py adds `../models` to sys.path so that `from rl_agent_api import RLAgent`
# works at startup. We emulate that by exporting PYTHONPATH too. We also need
# the parent directory of the laya/ package on PYTHONPATH so that
# `python -m laya.serve` resolves.
export PYTHONPATH="$UP:$ROOT/models:${PYTHONPATH:-}"

nohup "$PY" -m laya.serve \
    --host "$LAYA_HOST" --port "$LAYA_PORT" \
    > "$LOG" 2>&1 &
echo $! > "$PID"

echo "[laya_serve] started pid=$(cat "$PID") log=$LOG"

# Wait up to 90 s for /healthz
READY_URL="http://$LAYA_HOST:$LAYA_PORT/healthz"
for i in $(seq 1 90); do
    if curl -sf "$READY_URL" > /dev/null 2>&1; then
        echo "[laya_serve] ready in ${i}s"
        curl -s "$READY_URL"; echo
        exit 0
    fi
    # Detect early crash
    if ! kill -0 "$(cat "$PID")" 2>/dev/null; then
        echo "[laya_serve] crashed during startup. last log lines:" >&2
        tail -n 30 "$LOG" >&2 || true
        exit 1
    fi
    sleep 1
done

echo "[laya_serve] timeout waiting for $READY_URL" >&2
tail -n 30 "$LOG" >&2 || true
exit 1