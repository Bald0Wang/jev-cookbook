"""Multi-runner configuration.

JSON config that lists one or more (adapter, model, key_env) runners sharing
the same task set. Validated here; consumed by multi_runner.py.

Schema:
    {
      "run_id": str,                       # subdir under runs/
      "tasks": str,                        # path to JSONL tasks
      "cap_usd": float,                    # per-runner budget cap
      "delay_s": float,                    # pacing between requests
      "max_input_tokens": int,
      "max_output_tokens": int,
      "request_options": dict | null,
      "runners": [
        {
          "name": str,                     # subdir under runs/<run_id>/
          "adapter": str,                  # adapter name from registry
          "model": str,
          "endpoint": str,                 # override base url; default from preset
          "key_env": str,                  # env var holding the key; '' = public
          "price_in_per_m": float | null,
          "price_out_per_m": float | null,
          "skip_if_done": bool             # resume support; default true
        },
        ...
      ]
    }
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


class ConfigError(ValueError):
    pass


@dataclass
class RunnerConfig:
    name: str
    adapter: str
    model: str = ""
    endpoint: str = ""
    key_env: str = ""
    price_in_per_m: Optional[float] = None
    price_out_per_m: Optional[float] = None
    request_options: Optional[dict] = None
    skip_if_done: bool = True

    def effective_key(self) -> str:
        return os.environ.get(self.key_env, "") if self.key_env else ""

    def is_available(self) -> bool:
        """No key required, or key is set in environment."""
        if not self.key_env:
            return True
        return bool(os.environ.get(self.key_env))


@dataclass
class MultiRunConfig:
    run_id: str
    tasks_path: str
    runners: list[RunnerConfig] = field(default_factory=list)
    cap_usd: float = 1.5
    delay_s: float = 0.3
    max_input_tokens: int = 2000
    max_output_tokens: int = 200
    request_options: Optional[dict] = None
    out_root: str = "runs"

    def validate(self) -> None:
        if not self.run_id:
            raise ConfigError("run_id is required")
        if not self.runners:
            raise ConfigError("at least one runner is required")
        names = [r.name for r in self.runners]
        if len(set(names)) != len(names):
            raise ConfigError(f"runner names must be unique; got {names}")
        for r in self.runners:
            if not r.name:
                raise ConfigError("runner.name is required")
            if not r.adapter:
                raise ConfigError(f"runner {r.name!r}: adapter is required")
        if self.cap_usd <= 0:
            raise ConfigError("cap_usd must be positive")


def load_config(path: str) -> MultiRunConfig:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return _from_dict(d)


def _from_dict(d: dict) -> MultiRunConfig:
    if "run_id" not in d:
        raise ConfigError("missing 'run_id'")
    if "tasks" not in d:
        raise ConfigError("missing 'tasks'")
    runners = [
        RunnerConfig(
            name=r["name"],
            adapter=r["adapter"],
            model=r.get("model", ""),
            endpoint=r.get("endpoint", ""),
            key_env=r.get("key_env", ""),
            price_in_per_m=r.get("price_in_per_m"),
            price_out_per_m=r.get("price_out_per_m"),
            request_options=r.get("request_options"),
            skip_if_done=bool(r.get("skip_if_done", True)),
        )
        for r in d.get("runners", [])
    ]
    cfg = MultiRunConfig(
        run_id=d["run_id"],
        tasks_path=d["tasks"],
        runners=runners,
        cap_usd=float(d.get("cap_usd", 1.5)),
        delay_s=float(d.get("delay_s", 0.3)),
        max_input_tokens=int(d.get("max_input_tokens", 2000)),
        max_output_tokens=int(d.get("max_output_tokens", 200)),
        request_options=d.get("request_options"),
        out_root=d.get("out_root", "runs"),
    )
    cfg.validate()
    return cfg