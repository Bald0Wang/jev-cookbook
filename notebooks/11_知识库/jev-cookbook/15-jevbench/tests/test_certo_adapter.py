from jevbench.adapters import CertoLocalAdapter
from jevbench.tasks import Task


def task(qtype, criteria, labels):
    return Task(id="t", family="f", state="The item state.", labels=labels,
                expected=labels[0], split="public",
                question={"type": qtype, "instructions": "Decide this.", "criteria": criteria})


def test_certo_choice_mapping_is_fixed_and_does_not_send_answer():
    row = CertoLocalAdapter.build_request(task("choice", {"a": "Alpha", "b": "Beta"}, ["a", "b"]))
    assert row == {"state": "Decide this.\n\nThe item state.",
                   "options": [{"id": "a", "description": "Alpha"},
                               {"id": "b", "description": "Beta"}]}


def test_certo_noul_and_score_mapping():
    row = CertoLocalAdapter.build_request(task("noul", {"true": "T", "false": "F"}, ["no", "yes"]))
    assert row["options"] == [{"id": "no", "description": "F"}, {"id": "yes", "description": "T"}]
    row = CertoLocalAdapter.build_request(task("score", ["low", "mid", "high"], ["0", "1", "2"]))
    assert row["options"][2] == {"id": "2", "description": "high"}
