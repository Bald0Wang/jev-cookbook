"""djev adapter: Jev's typed questions map 1:1 onto djev's documented request and answers."""
from jevbench.adapters import DjevAdapter
from jevbench.adapters import djev as D
from jevbench.tasks import Task


def _task(qtype, criteria, labels):
    return Task(id="t1", family="f", state={"a": 1}, labels=labels, expected=labels[0], split="public",
                question={"type": qtype, "instructions": "Q?", "criteria": criteria})


def _run(monkeypatch, task, answer):
    sent = {}

    def fake_post(url, body, headers, timeout):
        sent.update(url=url, body=body, headers=headers)
        return 200, {"model": "djev-0.1", "answers": {"decision": answer}, "usage": {"input_tokens": 100, "output_tokens": 8}}, 0.2

    monkeypatch.setattr(D, "http_post_json", fake_post)
    monkeypatch.setenv("DJEV_API_KEY", "test-key")
    return DjevAdapter().run(task), sent


def test_request_is_the_documented_shape(monkeypatch):
    r, sent = _run(monkeypatch, _task("noul", {"true": "T", "false": "F"}, ["no", "yes"]), {"type": "noul", "noul": 0.8})
    assert sent["url"] == "https://api.djev.dev/v1/request"
    assert sent["body"] == {"model": "djev", "state": {"a": 1},
                            "questions": {"decision": {"type": "noul", "instructions": "Q?", "criteria": {"true": "T", "false": "F"}}}}
    assert sent["headers"]["Prefer"] == "low-latency" and "options" not in sent["body"]
    assert r.ok and r.probs["yes"] == 0.8 and abs(r.probs["no"] - 0.2) < 1e-9


def test_choice_and_score_use_djev_probabilities(monkeypatch):
    r, _ = _run(monkeypatch, _task("choice", {"a": "A", "b": "B"}, ["a", "b"]),
                {"type": "choice", "choice": "b", "probabilities": {"a": 0.3, "b": 0.7}, "confidence": 0.1})
    assert r.ok and r.probs == {"a": 0.3, "b": 0.7}
    r, _ = _run(monkeypatch, _task("score", ["lo", "hi"], ["0", "1"]),
                {"type": "score", "score": 0.9, "probabilities": {"0": 0.1, "1": 0.9}, "legend": {"0": "lo", "1": "hi"}, "confidence": 0.5})
    assert r.ok and r.probs == {"0": 0.1, "1": 0.9}


def test_choice_outside_the_options_is_a_failure(monkeypatch):
    r, _ = _run(monkeypatch, _task("choice", {"a": "A", "b": "B"}, ["a", "b"]),
                {"type": "choice", "choice": "z", "probabilities": {"a": 0.5, "b": 0.5}, "confidence": 0.0})
    assert not r.ok
