"""Extract privacy-conscious aggregates from an uploaded JevBench results ZIP.

The archive is read in place and never extracted. Raw model responses, prompts,
provider ledgers, and credentials are not copied into the repository.
"""

from __future__ import annotations

import argparse
import collections
import json
import zipfile
from pathlib import Path


CHAPTER = Path(__file__).resolve().parents[2]
OUTPUT_PATH = CHAPTER / "figures" / "jevbench-2026-09-26" / "snapshot.json"
MODEL_IDS = ["deepseek-flash", "doubao-2.1-pro", "glm-5.3-codeplan", "jev", "kimi-k3"]
DISPLAY_NAMES = {
    "deepseek-flash": "DeepSeek Flash",
    "doubao-2.1-pro": "Doubao 2.1 Pro",
    "glm-5.3-codeplan": "GLM 5.3 Codeplan",
    "jev": "Jev",
    "kimi-k3": "Kimi K3",
}


def aggregate_model(archive, model_id):
    prefix = f"runs/notebook-demo/real/{model_id}/"
    summary = json.loads(archive.read(prefix + "summary.json"))
    rows = [
        json.loads(line)
        for line in archive.read(prefix + "results.jsonl").decode("utf-8").splitlines()
        if line.strip()
    ]
    status_counts = collections.Counter(row.get("status", "(missing)") for row in rows)
    family = collections.defaultdict(collections.Counter)
    split = collections.defaultdict(collections.Counter)
    stop_reasons = collections.Counter()
    empty_probability_errors = 0

    for row in rows:
        status = row.get("status", "(missing)")
        is_valid = bool(row.get("valid"))
        is_correct = row.get("correct_value") is True
        group = row["task_id"].split("-", 1)[0]
        for counts in (family[row["family"]], split[group]):
            counts["total"] += 1
            counts["valid"] += int(is_valid)
            counts["correct"] += int(is_correct)
            counts["error"] += int(status == "error")
            counts["invalid"] += int(status == "invalid")
            counts["unattempted"] += int(status == "unattempted")
        if row.get("stop_reason"):
            stop_reasons[row["stop_reason"]] += 1
        if status == "error" and "could not parse probs from: ''" in str(row.get("error", "")):
            empty_probability_errors += 1

    n_valid = sum(bool(row.get("valid")) for row in rows)
    n_correct = sum(row.get("correct_value") is True for row in rows)
    total_cost = float(summary.get("cost_usd_total") or 0)
    return {
        "id": model_id,
        "display_name": DISPLAY_NAMES[model_id],
        "n_tasks": len(rows),
        "n_scorable": int(summary.get("n_scorable") or n_valid),
        "n_valid": n_valid,
        "n_correct": n_correct,
        "conditional_accuracy": summary.get("accuracy"),
        "correct_rate_all_tasks": n_correct / len(rows) if rows else None,
        "valid_rate": n_valid / len(rows) if rows else None,
        "status_counts": {key: status_counts.get(key, 0) for key in ["ok", "error", "invalid", "unattempted"]},
        "stop_reasons": dict(stop_reasons),
        "empty_probability_parse_errors": empty_probability_errors,
        "brier": summary.get("brier"),
        "ece": summary.get("ece"),
        "p50_s": summary.get("p50_s"),
        "p95_s": summary.get("p95_s"),
        "cost_usd_total": total_cost,
        "observed_cost_per_valid_usd": total_cost / n_valid if n_valid else None,
        "jevbench_score": summary.get("jevbench_score", {}).get("score"),
        "jevbench_axes": summary.get("jevbench_score", {}).get("axes", {}),
        "split": {key: dict(value) for key, value in split.items()},
        "family": {key: dict(value) for key, value in family.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", dest="zip_path", required=True, type=Path, help="Uploaded JevBench results ZIP")
    args = parser.parse_args()
    zip_path = args.zip_path.expanduser().resolve()
    with zipfile.ZipFile(zip_path) as archive:
        models = [aggregate_model(archive, model_id) for model_id in MODEL_IDS]

    metadata = {
        "snapshot_date": "2026-09-26",
        "source_zip": zip_path.name,
        "source_members": [
            "runs/notebook-demo/real/{provider}/summary.json",
            "runs/notebook-demo/real/{provider}/results.jsonl",
        ],
        "task_rows_by_provider": {model["id"]: model["n_tasks"] for model in models},
        "models_order": MODEL_IDS,
        "metrics_note": (
            "conditional_accuracy, Brier and ECE are computed on scorable responses; "
            "valid_rate and correct_rate_all_tasks use all task rows; p50/p95 use rows "
            "with observed latency; observed_cost_per_valid_usd = total recorded spend / "
            "valid responses; source composite is preserved as emitted."
        ),
        "privacy_note": (
            "This compact snapshot contains aggregate metrics and per-family/split counts only. "
            "Raw prompts, model outputs, provider ledgers and credentials are excluded."
        ),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"metadata": metadata, "models": models}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")
    for model in models:
        print(
            f"{model['display_name']}: {model['n_valid']}/{model['n_tasks']} valid, "
            f"conditional accuracy={model['conditional_accuracy']:.4f}"
        )


if __name__ == "__main__":
    main()
