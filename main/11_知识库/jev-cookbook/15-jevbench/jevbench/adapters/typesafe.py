"""Native TypeSafe-compatible /v1/systemone adapter.

Request: POST {endpoint}/v1/systemone
  {"state": ..., "model": ..., "questions": {"decision": {...}}}
Auth: Bearer token from the environment variable named by `key_env`
(default TYPESAFE_API_KEY). The key is never logged or stored.

Answer mapping to exact-label probabilities:
  noul   p_yes = answer["noul"]          -> {"yes": p, "no": 1-p}
  choice answer["probabilities"]         -> used as-is (keys = options)
  score  answer["probabilities"]         -> used as-is (keys = level indices)

Optional pricing via env TYPESAFE_PRICE_INPUT_PER_M / TYPESAFE_PRICE_OUTPUT_PER_M.
"""

from __future__ import annotations

import os

from .base import NOUL_LABELS, DecisionResult, build_question, http_post_json


class TypeSafeAdapter:
    name = "typesafe"

    def __init__(self, endpoint=None, model=None, key_env="TYPESAFE_API_KEY",
                 timeout_s=120.0, price_input_per_m=None, price_output_per_m=None):
        self.endpoint = (endpoint or os.environ.get("TYPESAFE_ENDPOINT")
                         or "https://api.typesafe.ai").rstrip("/")
        self.model = model or os.environ.get("TYPESAFE_MODEL") or "jev-latest"
        self.key_env = key_env
        self.timeout_s = timeout_s
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m

    def build_request(self, task) -> dict:
        q = build_question(task)
        # For score questions the criteria must be a list of levels; the
        # canonical record stores levels in `labels` order.
        return {"state": task.state, "model": self.model, "questions": {"decision": q}}

    def run(self, task) -> DecisionResult:
        key = os.environ.get(self.key_env, "") if self.key_env else ""
        if self.key_env and not key:
            return DecisionResult(
                adapter=self.name, ok=False, error=f"missing env key {self.key_env}",
                probs_source="native", model=self.model,
            )
        body = self.build_request(task)
        headers = {
            **({"Authorization": f"Bearer {key}"} if key else {}),
            "Content-Type": "application/json",
            # Some public demo CDNs reject urllib's default Python user agent
            # while accepting ordinary API clients. This identifies the
            # benchmark harness without altering browser or network identity.
            "User-Agent": "JevBench/1.2 (+https://github.com/fstandhartinger/jevbench)",
        }
        try:
            status, parsed, latency = http_post_json(
                f"{self.endpoint}/v1/systemone", body, headers, self.timeout_s
            )
        except ConnectionError as e:
            return DecisionResult(
                adapter=self.name, ok=False, error=str(e), probs_source="native",
                model=self.model, request_body=body,
            )
        res = DecisionResult(
            adapter=self.name, ok=False, status=status, latency_s=latency,
            probs_source="native", model=self.model, raw=parsed, request_body=body,
        )
        if status != 200 or not isinstance(parsed, dict):
            res.error = f"HTTP {status}: {str(parsed)[:300]}"
            return res
        answers = parsed.get("answers") or {}
        ans = answers.get("decision")
        if not isinstance(ans, dict):
            res.error = "missing 'answers.decision'"
            return res
        res.usage = parsed.get("usage") or {}
        res.model = parsed.get("model") or self.model
        qtype = task.question["type"]
        if ans.get("type") != qtype:
            res.error = "native answer type mismatch"
            return res
        try:
            if qtype == "noul":
                if isinstance(ans["noul"],bool) or not isinstance(ans["noul"],(int,float)): raise ValueError("noul must be numeric")
                p = float(ans["noul"])
                if not (0.0 <= p <= 1.0):
                    raise ValueError(f"noul out of range: {p}")
                res.probs = {"yes": p, "no": 1.0 - p}
            elif qtype == "choice":
                if ans.get("choice") not in task.labels: raise ValueError("Invalid native choice")
                probs = ans.get("probabilities")
                if not isinstance(probs, dict):
                    raise ValueError("choice answer missing probabilities")
                res.probs = probs
            elif qtype == "score":
                probs = ans.get("probabilities")
                if not isinstance(probs, dict):
                    raise ValueError("score answer missing probabilities")
                res.probs = probs
        except (KeyError, TypeError, ValueError) as e:
            res.error = f"answer parse failed: {e}"
            return res
        res.ok = True
        return res

    def reserve_estimate(self, task) -> float:
        """Conservative max reservation. Uses env prices when present;
        otherwise the runner requires an explicit reserve for this endpoint."""
        pin = self.price_input_per_m
        pout = self.price_output_per_m
        if pin is None:
            pin = float(os.environ.get("TYPESAFE_PRICE_INPUT_PER_M", "nan") or "nan")
        if pout is None:
            pout = float(os.environ.get("TYPESAFE_PRICE_OUTPUT_PER_M", "nan") or "nan")
        import math
        if math.isnan(pin) or math.isnan(pout):
            return None  # caller must supply explicit reserve
        # conservative caps: 100k input tokens, 4k output tokens per request
        return 100_000 * pin / 1e6 + 4_000 * pout / 1e6
