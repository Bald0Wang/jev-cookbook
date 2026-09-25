"""Adapter base: DecisionResult + shared HTTP helper."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional


class AdapterError(Exception):
    """Raised by adapter.call() on non-success.

    fatal=True means stop the run (401/403/429/permission/billing).
    fatal=False is an infrastructure error; the runner tolerates up to 3
    in a row before stopping.
    """

    def __init__(self, message: str, *, fatal: bool = False, code: int | None = None):
        super().__init__(message)
        self.fatal = fatal
        self.code = code


@dataclass
class DecisionResult:
    adapter: str
    ok: bool
    probs: Optional[dict] = None
    source: str = "unknown"  # "native" | "verbalized"
    model: str = ""
    status: Optional[int] = None
    error: Optional[str] = None
    latency_s: float = 0.0
    usage: dict = field(default_factory=dict)
    raw: Optional[Any] = None
    request_body: Optional[Any] = None

    def to_public(self) -> dict:
        return {
            "adapter": self.adapter,
            "ok": self.ok,
            "probs": self.probs,
            "source": self.source,
            "model": self.model,
            "status": self.status,
            "error": self.error,
            "latency_s": self.latency_s,
            "usage": self.usage,
        }


def http_post_json(
    url: str, body: dict, headers: dict, timeout_s: float = 120.0
) -> tuple[int, Any, float]:
    """POST JSON. Returns (status, parsed_body_or_text, latency_s)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = resp.status
            payload = resp.read().decode("utf-8", errors="replace")
            latency = time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            payload = e.read().decode("utf-8", errors="replace")
        except Exception:
            payload = ""
        latency = time.perf_counter() - t0
    except Exception as e:
        raise AdapterError(f"network: {type(e).__name__}: {e}") from e
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        parsed = payload
    return status, parsed, latency


def build_decision_prompt(task) -> dict:
    """Build the decision payload sent to the model. The `expected` field is NEVER included."""
    return {
        "instructions": task.instructions,
        "criteria": task.criteria,
        "labels": list(task.labels),
        "state": dict(task.state),
    }