"""Adapter registry. Per-provider configs are thin shims over
OpenAICompatAdapter; their default base URL, default model and
published pricing live here so they stay easy to update.
"""
from __future__ import annotations

from typing import Any

from .base import AdapterError
from .mock import MockAdapter
from .openai_compat import OpenAICompatAdapter
from .typesafe import TypesafeAdapter


# Provider presets. base_url is the OpenAI-compatible chat completions endpoint.
# Models default to the latest known general-purpose model; override via --model.
# Prices are USD per 1M tokens (input, output). null == unmetered.
# `mode` flags whether the model returns its OWN probability distribution
# ('native', Jev-class) or is a generic LLM we ask to WRITE one out
# ('verbalized', JSON-schema constrained). The two are labelled separately
# per the JevBench convention.
PROVIDERS: dict[str, dict[str, Any]] = {
    # ── JevBench reference row ──────────────────────────────────────────
    # Native System One — returns its own probability distribution over
    # the exact label set. Not a verbalized model.
    "jev": {
        "base_url": "https://api.typesafe.ai",   # /v1/systemone is appended by adapter
        "default_model": "jev-latest",
        "price_in_per_m": 0.042,   # $0.042 per 1M input tokens
        "price_out_per_m": 0.0,    # output tokens are free
        "mode": "native",
        "notes": "TypeSafe AI's Jev (System One). https://docs.typesafe.ai/models",
    },
    "typesafe": {  # alias kept for backward compatibility
        "base_url": "https://api.typesafe.ai",
        "default_model": "jev-latest",
        "price_in_per_m": 0.042,
        "price_out_per_m": 0.0,
        "mode": "native",
        "notes": "Alias of `jev`. See https://docs.typesafe.ai/models",
    },
    # ── Chinese-model evaluation set (verbalized via JSON schema) ──────
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-flash",  # was deepseek-v4.1
        "price_in_per_m": 0.27,             # V4.1 cache-miss input (placeholder)
        "price_out_per_m": 1.10,
        "mode": "verbalized",
        "notes": "DeepSeek-flash (cache-miss input; cache-hit $0.07/M). Use deepseek-v4-pro for higher quality.",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen3.8-max",     # was qwen-plus
        "price_in_per_m": 0.004,
        "price_out_per_m": 0.012,
        "mode": "verbalized",
        "notes": "DashScope OpenAI-compatible mode. qwen3.8-max / qwen3-max / qwen-plus.",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-5.3",         # was glm-4-plus
        "price_in_per_m": 0.50,
        "price_out_per_m": 0.50,
        "mode": "verbalized",
        "notes": "Zhipu BigModel. GLM-5.3 codeplan tier — 0.5/0.5 USD per 1M.",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k3",         # was moonshot-v1-32k
        "price_in_per_m": 0.10,
        "price_out_per_m": 0.30,
        "mode": "verbalized",
        "notes": "Moonshot Kimi K3. temperature=1 only — set request_options={'temperature': 1}.",
    },
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "",                # auto-discover latest doubao-seed-2-1-pro-* endpoint
        "price_in_per_m": 0.80,
        "price_out_per_m": 1.00,
        "mode": "verbalized",
        "notes": "ByteDance 豆包 via 火山方舟. --model takes the endpoint id (e.g. doubao-seed-2-1-pro-260915); the notebook auto-discovers it.",
    },
    "stepfun": {
        "base_url": "https://api.stepfun.com/v1",
        "default_model": "step-5",          # was step-1-8k
        "price_in_per_m": 1.00,
        "price_out_per_m": 2.00,
        "mode": "verbalized",
        "notes": "阶跃星辰 StepFun codingplan tier. step-5 / step-2 / step-1.",
    },
    "xiaomi": {
        "base_url": "https://api.xiaomi.com/v1",
        "default_model": "mimo-2.6-pro",    # was mimo
        "price_in_per_m": None,
        "price_out_per_m": None,
        "mode": "verbalized",
        "notes": "小米 MiMo 2.6-pro. base_url is a placeholder until the public API is confirmed — verify before charging.",
    },
    "k3": {  # alias of moonshot (kept for back-compat with older configs)
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k3",
        "price_in_per_m": 0.10,
        "price_out_per_m": 0.30,
        "mode": "verbalized",
        "notes": "Alias of `moonshot` with default_model=kimi-k3.",
    },
}


def get_adapter(
    *,
    name: str,
    model: str = "",
    endpoint: str = "",
    key: str = "",
    request_options: dict | None = None,
    price_in_per_m: float | None = None,
    price_out_per_m: float | None = None,
    max_input_tokens: int = 2000,
    max_output_tokens: int = 200,
    **kwargs,
):
    """Factory. Always returns an object exposing .call(task)."""
    if name == "mock":
        # If the model name starts with 'uniform', return a flat dist (mostly wrong).
        uniform = model.startswith("uniform")
        return MockAdapter(uniform=uniform)
    if name == "openai_compat":
        if not endpoint:
            raise ValueError("--endpoint required for openai_compat")
        return OpenAICompatAdapter(
            base_url=endpoint,
            model=model,
            key=key,
            request_options=request_options,
        )
    if name in PROVIDERS:
        spec = PROVIDERS[name]
        base_url = endpoint if endpoint else spec["base_url"]
        mdl = model or spec["default_model"]
        # Jev (TypeSafe) is NOT OpenAI-compatible — it exposes its own
        # /v1/systemone endpoint. Route it to the native adapter.
        if name in ("jev", "typesafe"):
            return TypesafeAdapter(
                base_url=base_url,
                model=mdl,
                key=key,
                request_options=request_options,
            )
        return OpenAICompatAdapter(
            base_url=base_url,
            model=mdl,
            key=key,
            request_options=request_options,
        )
    raise ValueError(f"unknown adapter: {name!r}")