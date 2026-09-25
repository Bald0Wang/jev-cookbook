"""OpenAI-compatible adapter.

Works against any provider that speaks the /v1/chat/completions schema
and supports JSON-schema-constrained decoding (or at least
returns parseable JSON). Use it directly or via one of the per-provider
thin shims in this package.

Returned probabilities are tagged source='verbalized' because the model
WROTE them out — they are not token-level logprobs. That distinction is
preserved through scoring.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .base import AdapterError, DecisionResult, build_decision_prompt, http_post_json


CHAT_COMPLETIONS = "/chat/completions"

# JSON-schema fragment forcing a probability map over the exact label set.
def _probs_schema(labels: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "probs": {
                "type": "object",
                "properties": {lab: {"type": "number"} for lab in labels},
                "required": list(labels),
                "additionalProperties": False,
            },
            "reasoning": {"type": "string"},
        },
        "required": ["probs"],
        "additionalProperties": False,
    }


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model response. Robust to leading prose."""
    if not text:
        return None
    # fast path
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fall back: find first { and last }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


class OpenAICompatAdapter:
    adapter_name = "openai_compat"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        key: str = "",
        request_options: dict | None = None,
        timeout_s: float = 120.0,
        system_prompt: str | None = None,
    ):
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key = key
        self.request_options = dict(request_options or {})
        self.timeout_s = timeout_s
        self.system_prompt = system_prompt or (
            "You are a typed decision engine. Read the state and instructions, "
            "then return JSON with a single key 'probs' that maps each label "
            "to a probability in [0,1]. Probabilities must sum to 1 (rounding "
            "within 0.02 is fine). Do not include any other text."
        )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def call(self, task) -> dict:
        """Returns a dict shaped like DecisionResult.to_public(), without raw body."""
        prompt = build_decision_prompt(task)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Decision request:\n"
                        + json.dumps(prompt, ensure_ascii=False)
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 256,
            "response_format": {"type": "json_object"},
        }
        # Provider-specific overrides (DashScope 'qwen3-max' style aliases, etc.)
        for k, v in self.request_options.items():
            if v is None:
                body.pop(k, None)
            else:
                body[k] = v

        url = self.base_url + CHAT_COMPLETIONS
        try:
            status, parsed, latency = http_post_json(
                url, body, self._headers(), timeout_s=self.timeout_s
            )
        except AdapterError:
            raise
        if status == 401 or status == 403 or status == 429:
            raise AdapterError(
                f"http {status}: auth/rate-limited", fatal=True, code=status
            )
        if status >= 400:
            raise AdapterError(f"http {status}: {str(parsed)[:200]}", code=status)

        # Extract content
        try:
            content = parsed["choices"][0]["message"]["content"]
        except (KeyError, TypeError, IndexError):
            raise AdapterError(f"unexpected response: {parsed}")
        probs_obj = _extract_json(content) if isinstance(content, str) else content
        if not isinstance(probs_obj, dict):
            raise AdapterError(f"could not parse probs from: {content!r:.200}")
        # Some models occasionally misspell "probs" as "progs" / "probabilities"
        # / "weights". Accept any of these so a single typo doesn't tank the run.
        for key in ("probs", "progs", "probabilities", "weights", "distribution"):
            if key in probs_obj and isinstance(probs_obj[key], dict):
                probs = probs_obj[key]
                break
        else:
            raise AdapterError(f"could not find probs in: {content!r:.200}")
        # Coerce string-typed probabilities to float (some providers
        # serialize numbers as JSON strings).
        for k, v in list(probs.items()):
            if isinstance(v, str):
                try:
                    probs[k] = float(v)
                except ValueError:
                    raise AdapterError(f"non-numeric prob[{k!r}]={v!r}")
        if not isinstance(probs, dict):
            raise AdapterError("'probs' is not a dict")

        usage = parsed.get("usage", {}) or {}
        return {
            "probs": probs,
            "source": "verbalized",
            "model": parsed.get("model", self.model),
            "usage": usage,
            "request_body": body,
            "raw": parsed,
            "latency_s": latency,
            "status": status,
        }