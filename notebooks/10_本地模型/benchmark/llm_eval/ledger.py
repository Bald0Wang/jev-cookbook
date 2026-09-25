"""File-locked append-only budget ledger.

reserve() writes worst-case cost before the request leaves;
settle() writes the real cost after. The cap is read from the
ledger's first 'cap' row, so a later run cannot raise it by passing
a bigger --cap-usd. An unsettled reservation stays charged —
crash mid-request is recorded as 'spent', not 'never happened'.

A settlement larger than its reservation raises (an assumption is
wrong, stop). Non-finite or negative amounts are rejected, not coerced.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import time
import uuid


class BudgetExceeded(RuntimeError):
    pass


def _finite(x) -> float:
    try:
        f = float(x)
    except (TypeError, ValueError):
        raise BudgetExceeded(f"cost/cap must be a real number, got {x!r}")
    if not math.isfinite(f) or f < 0:
        raise BudgetExceeded(f"cost/cap must be finite and non-negative, got {x!r}")
    return f


class Ledger:
    def __init__(self, path: str, cap_usd: float = 15.0):
        self.path = str(path)
        self.cap_usd = _finite(cap_usd)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        # Make sure the file exists so flock can take a shared lock on it.
        open(self.path, "a").close()

    def _read(self, f):
        f.seek(0)
        rows = [json.loads(ln) for ln in f if ln.strip()]
        reserved, settled = {}, {}
        for r in rows:
            if r["event"] == "reserve":
                reserved[r["reservation_id"]] = _finite(r["reserved_usd"])
            elif r["event"] == "settle":
                rid = r["reservation_id"]
                if rid in settled or rid not in reserved:
                    raise BudgetExceeded("invalid settlement history")
                settled[rid] = _finite(r["charged_usd"])
        return rows, reserved, settled

    @staticmethod
    def _charge(reserved: dict, settled: dict) -> float:
        total = 0.0
        for k, v in reserved.items():
            amount = settled.get(k, v)
            # Defensive: a stray string from an older run would break float math.
            try:
                total += float(amount)
            except (TypeError, ValueError):
                total += float(v)
        return total

    @staticmethod
    def _append(f, row: dict) -> None:
        f.seek(0, 2)
        f.write(json.dumps(row, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

    @property
    def charged(self) -> float:
        with open(self.path, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            _, r, s = self._read(f)
            return self._charge(r, s)

    def reserve(self, amount_usd: float, meta: dict | None = None) -> str:
        amount = _finite(amount_usd)
        with open(self.path, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            rows, r, s = self._read(f)
            caps = [x["cap_usd"] for x in rows if x["event"] == "cap"]
            cap = min(caps) if caps else self.cap_usd
            if not caps:
                self._append(f, {"event": "cap", "cap_usd": cap, "ts": time.time()})
            if self._charge(r, s) + amount > cap + 1e-12:
                raise BudgetExceeded("shared budget exhausted; request not sent")
            rid = uuid.uuid4().hex
            self._append(
                f,
                {
                    "event": "reserve",
                    "reservation_id": rid,
                    "reserved_usd": amount,
                    "ts": time.time(),
                    "meta": meta or {},
                },
            )
            return rid

    def settle(self, reservation_id: str, actual_usd: float, meta: dict | None = None) -> None:
        actual = _finite(actual_usd)
        with open(self.path, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            _, r, s = self._read(f)
            if reservation_id not in r or reservation_id in s:
                raise BudgetExceeded("missing or duplicate reservation")
            self._append(
                f,
                {
                    "event": "settle",
                    "reservation_id": reservation_id,
                    "charged_usd": actual,
                    "ts": time.time(),
                    "meta": meta or {},
                },
            )
            if actual > float(r[reservation_id]) + 1e-12:
                raise BudgetExceeded(
                    "actual charge exceeded reserved maximum; halt and audit"
                )