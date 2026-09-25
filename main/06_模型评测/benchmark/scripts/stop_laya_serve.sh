#!/usr/bin/env bash
# stop_laya_serve.sh — terminate the background Laya serve started by start_laya_serve.sh.

set -euo pipefail

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
PID="$PROJ/runs/laya_serve.pid"

if [ ! -f "$PID" ]; then
    echo "[laya_serve] no pid file at $PID — nothing to stop"
    exit 0
fi

pid="$(cat "$PID")"
if kill -0 "$pid" 2>/dev/null; then
    echo "[laya_serve] stopping pid=$pid"
    kill "$pid" || true
    # wait up to 5 s for graceful exit
    for i in $(seq 1 5); do
        if ! kill -0 "$pid" 2>/dev/null; then break; fi
        sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "[laya_serve] still alive — sending SIGKILL"
        kill -9 "$pid" || true
    fi
else
    echo "[laya_serve] pid=$pid not running (stale)"
fi
rm -f "$PID"