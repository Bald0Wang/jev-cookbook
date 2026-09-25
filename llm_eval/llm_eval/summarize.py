"""Summarize a results.jsonl into a public-safe aggregate.

public_export() deliberately ignores any summary passed in and recomputes
everything from the per-task records via an allowlist. A test proves a
private item's text cannot ride out with it.
"""
from __future__ import annotations

import json

from .metrics import aggregate, jevbench_score
from .task import Task

# Whitelist of fields allowed in the public summary. Anything else is dropped.
_PUBLIC_FIELDS = {
    "n_tasks",
    "n_scorable",
    "schema_validity",
    "schema_validity_strict",
    "accuracy",
    "majority_class_accuracy",
    "brier",
    "ece",
    "ece_bins",
    "ordinal_mae",
    "p50_s",
    "p95_s",
    "cost_usd_total",
    "paraphrase_consistency",
    "per_family",
    "per_topic",
    "stop_reason",
    "run_meta",
    "jevbench_score",
}


def load_results(path: str) -> list[dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def public_export(results: list[dict], tasks: list[Task], run_meta: dict | None = None) -> dict:
    tasks_by_id = {t.id: t for t in tasks}
    full = aggregate(results, tasks_by_id)
    full["run_meta"] = run_meta or {}
    # Per-topic (only the ones that appeared).
    per_topic: dict[str, dict] = {}
    for r in results:
        t = tasks_by_id.get(r["task_id"])
        if t is None:
            continue
        if t.topic:
            per_topic.setdefault(t.topic, {"n": 0, "correct": 0})
            per_topic[t.topic]["n"] += 1
            if r.get("correct_value"):
                per_topic[t.topic]["correct"] += 1
    per_topic = {
        k: {"n": v["n"], "accuracy": (v["correct"] / v["n"]) if v["n"] else None}
        for k, v in per_topic.items()
    }
    full["per_topic"] = per_topic

    # JevBench composite score (4 axes → geometric mean, low-Intelligence
    # penalty). chance baseline uses the largest label-set size observed
    # in the dataset (most generous; conservative would use the per-task
    # average).
    max_label_set = 0
    for t in tasks:
        if t.labels:
            max_label_set = max(max_label_set, len(t.labels))
    full["jevbench_score"] = jevbench_score(
        accuracy=full.get("accuracy"),
        n_scorable=full.get("n_scorable") or 0,
        label_set_size_max=max_label_set,
        ece=full.get("ece"),
        p50_s=full.get("p50_s"),
        cost_usd_total=full.get("cost_usd_total"),
        n_tasks=full.get("n_tasks") or 0,
    )

    return {k: v for k, v in full.items() if k in _PUBLIC_FIELDS}