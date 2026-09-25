"""v1.2.7: the run-3 additions, and the rule that keeps an incomplete run out of the ranking.

The GLiNER2.5 rows are complete runs on our own machine. jqv is not: its endpoint is the submitter's own machine,
so the held-out hard items were never sent to it and the row must stay unranked with its coverage visible.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = json.loads((ROOT / "results/v1.2/jevbench-v1.2-results.json").read_text())
SYS = {s["key"]: s for s in ART["systems"]}
NEW_COMPLETE = ["gliner2.5-small", "gliner2.5-multi"]
N_HARD, N_PUBLIC_HARD = 220, 111


def test_the_new_rows_are_present_in_this_revision():
    assert tuple(map(int, ART["revision"].removeprefix("v").split("."))) >= (1, 2, 7)
    for key in [*NEW_COMPLETE, "jqv"]:
        assert key in SYS, key


def test_the_gliner25_rows_are_complete_and_ranked():
    for key in NEW_COMPLETE:
        s = SYS[key]
        assert s["listing"] == "ranked" and s["rank"], key
        assert not s["partial"], key
        assert s["hard"]["coverage"] == 1.0, key
        assert all(s["tiers"][t] is not None for t in ("easy", "standard", "judge", "hard")), key


def test_jqv_partial_row_was_replaced_by_a_complete_run_in_v128():
    # v1.2.7 showed jqv as a partial row (425 of 534, no held-out hard items sent to the submitter's machine).
    # v1.2.8 re-ran it on our own GPU from the now-public serving code, so the row is complete and ranked.
    s = SYS["jqv"]
    assert not s["partial"] and s["listing"] == "ranked" and s["rank"]
    assert s["hard"]["n_attempted"] == N_HARD and s["hard"]["coverage"] == 1.0
    assert s["endpoint_kind"] == "gpu"
    assert "replaces the v1.2.7 partial row" in ART["footnotes"]["jqv"]


def test_an_incomplete_run_can_never_carry_a_rank():
    for s in ART["systems"]:
        if s["partial"]:
            assert not s["rank"] and s["listing"] == "partial", s["key"]


def test_the_earlier_gliner2_row_did_not_move():
    assert round(SYS["gliner2"]["jevbench_score"], 1) == 53.0
    assert SYS["gliner2"]["tiers"]["hard"] == SYS["gliner2"]["hard"]["accuracy"]
