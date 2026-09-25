"""OpenAI-compatible adapter with JSON-schema-constrained output.

The model must emit a JSON object: {"probabilities": {<label>: <number>, ...}}
with EXACTLY the canonical label keys. The distribution is verbalized by the
model in its output text - we explicitly mark probs_source="verbalized".
This is NOT logprobs; token-level logprobs are not used anywhere.

A provider that cannot take a strict JSON schema gets the weaker
`{"type": "json_object"}` through `request_options`; the run manifest records
which constraint each model actually ran under, because a schema failure under
a weaker constraint is not the same finding as one under a strict schema.
"""

from __future__ import annotations

import json

from .base import DecisionResult, http_post_json

_SYSTEM = (
    "You are a calibration engine. You never answer in prose. You output only "
    "a JSON object with the key 'probabilities' mapping every given option to "
    "a probability, all options included, values in [0,1], summing to 1."
)


class OpenAICompatAdapter:
    name = "openai_compat"

    def __init__(self, endpoint, model, key_env="OPENAI_COMPAT_API_KEY",
                 timeout_s=120.0, price_input_per_m=None, price_output_per_m=None):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.key_env = key_env
        self.timeout_s = timeout_s
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m

    def build_request(self, task) -> dict:
        labels = [str(x) for x in task.labels]
        qtype = task.question["type"]
        crit = task.question.get("criteria")
        instructions = task.question["instructions"]
        if qtype == "score":
            legend = "\n".join(f"{lab}: {crit[int(lab)]}" for lab in labels)
            user = (
                f"{instructions}\n\nLevels:\n{legend}\n\n"
                "Rate the state. Output probabilities over the level indices: "
                f"{json.dumps(labels)}."
            )
        else:
            opt_lines = []
            if isinstance(crit, dict):
                for lab in labels:
                    desc = crit.get({"yes":"true","no":"false"}.get(lab,lab)) if qtype=="noul" else crit.get(lab)
                    opt_lines.append(f"- {lab}: {desc}" if desc else f"- {lab}")
            else:
                opt_lines = [f"- {lab}" for lab in labels]
            user = (
                f"{instructions}\n\nOptions:\n" + "\n".join(opt_lines)
                + f"\n\nOutput probabilities over exactly these keys: "
                f"{json.dumps(labels)}."
            )
        if isinstance(task.state, str):
            state_text = task.state
        else:
            state_text = json.dumps(task.state, ensure_ascii=False)
        schema = {
            "type": "object",
            "properties": {
                "probabilities": {
                    "type": "object",
                    "properties": {k: {"type": "number"} for k in labels},
                    "required": labels,
                    "additionalProperties": False,
                }
            },
            "required": ["probabilities"],
            "additionalProperties": False,
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"State:\n{state_text}\n\n{user}"},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "distribution", "schema": schema, "strict": True}},
            "temperature": 0,
            "max_tokens": 4096,
        }
        # Providers differ on which of these knobs exist at all. An override of
        # None removes the field, so a run can say "this model has no
        # temperature" instead of arguing with a 400. Every override is copied
        # into the run manifest, so a published number names its settings.
        for k, v in getattr(self, "request_options", {}).items():
            if v is None:
                body.pop(k, None)
            else:
                body[k] = v
        return body

    def run(self, task) -> DecisionResult:
        import os
        key = os.environ.get(self.key_env, "")
        if not key:
            return DecisionResult(
                adapter=self.name, ok=False, error=f"missing env key {self.key_env}",
                probs_source="verbalized", model=self.model,
            )
        body = self.build_request(task)
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            status, parsed, latency = http_post_json(
                f"{self.endpoint}/chat/completions", body, headers, self.timeout_s
            )
        except ConnectionError as e:
            return DecisionResult(
                adapter=self.name, ok=False, error=str(e),
                probs_source="verbalized", model=self.model,
            )
        res = DecisionResult(
            adapter=self.name, ok=False, status=status, latency_s=latency,
            probs_source="verbalized", model=parsed.get("model", self.model) if isinstance(parsed,dict) else self.model, raw=parsed, request_body=body,
        )
        if status != 200 or not isinstance(parsed, dict):
            res.error = f"HTTP {status}: {str(parsed)[:300]}"
            return res
        choices = parsed.get("choices") or []
        if not choices:
            res.error = "no choices in response"
            return res
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        res.usage = parsed.get("usage") or {}
        res.usage["input_tokens"] = res.usage.get("prompt_tokens",res.usage.get("input_tokens"))
        res.usage["output_tokens"] = res.usage.get("completion_tokens",res.usage.get("output_tokens"))
        try:
            obj = json.loads(content)
            if not isinstance(obj,dict) or set(obj)!={"probabilities"}: raise ValueError("JSON does not match schema")
            probs = obj["probabilities"]
            if not isinstance(probs, dict):
                raise ValueError("probabilities is not an object")
            res.probs = probs
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            res.error = f"verbalized distribution parse failed: {e}"
            return res
        res.ok = True
        return res

    def reserve_estimate(self, task) -> float:
        """Unknown price -> None unless explicit prices were configured."""
        import math
        pin = self.price_input_per_m
        pout = self.price_output_per_m
        if pin is None or pout is None:
            return None
        # conservative caps: 100k input tokens, 4k output tokens per request
        return 100_000 * pin / 1e6 + 4_000 * pout / 1e6
