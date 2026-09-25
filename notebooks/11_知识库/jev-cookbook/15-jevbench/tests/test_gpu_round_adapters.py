"""v1.1.3 GPU-round adapters: the question mappings, checked without a GPU."""
import json

from jevbench.adapters import RemoteInprocAdapter, SemIfDirectAdapter, So1DeciderAdapter
from jevbench.tasks import Task


def _task(qtype, criteria, labels, state="s"):
    return Task(id="t1", family="f", state=state, labels=labels, expected=labels[0], split="public",
                question={"type": qtype, "instructions": "Q?", "criteria": criteria})


def test_semif_noul_follows_author_true_false_order():
    row = SemIfDirectAdapter().build_request(_task("noul", {"true": "T", "false": "F"}, ["no", "yes"]))
    assert [o["id"] for o in row["options"]] == ["true", "false"]
    assert row["options"][0]["description"] == "true: T"


def test_semif_noul_default_text_and_choice_and_score():
    row = SemIfDirectAdapter().build_request(_task("noul", None, ["no", "yes"]))
    assert row["options"][1]["description"] == "false: The proposition is false."
    row = SemIfDirectAdapter().build_request(_task("choice", {"a": "A desc", "b": "B desc"}, ["a", "b"]))
    assert [o["description"] for o in row["options"]] == ["a: A desc", "b: B desc"]
    row = SemIfDirectAdapter().build_request(_task("score", ["low", "mid", "high"], ["0", "1", "2"]))
    assert [o["id"] for o in row["options"]] == ["0", "1", "2"] and row["options"][2]["description"] == "2: high"


def test_so1_uses_the_v11_space_mapping():
    a = So1DeciderAdapter()
    body = a._space.build_request(_task("noul", {"true": "T", "false": "F"}, ["no", "yes"]))
    assert body["labels"] == ["no", "yes"]
    assert body["fields"][0] == "Q?\nRubric: " + json.dumps({"no": "F", "yes": "T"})


def test_remote_client_never_sends_the_answer():
    sent = {}

    def fake_post(url, body, headers, timeout):
        sent.update(body)
        return 200, {"ok": True, "probs": {"no": 0.2, "yes": 0.8}, "latency_s": 0.01}, 0.05

    import jevbench.adapters.remote_inproc as m
    orig, m.http_post_json = m.http_post_json, fake_post
    try:
        r = RemoteInprocAdapter(endpoint="http://x").run(_task("noul", None, ["no", "yes"]))
    finally:
        m.http_post_json = orig
    assert sent["task"]["expected"] is None and sent["task"]["provenance"] == {}
    assert r.ok and r.probs["yes"] == 0.8
