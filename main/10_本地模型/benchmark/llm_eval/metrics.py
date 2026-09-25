"""Aggregate metrics from per-task scored results.

Conventions match the JevBench README:
  * Accuracy: argmax for classification; ordinal reports both argmax accuracy
    and probability-weighted MAE.
  * Brier: multi-class sum over the exact label set; binary uses 2-class
    convention so numbers are comparable.
  * ECE: top-label confidence, 10 equal-width bins.
  * Latency: p50 / p95 across all attempts.
  * Paraphrase: both-correct consistency over paraphrase pairs.
  * Empty metrics return None with n=0, not 0.0.
"""
from __future__ import annotations

import math
from collections import defaultdict


def percentile(values: list, q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    k = (len(vals) - 1) * q
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vals[int(k)]
    return vals[f] * (c - k) + vals[c] * (k - f)


def latency_summary(seconds: list) -> dict:
    ok = [v for v in seconds if v is not None]
    return {
        "n": len(ok),
        "p50_s": percentile(ok, 0.5),
        "p95_s": percentile(ok, 0.95),
    }


def brier_score(probs: dict, expected_label: str, labels: list) -> float:
    if len(labels) == 2 and expected_label in labels:
        p_yes = probs[expected_label]
        no_label = labels[0] if labels[1] == expected_label else labels[1]
        p_no = probs[no_label]
        return (p_yes - 1.0) ** 2 + (p_no - 0.0) ** 2
    return sum(
        (float(probs.get(lab, 0.0)) - (1.0 if lab == expected_label else 0.0)) ** 2
        for lab in labels
    )


def ece_top_label(pairs: list, n_bins: int = 10) -> dict:
    """Expected calibration error over (confidence, correct) pairs."""
    bins = [
        {"lo": i / n_bins, "hi": (i + 1) / n_bins, "n": 0, "conf_sum": 0.0, "correct": 0}
        for i in range(n_bins)
    ]
    for conf, correct in pairs:
        conf = min(max(float(conf), 0.0), 1.0)
        idx = min(int(conf * n_bins), n_bins - 1)
        b = bins[idx]
        b["n"] += 1
        b["conf_sum"] += conf
        b["correct"] += 1 if correct else 0
    n_total = sum(b["n"] for b in bins)
    ece = 0.0
    for b in bins:
        if b["n"]:
            acc = b["correct"] / b["n"]
            mean_conf = b["conf_sum"] / b["n"]
            ece += (b["n"] / n_total) * abs(acc - mean_conf)
    return {
        "ece": ece if n_total else None,
        "n": n_total,
        "bins": [
            {
                "lo": b["lo"],
                "hi": b["hi"],
                "n": b["n"],
                "mean_confidence": (b["conf_sum"] / b["n"]) if b["n"] else None,
                "accuracy": (b["correct"] / b["n"]) if b["n"] else None,
            }
            for b in bins
        ],
    }


def ordinal_mae(pairs: list) -> float | None:
    """Mean absolute error over (expected_level:int, predicted_ev:float)."""
    if not pairs:
        return None
    return sum(abs(e - p) for e, p in pairs) / len(pairs)


def paraphrase_consistency(results_by_id: dict, tasks_by_id: dict) -> dict:
    """Both-correct consistency over paraphrase pairs."""
    groups: dict[str, list[str]] = defaultdict(list)
    for tid, t in tasks_by_id.items():
        if t.group:
            groups[t.group].append(tid)
    n_pairs = n_answered = n_correct = n_unscorable = 0
    for _, ids in sorted(groups.items()):
        if len(ids) < 2:
            continue
        n_pairs += 1
        outcomes = [results_by_id.get(i) for i in ids]
        if any(o is None or not o.get("valid") for o in outcomes):
            continue
        n_answered += 1
        if any(o.get("correct_value") is None for o in outcomes):
            n_unscorable += 1
            continue
        if all(o.get("correct_value") for o in outcomes):
            n_correct += 1
    return {
        "pairs": n_pairs,
        "both_answered_valid": n_answered,
        "both_correct": n_correct,
        "unscorable_expected_none": n_unscorable,
        "consistency": (n_correct / n_answered) if n_answered else None,
    }


def aggregate(results: list[dict], tasks_by_id: dict) -> dict:
    """Reduce per-task scored records to summary stats.

    `results` is a list of dicts produced by scorer.score_distribution.
    """
    if not results:
        return {
            "n_tasks": 0,
            "n_scorable": 0,
            "schema_validity": None,
            "schema_validity_strict": None,
            "accuracy": None,
            "majority_class_accuracy": None,
            "brier": None,
            "ece": None,
            "ordinal_mae": None,
            "p50_s": None,
            "p95_s": None,
            "cost_usd": None,
            "paraphrase_consistency": None,
            "per_family": {},
        }

    n_tasks = len(results)
    n_strict = sum(1 for r in results if r.get("strict_valid"))
    n_valid = sum(1 for r in results if r.get("valid"))
    scorable = [r for r in results if r.get("correct_value") is not None]
    n_scorable = len(scorable)
    n_correct = sum(1 for r in scorable if r.get("correct_value"))
    accuracy = (n_correct / n_scorable) if n_scorable else None

    # majority-class baseline per family
    per_family_correct: dict[str, list] = defaultdict(list)
    for r in results:
        t = tasks_by_id.get(r["task_id"])
        if t is None or not r.get("valid") or r.get("correct_value") is None:
            continue
        per_family_correct[t.family].append(r.get("correct_value"))
    per_family = {
        fam: {
            "n": len(vs),
            "accuracy": (sum(vs) / len(vs)) if vs else None,
        }
        for fam, vs in per_family_correct.items()
    }

    # majority-class accuracy: for each task, what's the most-common expected label in its family?
    family_expected: dict[str, list[str]] = defaultdict(list)
    for tid, t in tasks_by_id.items():
        if t.expected is not None:
            family_expected[t.family].append(t.expected)
    majority_label: dict[str, str] = {}
    for fam, labels in family_expected.items():
        counts: dict[str, int] = defaultdict(int)
        for lab in labels:
            counts[lab] += 1
        majority_label[fam] = max(counts.items(), key=lambda kv: kv[1])[0] if counts else ""
    mc_total = mc_n = 0
    for r in results:
        t = tasks_by_id.get(r["task_id"])
        if t is None or t.expected is None:
            continue
        mc_total += 1
        if r.get("valid") and argmax_like(r.get("probs", {}), majority_label.get(t.family, "")):
            mc_n += 1
    mc_acc = (mc_n / mc_total) if mc_total else None

    # Brier / ECE / MAE
    briers = [
        r["brier"]
        for r in results
        if r.get("brier") is not None
    ]
    ece_pairs = [r["ece_pair"] for r in results if r.get("ece_pair")]
    mae_pairs = [r["mae_pair"] for r in results if r.get("mae_pair")]

    ece = ece_top_label(ece_pairs) if ece_pairs else {"ece": None, "n": 0, "bins": []}

    # Latency — populated by runner, attached to each result if available.
    latencies = [r.get("latency_s") for r in results if r.get("latency_s") is not None]
    lat = latency_summary(latencies)

    # Cost — populated by runner. Coerce defensively so a stray string from
    # an older run can't break float arithmetic.
    def _coerce_cost(v):
        if v is None:
            return 0.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    cost_total = sum(_coerce_cost(r.get("cost_usd")) for r in results)

    # Paraphrase consistency.
    res_by_id = {r["task_id"]: r for r in results}
    para = paraphrase_consistency(res_by_id, tasks_by_id)

    return {
        "n_tasks": n_tasks,
        "n_scorable": n_scorable,
        "schema_validity": (n_valid / n_tasks) if n_tasks else None,
        "schema_validity_strict": (n_strict / n_tasks) if n_tasks else None,
        "accuracy": accuracy,
        "majority_class_accuracy": mc_acc,
        "brier": (sum(briers) / len(briers)) if briers else None,
        "ece": ece["ece"],
        "ece_bins": ece["bins"],
        "ordinal_mae": ordinal_mae(mae_pairs),
        "p50_s": lat["p50_s"],
        "p95_s": lat["p95_s"],
        "cost_usd_total": cost_total if cost_total else None,
        "paraphrase_consistency": para,
        "per_family": per_family,
    }


def argmax_like(probs: dict, label: str) -> bool:
    """Helper: True if `label` has the highest prob. Used for majority-class baseline."""
    if not probs or not label:
        return False
    top = max(probs.values())
    return probs.get(label, -1.0) >= top and probs.get(label, 0.0) == top


# ──────────────────────────────────────────────────────────────────────
# JevBench Score — composite (v1.3 style) per upstream JevBench README
# ──────────────────────────────────────────────────────────────────────
#
#   JevBench Score = geometric_mean( Intelligence, Calibration, Speed, Cost )
#   each axis in 0-100, then a soft-weight penalty for low Intelligence:
#     when Intelligence < 50, multiply the score by (Intelligence / 50)².
#
# Axis definitions:
#   Intelligence  — chance-corrected accuracy:
#                     (accuracy - chance) / (1 - chance), clipped at 0, * 100
#                   where chance = 1 / max_label_size observed in the dataset.
#   Calibration   — derived from ECE:  100 - 100 * ECE
#                   (ECE is in [0,1]; this maps ECE=0 → 100, ECE≥1 → 0).
#   Speed         — log10 scale on p50: 100 - 20 * log10(s / 0.1s)
#                   → 0.1s = 100, 1s = 80, 10s = 0 (clamped at 0).
#   Cost          — log10 scale on $/1k decisions:
#                   100 - 30 * log10($ / $0.001), clamped at 0
#                   → $0.001 = 100, $0.01 = 70, $0.10 = 40, $1 = 10.
#
# A null on any axis yields a null composite (no synthesis).

def _clip(v, lo, hi):
    if v is None:
        return None
    return max(lo, min(hi, v))


def intelligence_score(accuracy: float | None, chance: float | None) -> float | None:
    if accuracy is None or chance is None or chance >= 1:
        return None
    return _clip((accuracy - chance) / (1.0 - chance) * 100.0, 0.0, 100.0)


def calibration_score(ece: float | None) -> float | None:
    if ece is None:
        return None
    return _clip(100.0 - 100.0 * max(0.0, float(ece)), 0.0, 100.0)


def speed_score(p50_s: float | None) -> float | None:
    if p50_s is None or p50_s <= 0:
        return None
    return _clip(100.0 - 20.0 * math.log10(float(p50_s) / 0.1), 0.0, 100.0)


def cost_score(cost_per_1k_decisions_usd: float | None) -> float | None:
    if cost_per_1k_decisions_usd is None or cost_per_1k_decisions_usd <= 0:
        return None
    return _clip(100.0 - 30.0 * math.log10(float(cost_per_1k_decisions_usd) / 0.001), 0.0, 100.0)


def geometric_mean(values: list[float]) -> float | None:
    vs = [v for v in values if v is not None]
    if not vs or any(v <= 0 for v in vs):
        return None
    return (math.prod(vs)) ** (1.0 / len(vs))


def jevbench_score(
    *,
    accuracy: float | None,
    n_scorable: int,
    label_set_size_max: int,
    ece: float | None,
    p50_s: float | None,
    cost_usd_total: float | None,
    n_tasks: int,
) -> dict:
    """Compute the 4-axis JevBench Score and a single composite in 0-100.

    Inputs come straight from the public summary. Returns a dict with
    axes + composite + the chance / cost-per-1k / low-Intelligence flag.
    A null axis propagates as null in the composite (no synthesis).
    """
    chance = (1.0 / label_set_size_max) if label_set_size_max > 1 else None
    intel = intelligence_score(accuracy, chance)
    cal = calibration_score(ece)
    spd = speed_score(p50_s)
    cost_per_1k = (
        (cost_usd_total / n_tasks * 1000.0)
        if (cost_usd_total is not None and n_tasks)
        else None
    )
    cst = cost_score(cost_per_1k)

    axes = {
        "intelligence": intel,
        "calibration": cal,
        "speed": spd,
        "cost": cst,
    }
    composite = geometric_mean(list(axes.values()))
    penalty_applied = False
    if composite is not None and intel is not None and intel < 50.0:
        composite = composite * (intel / 50.0) ** 2
        penalty_applied = True

    return {
        "axes": axes,
        "chance_baseline": chance,
        "cost_usd_per_1k": cost_per_1k,
        "intelligence_penalty_applied": penalty_applied,
        "n_scorable": n_scorable,
        "label_set_size_max": label_set_size_max,
        "score": composite,
    }