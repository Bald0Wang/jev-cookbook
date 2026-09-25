"""Laya-local adapter — points at a local `python -m laya.serve` exposing
`/v1/systemone` on 127.0.0.1:8811.

Wire format is identical to TypeSafe's Jev (`{state, questions} → {answers}`),
so this adapter inherits `TypesafeAdapter` entirely and only overrides the
default endpoint / model / key. No new HTTP or decoding code lives here.

Cost basis is "local self-hosted, no provider tariff" — `price_in_per_m=None`,
`price_out_per_m=None`. The framework reports `cost_usd_total = 0` for this
runner and excludes it from the Cost axis in the geometric mean (axes with
null values are skipped, never fabricated; see `summarize.py`).
"""
from __future__ import annotations

from .typesafe import TypesafeAdapter


DEFAULT_BASE_URL = "http://127.0.0.1:8811"
DEFAULT_MODEL = "laya-multilingual"


class LayaLocalAdapter(TypesafeAdapter):
    """Native Laya serve adapter — same call shape as `TypesafeAdapter`."""

    adapter_name = "laya_local"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        key: str = "",
        request_options: dict | None = None,
        timeout_s: float = 120.0,
    ):
        # The local serve binds to loopback with no auth; we still pass a
        # non-empty placeholder so TypesafeAdapter.__init__'s `if not key`
        # guard doesn't fire. The local server ignores Authorization.
        super().__init__(
            base_url=base_url,
            model=model,
            key=key or "no-key-needed",
            request_options=request_options,
            timeout_s=timeout_s,
        )


# Defaults consumed by the runner / factory.
DEFAULT_PRICE_IN = None
DEFAULT_PRICE_OUT = None