import math

import pytest

from jevbench.composite_v12 import (PRESETS, TIER_WEIGHTS, adjusted_latency, calibration, cost, intelligence,
                                    jevbench_score, preset_score, speed, speed_point, tvd)


def test_weights_sum_to_one():
    assert abs(sum(TIER_WEIGHTS.values()) - 1) < 1e-12
    assert TIER_WEIGHTS["hard"] == 0.30
    assert abs(TIER_WEIGHTS["standard"] - 2 * TIER_WEIGHTS["easy"]) < 1e-12 and TIER_WEIGHTS["judge"] == TIER_WEIGHTS["standard"]
    for w in PRESETS.values():
        assert abs(sum(w) - 1) < 1e-9


def test_intelligence():
    assert intelligence({"easy": 1, "standard": 1, "judge": 1, "hard": 0}) == pytest.approx(70.0)
    # a tier a partial run never reached is left out, the rest renormalised
    assert intelligence({"easy": 1, "standard": 1, "judge": 1, "hard": None}) == pytest.approx(100.0)


def test_speed_scale_and_adjustment():
    assert speed_point(0.1) == 100 and speed_point(1.0) == pytest.approx(80) and speed_point(10) == pytest.approx(60)
    assert speed_point(0.01) == 100
    assert adjusted_latency(0.5, "api") == 0.5
    assert adjusted_latency(0.5, "demo") == pytest.approx(1.0)
    assert adjusted_latency(0.5, "gpu") == pytest.approx(1.15)
    assert adjusted_latency(0.5, "cpu") == pytest.approx(1.15)
    assert speed(1.0, 1.0, "api") == pytest.approx(80)


def test_cost_scale_and_no_free_pass():
    assert cost(0.001) == 100 and cost(0.01) == pytest.approx(70) and cost(1) == pytest.approx(10)
    with pytest.raises(ValueError):
        cost(None)


def test_calibration_and_tvd():
    assert calibration(0.0) == 100.0 and calibration(0.5) == 0.0 and calibration(0.9) == 0.0
    assert calibration(0.1, 0.2) == (80.0 + 80.0) / 2
    assert calibration(None) is None
    assert tvd({"a": 1.0}, {"a": 0.6, "b": 0.4}, ["a", "b"]) == 0.4


def test_geometric_mean():
    assert jevbench_score({"intelligence": 80, "calibration": 80, "speed": 80, "cost": 80}) == pytest.approx(80)
    s = jevbench_score({"intelligence": 90, "calibration": 90, "speed": 90, "cost": 10})
    assert s == pytest.approx(math.exp((3 * math.log(90) + math.log(10)) / 4)) and s < 70  # a weak axis pulls hard
    assert jevbench_score({"intelligence": 90, "calibration": None, "speed": 90, "cost": 90}) == pytest.approx(90 ** 0.75)
    assert preset_score({"intelligence": 50, "calibration": 0, "speed": 100, "cost": 100}, PRESETS["Intelligence only"]) == pytest.approx(50)


def test_score_lab_reference_rows():
    """Jev 1.13 and SemIf as the Score Lab computed them on 19 Sep 2026: 75.3 and 74.6.

    A fixed historical check of the formula, with the prices as published that day. The v1.2.3 cost correction
    (20 Sep 2026) moved those two prices to $0.039914 and $0.022445, which lifts the scores to 75.4 and 74.7;
    the live figures are checked against the artifact in tests/test_cost_correction.py.
    """
    jev = dict(intelligence=intelligence({"easy": 1.0, "standard": 0.9895833333333334, "judge": 0.9452054794520548, "hard": 0.740909090909091}),
               calibration=82.6528888888889, speed=speed(0.6524335257709026, 0.7221905551850795, "api"), cost=cost(0.04061412193840432))
    semif = dict(intelligence=intelligence({"easy": 1.0, "standard": 0.9791666666666666, "judge": 0.952054794520548, "hard": 0.5954545454545455}),
                 calibration=72.60139737235289, speed=speed(0.19796114787459373, 0.3153164997696876, "gpu"), cost=cost(0.022975040619190038))
    assert round(jevbench_score(jev), 1) == 75.3
    assert round(jevbench_score(semif), 1) == 74.6
