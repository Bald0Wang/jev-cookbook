"""Subject topics (datasets/topics.json) and the per-topic aggregates agree with the published per-task artifact."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = json.loads((ROOT / "datasets/topics.json").read_text())
RES = json.loads((ROOT / "results/v1.2/jevbench-v1.2-topics.json").read_text())
PT = json.loads((ROOT / "results/v1.2/jevbench-v1.2-per-task.json").read_text())
KEYS = [t["key"] for t in DS["topics"]]


def test_every_public_item_has_one_topic_from_the_fixed_list():
    public = {t["id"] for t in PT["tasks"] if t["public"]}
    assert set(DS["public"]) == public
    assert set(DS["public"].values()) <= set(KEYS)
    assert 6 <= len(KEYS) <= 9


def test_counts_add_up_and_every_topic_has_at_least_15_items():
    assert sum(DS["n_items"].values()) == 534
    for k in KEYS:
        assert DS["n_items"][k] >= 15
        assert sum(DS["n_items_by_tier"][k].values()) == DS["n_items"][k]
        public = sum(1 for v in DS["public"].values() if v == k)
        assert public + sum(DS["heldout_or_imported_counts"][k].values()) == DS["n_items"][k]
    for tier, c in PT["task_counts"].items():
        assert sum(DS["n_items_by_tier"][k][tier] for k in KEYS) == c["public"] + c["heldout_or_imported"]


def test_aggregates_match_the_per_task_artifact():
    assert set(RES["systems"]) == set(PT["systems"])
    for key, s in RES["systems"].items():
        pt = PT["systems"][key]
        # totals over topics = totals over tiers
        assert sum(t["correct"] for t in s["topics"].values()) == sum(v["c"] for v in pt["by_tier"].values())
        assert sum(t["n"] - t["attempted"] for t in s["topics"].values()) == sum(v["n"] for v in pt["by_tier"].values())
        for k, t in s["topics"].items():
            assert t["n"] == DS["n_items"][k]
            assert t["accuracy"] is None if not t["attempted"] else abs(t["accuracy"] - t["correct"] / t["attempted"]) < 1e-4
            # public outcomes are a subset of each topic's aggregate
            pub = [pt["public_tasks"][i][0] for i, v in DS["public"].items() if v == k]
            assert sum(c == "c" for c in pub) <= t["correct"] and sum(c != "n" for c in pub) <= t["attempted"]


def test_no_heldout_ids_are_published():
    assert all(not i.startswith(("heldout", "router-", "legacy-")) for i in DS["public"])
