"""Mock adapter. Always returns the expected label with prob 1.0
(or a peaked distribution if you prefer), with controllable latency.
Use it to dry-run the harness end-to-end without spending API credits.
"""
from __future__ import annotations

import time
from typing import Any

from .base import AdapterError


class MockAdapter:
    adapter_name = "mock"

    def __init__(
        self,
        *,
        model: str = "mock",
        peak: bool = True,           # True = argmax at expected; False = uniform
        # When `peak` is False but `uniform` is True, returns a flat uniform
        # distribution over all labels (mostly wrong, never confident).
        uniform: bool = False,
        latency_s: float = 0.05,
        fail_on: set[str] | None = None,
        fatal_on: set[str] | None = None,
    ):
        self.model = model
        self.peak = peak
        self.uniform = uniform
        self.latency_s = latency_s
        self.fail_on = set(fail_on or [])
        self.fatal_on = set(fatal_on or [])

    def call(self, task) -> dict:
        time.sleep(self.latency_s)
        if task.id in self.fatal_on:
            raise AdapterError("mock fatal", fatal=True, code=429)
        if task.id in self.fail_on:
            raise AdapterError("mock transient", code=500)

        labels = list(task.labels)
        if self.uniform:
            n = len(labels)
            probs = {lab: 1.0 / n for lab in labels}
        elif self.peak and task.expected in labels:
            probs = {lab: (1.0 if lab == task.expected else 0.0) for lab in labels}
        else:
            n = len(labels)
            probs = {lab: 1.0 / n for lab in labels}
        return {
            "probs": probs,
            "source": "native",
            "model": self.model,
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            "request_body": {"_mock": True},
            "raw": {"_mock": True, "task_id": task.id},
            "latency_s": self.latency_s,
            "status": 200,
        }