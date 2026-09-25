"""Configuration resolution."""

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx2

from typesafe_sdk._core.errors import TypeSafeError
from typesafe_sdk.constants import (
    API_KEY_ENV,
    BASE_URL_ENV,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_MODEL_ENV,
    DEFAULT_TIMEOUT,
)


def _resolve_env(value: str | None, env: str, default: str | None = None) -> str | None:
    return value if value is not None else os.environ.get(env, "").strip() or default


def resolve_timeout(timeout: float | httpx2.Timeout) -> float | httpx2.Timeout:
    if not isinstance(timeout, httpx2.Timeout) and (not math.isfinite(timeout) or timeout <= 0):
        raise TypeSafeError("timeout must be a positive, finite number of seconds.")
    return timeout


@dataclass
class Config:
    api_key: str = field(repr=False)
    base_url: str
    default_model: str
    timeout: float | httpx2.Timeout
    default_headers: httpx2.Headers = field(repr=False)

    @classmethod
    def resolve(
        cls,
        api_key: str | None,
        base_url: str | None,
        default_model: str | None,
        timeout: float | httpx2.Timeout | None,
        default_headers: Mapping[str, str] | None,
    ) -> "Config":
        key = _resolve_env(api_key, API_KEY_ENV)
        if key is None:
            raise TypeSafeError(f"No API key was provided. Pass api_key or set the {API_KEY_ENV} environment variable.")
        resolved_base_url = _resolve_env(base_url, BASE_URL_ENV, DEFAULT_BASE_URL)
        resolved_model = _resolve_env(default_model, DEFAULT_MODEL_ENV, DEFAULT_MODEL)
        assert resolved_base_url is not None, "DEFAULT_BASE_URL default guarantees a value"  # noqa: S101 - narrows the non-None default.
        assert resolved_model is not None, "DEFAULT_MODEL default guarantees a value"  # noqa: S101 - narrows the non-None default.
        return cls(
            key,
            resolved_base_url.rstrip("/"),
            resolved_model,
            resolve_timeout(DEFAULT_TIMEOUT if timeout is None else timeout),
            httpx2.Headers(default_headers),
        )
