"""One-shot: convert JevBench public JSONL into llm_eval format.

JevBench task record -> llm_eval.Task:
  question.type        -> question_type
  question.instructions-> instructions
  question.criteria    -> criteria
  state (str|dict)     -> state (dict; str wrapped as {"text": str})
  provenance (dict)    -> provenance (str)
  family / split / group / id / labels / expected: passthrough

Adds a 'topic' key when it can be inferred from id prefix; otherwise "".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


_TOPIC_HINTS = {
    "intent": "everyday",
    "routing": "support_ops",
    "policy": "rules_law",
    "extraction": "coding",
    "ordinal": "support_ops",
    "adequacy": "everyday",
    "score": "support_ops",
}


def convert(rec: dict) -> dict:
    q = rec.get("question", {})
    state = rec.get("state")
    if isinstance(state, str):
        state = {"text": state}
    elif state is None:
        state = {}
    prov = rec.get("provenance", "")
    if isinstance(prov, dict):
        prov = prov.get("source", "") or ""
    family = rec.get("family", "")
    topic = _TOPIC_HINTS.get(family, "")
    expected = rec.get("expected")
    labels = list(rec["labels"])
    # Normalize score-family expected to string so it matches string labels.
    if q.get("type") == "score" and expected is not None and not isinstance(expected, str):
        expected = str(expected)
    out = {
        "id": rec["id"],
        "family": family,
        "question_type": q.get("type", "choice"),
        "instructions": q.get("instructions", ""),
        "state": state,
        "labels": labels,
        "expected": expected,
        "criteria": q.get("criteria"),
        "split": rec.get("split", "public"),
        "group": rec.get("group"),
        "provenance": str(prov),
        "topic": topic,
    }
    return out


def main():
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    dst.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with src.open("r", encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out = convert(rec)
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")
            n += 1
    print(f"converted {n} records from {src} -> {dst}")


if __name__ == "__main__":
    main()