"""TypeSafe AI's Jev API — native System One endpoint.

Jev is NOT OpenAI-compatible. It exposes its own /v1/systemone endpoint
that takes a {state, questions} bundle and returns probabilities over
the supplied label set (or an expected value for score questions).

This adapter maps the JevBench task shape (instructions + labels +
criteria) into SystemOne questions, and converts SystemOne answers back
into the {label: prob} dict that JevBench's scorer expects.

Endpoint: https://api.typesafe.ai/v1
Models:   jev-latest, jev-preview   (discover via GET /v1/models)
Pricing:  $0.042 / 1M input tokens; output free
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .base import AdapterError


SYSTEMONE = "/v1/systemone"
# Default base_url is the API root (no /v1 suffix); the SYSTEMONE constant
# already includes /v1, so concatenation produces the right URL.
DEFAULT_BASE_URL = "https://api.typesafe.ai"


def _qtype_from_task(task) -> str:
    return {"noul": "noul", "choice": "choice", "score": "score"}.get(
        task.question_type, "choice"
    )


def _build_request(task, model: str) -> dict[str, Any]:
    """Wrap a JevBench task as a single-question SystemOne request."""
    q: dict[str, Any] = {
        "type": _qtype_from_task(task),
        "instructions": task.instructions,
    }
    if task.question_type == "choice":
        # ChoiceQuestion expects `criteria` = {name: description}.
        # JevBench `task.criteria` already maps label → description; if absent,
        # use the label itself as its own description.
        criteria = dict(task.criteria) if task.criteria else {}
        for lab in task.labels:
            lab = str(lab)
            criteria.setdefault(lab, lab)
        q["criteria"] = criteria
    elif task.question_type == "score":
        # ScoreQuestion expects `criteria` = ordered list of level descriptions.
        # JevBench score tasks usually have no descriptions; use labels.
        q["criteria"] = [str(x) for x in task.labels]
    # For noul: SystemOne defaults to {yes, no}; nothing extra needed.
    return {
        "model": model,
        "state": task.state,
        "questions": {"q": q},
    }


def _answer_to_probs(answer: dict, labels: list[str]) -> dict[str, float]:
    """Convert one SystemOne answer to a {label: prob} dict.

    noul  → {"yes": noul, "no": 1-noul} (label set must be ['yes','no'])
    choice→ uses answer.probabilities when available (full distribution),
            else falls back to {top: 1.0, others: 0.0}
    score → builds a triangular distribution around the expected value
            and renormalizes (SystemOne only gives the weighted mean).
    """
    qtype = answer.get("type")
    if qtype == "noul":
        p_yes = float(answer.get("noul", 0.5))
        return {"yes": p_yes, "no": 1.0 - p_yes}
    if qtype == "choice":
        # Prefer the full distribution when SystemOne returns it.
        probs = answer.get("probabilities")
        if isinstance(probs, dict) and probs:
            # Map every JevBench label into the returned probs (default 0).
            return {str(lab): float(probs.get(str(lab), 0.0)) for lab in labels}
        top = answer.get("choice")
        return {str(lab): (1.0 if lab == top else 0.0) for lab in labels}
    if qtype == "score":
        try:
            ev = float(answer.get("score", 0.0))
        except (TypeError, ValueError):
            ev = 0.0
        try:
            levels = [int(x) for x in labels]
        except (TypeError, ValueError):
            levels = []
        if not levels:
            return {}
        lo, hi = min(levels), max(levels)
        # Triangular kernel centered on round(ev); span = (hi-lo)/2, min 1.0.
        span = max(1.0, (hi - lo) / 2.0)
        out = {}
        for lvl in levels:
            d = abs(lvl - ev) / span
            out[str(lvl)] = max(0.0, 1.0 - d)
        s = sum(out.values()) or 1.0
        return {k: v / s for k, v in out.items()}
    return {str(lab): 1.0 / len(labels) for lab in labels} if labels else {}


class TypesafeAdapter:
    """Native Jev /v1/systemone adapter.

    Returns a dict shaped like DecisionResult.to_public(), so the rest of
    the pipeline (runner / scorer) treats it the same as verbalized
    adapters — only `source` is 'native' instead of 'verbalized'.
    """
    adapter_name = "typesafe"

    def __init__(
        self,
        *,
        base_url: str = "https://api.typesafe.ai",
        model: str = "jev-latest",
        key: str = "",
        request_options: dict | None = None,
        timeout_s: float = 120.0,
        system_prompt: str | None = None,  # ignored — native endpoint
    ):
        if not key:
            raise ValueError("Jev adapter requires an API key")
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key = key
        self.request_options = dict(request_options or {})
        self.timeout_s = timeout_s

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}",
        }

    def _post(self, url: str, body: dict) -> tuple[int, Any, float]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
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
            if status in (401, 403, 429):
                raise AdapterError(
                    f"http {status}: auth/rate-limited", fatal=True, code=status
                )
            raise AdapterError(f"http {status}: {payload[:200]}", code=status) from None
        except Exception as e:
            raise AdapterError(f"network: {type(e).__name__}: {e}") from e
        try:
            return status, json.loads(payload), latency
        except json.JSONDecodeError:
            raise AdapterError(f"non-JSON response: {payload[:200]}") from None

    def call(self, task) -> dict:
        body = _build_request(task, self.model)
        status, parsed, latency = self._post(self.base_url + SYSTEMONE, body)
        answers = parsed.get("answers", {})
        if "q" not in answers:
            raise AdapterError(f"no 'q' answer in response: {parsed!r:.300}")
        answer = answers["q"]
        probs = _answer_to_probs(answer, [str(x) for x in task.labels])
        usage = parsed.get("usage", {}) or {}
        norm_usage = {
            "prompt_tokens": int(usage.get("input_tokens", 0) or 0),
            "completion_tokens": int(usage.get("output_tokens", 0) or 0),
            "total_tokens": (
                int(usage.get("input_tokens", 0) or 0)
                + int(usage.get("output_tokens", 0) or 0)
            ),
        }
        return {
            "probs": probs,
            "source": "native",
            "model": parsed.get("model", self.model),
            "usage": norm_usage,
            "request_body": body,
            "raw": parsed,
            "latency_s": latency,
            "status": status,
        }


# Defaults — used by the runner when no explicit value is given.
DEFAULT_PRICE_IN = 0.042
DEFAULT_PRICE_OUT = 0.0
DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
