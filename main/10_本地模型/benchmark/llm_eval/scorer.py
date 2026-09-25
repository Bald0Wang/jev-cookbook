"""Distribution validation, argmax and ordinal scoring.

All scoring is deterministic and pure. Malformed distributions fail
closed: they are invalid and count as incorrect; callers must NOT
invent calibration.
"""
from __future__ import annotations

import math
from typing import Optional

SUM_TOL = 1e-3
RENORM_TOL = 2e-2  # headline tolerance; strict tolerance is the frozen 1e-3


class InvalidDistribution(ValueError):
    pass


def validate_probs(
    probs: dict, labels: list, sum_tol: float = SUM_TOL
) -> dict:
    """Validate a probability map against the exact label set.

    Keys must match labels exactly. Values must be finite floats in
    [0, 1] and sum to 1 within sum_tol. Returns a sanitized copy.
    """
    if not isinstance(probs, dict):
        raise InvalidDistribution("probs is not a dict")
    want = set(labels)
    got = set(probs.keys())
    if got != want:
        raise InvalidDistribution(
            f"label keys mismatch: missing={sorted(want - got)} extra={sorted(got - want)}"
        )
    out: dict = {}
    total = 0.0
    for k, v in probs.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise InvalidDistribution(f"prob[{k!r}] is not a number: {v!r}")
        f = float(v)
        if not math.isfinite(f):
            raise InvalidDistribution(f"prob[{k!r}] is not finite")
        if f < 0.0 or f > 1.0:
            raise InvalidDistribution(f"prob[{k!r}] out of [0,1]: {f}")
        out[str(k)] = f
        total += f
    if abs(total - 1.0) > sum_tol:
        raise InvalidDistribution(f"probs sum to {total}, tolerance {sum_tol}")
    return out


def maybe_renormalize(probs: dict, labels: list, tol: float = RENORM_TOL) -> tuple[dict, bool]:
    """If the sum is within tol of 1.0, rescale; else return (probs, False).

    Refuses silently filling missing labels with 0 — keys must already match.
    """
    if set(probs.keys()) != set(labels):
        return probs, False
    total = sum(probs.get(k, 0.0) for k in labels)
    if abs(total - 1.0) <= tol:
        out = {k: probs.get(k, 0.0) / total for k in labels}
        return out, True
    return probs, False


def argmax_label(probs: dict) -> str:
    """Deterministic argmax: ties broken by lexicographically smallest label."""
    best, best_p = None, -1.0
    for k in sorted(probs.keys()):
        if probs[k] > best_p:
            best, best_p = k, probs[k]
    return best


def expected_value_ordinal(probs: dict) -> Optional[float]:
    """Probability-weighted expected level over integer-string keys."""
    try:
        return sum(float(k) * v for k, v in probs.items())
    except (TypeError, ValueError):
        return None


def top_label_confidence(probs: dict) -> float:
    return max(probs.values()) if probs else 0.0


def score_distribution(probs: dict, task, source: str = "unknown") -> dict:
    """Score one (possibly malformed) distribution against a canonical task.

    Returns a dict with keys: valid, strict_valid, correct, correct_value,
    brier, ece_pair, mae_pair. Missing metric = None.
    """
    out = {
        "valid": False,
        "strict_valid": False,
        "correct": None,
        "correct_value": None,
        "brier": None,
        "ece_pair": None,
        "mae_pair": None,
        "source": source,
    }
    # Try strict validation first.
    try:
        strict = validate_probs(probs, task.labels, sum_tol=SUM_TOL)
        out["strict_valid"] = True
    except InvalidDistribution:
        # Maybe a rounded distribution. Try renorm.
        renorm, ok = maybe_renormalize(probs, task.labels, tol=RENORM_TOL)
        if not ok:
            return out
        try:
            strict = validate_probs(renorm, task.labels, sum_tol=SUM_TOL)
        except InvalidDistribution:
            return out
        out["valid"] = True
        probs = strict
    else:
        out["valid"] = True
        probs = strict

    pred = argmax_label(probs)
    if task.expected is None:
        out["correct_value"] = None
    else:
        out["correct_value"] = (pred == task.expected)

    if task.question_type == "score" and task.expected is not None:
        ev = expected_value_ordinal(probs)
        if ev is not None and task.expected.isdigit():
            out["mae_pair"] = (float(task.expected), ev)

    # Brier (multi-class sum; binary 2-class convention).
    if task.expected is not None:
        out["brier"] = _brier(probs, task.expected, task.labels)
        conf = top_label_confidence(probs)
        correct = 1 if out["correct_value"] else 0
        out["ece_pair"] = (conf, correct)

    return out


def _brier(probs: dict, expected_label: str, labels: list) -> float:
    if len(labels) == 2 and expected_label in labels:
        p_yes = probs[expected_label]
        p_no = probs[labels[0] if labels[1] == expected_label else labels[1]]
        return (p_yes - 1.0) ** 2 + (p_no - 0.0) ** 2
    return sum((float(probs.get(lab, 0.0)) - (1.0 if lab == expected_label else 0.0)) ** 2 for lab in labels)