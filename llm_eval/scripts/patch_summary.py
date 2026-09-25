"""Synthesize a partial summary.json from a results.jsonl for cell 14 to read.

Used when a multi-run is still in-flight and we want to surface partial real
data in the cross-model chart immediately. Reads usage/acc/brier/ece directly
from results.jsonl, computes the same fields llm_eval.summarize would compute,
and writes to <real_root>/<label>/summary.json.

Usage:
  python3 scripts/patch_summary.py <run_id> <label>
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) < 3:
        print("usage: patch_summary.py <run_id> <label> [runner_dir_name]")
        return 1
    run_id = sys.argv[1]
    label = sys.argv[2]
    # runner_dir_name defaults to label (with dots replaced by underscores for slug).
    # Accept both "real-" and "cell12-" prefixes for run_id.
    if not run_id.startswith(("cell12-", "real-")):
        run_id = f"cell12-{label}"
    runner_dir_name = sys.argv[3] if len(sys.argv) > 3 else label.replace(".", "_")
    real_root = PROJ / "runs" / "notebook-demo" / "real"
    src_results = real_root / "_tmp" / run_id / runner_dir_name / "results.jsonl"
    if not src_results.exists():
        print(f"missing {src_results}")
        return 1
    target = real_root / label
    target.mkdir(parents=True, exist_ok=True)
    tgt_results = target / "results.jsonl"
    src_text = src_results.read_text()
    if not tgt_results.exists() or tgt_results.stat().st_size == 0:
        tgt_results.write_text(src_text)

    # pre-parse tasks once
    sys.path.insert(0, str(PROJ))
    from llm_eval.task import load_tasks
    from llm_eval.adapters import PROVIDERS
    tasks = {t.id: t for t in load_tasks("tasks/public_all.jsonl")}

    # Map label → (price_in_per_m, price_out_per_m) — same source the runner uses.
    PRICE_BY_LABEL = {
        "deepseek-flash":     (PROVIDERS["deepseek"]["price_in_per_m"], PROVIDERS["deepseek"]["price_out_per_m"]),
        "kimi-k3":            (PROVIDERS.get("moonshot", {}).get("price_in_per_m"), PROVIDERS.get("moonshot", {}).get("price_out_per_m")),
        "glm-5.3-codeplan":   (PROVIDERS.get("glm", {}).get("price_in_per_m"), PROVIDERS.get("glm", {}).get("price_out_per_m")),
        "doubao-2.1-pro":     (0.80, 1.00),  # 20-yuan plan: user-confirmed price tier
    }
    price_in, price_out = PRICE_BY_LABEL.get(label, (None, None))

    n_total = 0
    n_ok = 0
    n_err = 0
    n_unat = 0
    latencies = []
    correct = 0
    scorable = 0
    brier_total = 0.0
    token_in_total = 0
    token_out_total = 0
    cost_total = 0.0
    schema_valid_pairs = 0

    for line in src_text.splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        n_total += 1
        status = r.get("status")
        if status == "ok":
            n_ok += 1
            lat = r.get("latency_s")
            if lat:
                latencies.append(lat)
            probs = r.get("probs") or {}
            usage = r.get("usage") or {}
            ti = usage.get("prompt_tokens", 0) or 0
            to = usage.get("completion_tokens", 0) or 0
            token_in_total += ti
            token_out_total += to
            if price_in is not None and price_out is not None:
                cost_total += (ti * price_in + to * price_out) / 1e6
            tid = r.get("task_id")
            task = tasks.get(tid)
            if task is not None:
                expected_str = task.expected
                labels = task.labels
                # schema validity: all labels present in probs (key match)
                if all(lbl in probs for lbl in labels):
                    schema_valid_pairs += 1
                # accuracy: argmax(probs) == expected
                scorable += 1
                if probs:
                    pred = max(probs, key=probs.get)
                    if pred == expected_str:
                        correct += 1
                # brier (1-hot target distribution)
                b = 0.0
                for lbl in labels:
                    pred_p = float(probs.get(lbl, 0.0))
                    target_p = 1.0 if lbl == expected_str else 0.0
                    b += (pred_p - target_p) ** 2
                brier_total += b
        elif status == "error":
            n_err += 1
        elif status == "unattempted":
            n_unat += 1

    accuracy = correct / scorable if scorable else None
    brier = brier_total / scorable if scorable else None

    # ECE (10-bin equal-width) — second pass to bin per-record, then aggregate
    ece_bins = [{"lo": i * 0.1, "hi": (i + 1) * 0.1, "n": 0, "sum_conf": 0.0, "sum_acc": 0.0} for i in range(10)]
    if scorable:
        for line in src_text.splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("status") != "ok":
                continue
            probs = r.get("probs") or {}
            tid = r.get("task_id")
            task = tasks.get(tid)
            if task is None or not probs:
                continue
            expected_str = task.expected
            conf = max(probs.values())
            pred = max(probs, key=probs.get)
            bin_idx = min(int(conf * 10), 9)
            ece_bins[bin_idx]["n"] += 1
            ece_bins[bin_idx]["sum_conf"] += conf
            ece_bins[bin_idx]["sum_acc"] += 1.0 if pred == expected_str else 0.0

    ece = None
    ece_total_conf_acc = 0.0
    for bin_ in ece_bins:
        if bin_["n"] > 0:
            mean_conf = bin_["sum_conf"] / bin_["n"]
            mean_acc  = bin_["sum_acc"]  / bin_["n"]
            ece_total_conf_acc += (bin_["n"] / scorable) * abs(mean_conf - mean_acc)
    ece = round(ece_total_conf_acc, 6)

    # ordinal MAE (probability-weighted, labels in order); only for tasks where
    # question_type == 'ordinal' (we'd need task attribute). Most public_all tasks
    # are 'choice' or 'noul' so this is 0 / None — leave None.
    ordinal_mae = None

    sorted_lats = sorted(latencies) if latencies else []
    summary = {
        "n_tasks": 231,  # full bench size (consistent across rows)
        "n_scorable": scorable,
        "schema_validity": schema_valid_pairs / n_total if n_total else 0.0,
        "schema_validity_strict": schema_valid_pairs / n_total if n_total else 0.0,
        "accuracy": accuracy,
        "brier": brier,
        "ece": ece,
        "ordinal_mae": ordinal_mae,
        "ece_bins": [],
        "p50_s": sorted_lats[len(sorted_lats) // 2] if sorted_lats else None,
        "p95_s": sorted_lats[int(len(sorted_lats) * 0.95)] if sorted_lats else None,
        "cost_usd_total": round(cost_total, 6) if (price_in is not None and price_out is not None) else None,
        "latency_samples": len(latencies),
        "partial": True,
        "patched_at": time.time(),
        "run_meta": {
            "run_id": run_id,
            "runner": label,
            "adapter": label,
            "model": label,
        },
    }
    (target / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"patched {label}: n_ok={n_ok} err={n_err} unat={n_unat} acc={accuracy} brier={brier} tok_in={token_in_total} tok_out={token_out_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
