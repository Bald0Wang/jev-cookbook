"""v1.2.2 additions: the request mappings fixed in docs/v1.2-additions.md, without loading any model."""
import json

from jevbench.adapters import ClassifierDevAdapter, PawLocalAdapter
from jevbench.adapters import classifier_dev as CD
from jevbench.adapters import gliner2_local as G
from jevbench.adapters import paw_local as P
from jevbench.runner import Runner
from jevbench.budget import Ledger
from jevbench.tasks import Task


def _task(qtype, criteria, labels, state="hello"):
    return Task(id="t1", family="f", state=state, labels=labels, expected=labels[0], split="public",
                question={"type": qtype, "instructions": "Q?", "criteria": criteria})


def test_gliner2_labels_and_text():
    t = _task("choice", {"a": "Alpha", "b": None}, ["a", "b"], state={"x": 1})
    assert G.gliner2_labels(t) == {"a": "Alpha", "b": "b"}
    assert G.gliner2_text(t) == 'Question: Q?\n\n{"x": 1}'
    assert G.gliner2_labels(_task("noul", {"true": "T", "false": None}, ["no", "yes"])) == {"yes": "T", "no": "No"}
    assert G.gliner2_labels(_task("score", ["lo", "hi"], ["0", "1"])) == {"0": "lo", "1": "hi"}
    req = G.Gliner2LocalAdapter().build_request(t)
    assert (req["class_act"], req["multi_label"], req["cls_threshold"]) == ("softmax", True, 0.0)


def test_paw_spec_and_label_matching():
    t = _task("choice", {"refund": "money back", "keep": None}, ["refund", "keep"])
    assert P.paw_spec(t) == "Q?\n\nReturn ONLY one of: refund, keep.\n\nrefund: money back\nkeep: keep"
    assert P.match_label(' "Refund". ', t.labels) == "refund"
    assert P.match_label("refund because", t.labels) is None
    n = _task("noul", None, ["no", "yes"])
    assert P.paw_spec(n).splitlines()[2] == "Return ONLY one of: yes, no."


def test_paw_is_label_only_and_prepare_runs_before_the_clock(tmp_path, monkeypatch):
    t = _task("choice", {"a": "A", "b": "B"}, ["a", "b"])
    progs = tmp_path / "p.json"
    progs.write_text(json.dumps({P.spec_key(P.paw_spec(t)): {"id": "prog1"}}))
    a = PawLocalAdapter(endpoint=str(progs))
    calls = []
    monkeypatch.setattr(a, "prepare", lambda task: (calls.append("prepare"), a._fns.__setitem__("prog1", lambda s: (calls.append("fn"), "b")[1])))
    rec = Runner(a, Ledger(str(tmp_path / "l.jsonl"), cap_usd=1.0), raw_dir=str(tmp_path / "raw")).run_task(t)
    assert calls == ["prepare", "fn"] and "prepare_s" in rec
    assert rec["probs_source"] == "label_only_no_calibrated_distribution" and rec["predicted"] == "b" and rec["correct"] is False


def test_classifier_dev_request_and_score_mapping(monkeypatch):
    t = _task("score", ["not urgent", "blocking"], ["0", "1"], state={"k": "v"})
    sent = {}

    def fake_post(url, body, headers, timeout):
        sent.update(url=url, body=body)
        return 200, {"results": [{"label": "blocking", "confidence": 0.8, "scores": {"not urgent": 0.2, "blocking": 0.8},
                                  "model": "jev-1.13", "ms": 5}], "usage": {"classifications": 1}}, 0.3

    monkeypatch.setattr(CD, "http_post_json", fake_post)
    r = ClassifierDevAdapter().run(t)
    assert sent["url"] == "https://classifier.dev/v1/classify"
    assert sent["body"] == {"input": '{"k": "v"}', "labels": ["not urgent", "blocking"], "tier": "fast",
                            "instructions": "Q?\n\nLevels, lowest to highest:\n- not urgent\n- blocking"}
    assert r.ok and r.probs == {"0": 0.2, "1": 0.8}


def test_classifier_dev_choice_carries_the_rubric():
    t = _task("choice", {"billing": "invoices", "tech": None}, ["billing", "tech"])
    body = ClassifierDevAdapter().build_request(t)
    assert body["labels"] == ["billing", "tech"]
    assert body["instructions"] == "Q?\n\nOptions:\n- billing: invoices\n- tech: tech"
