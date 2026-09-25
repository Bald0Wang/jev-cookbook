"""Canonical task record. Mirrors the JevBench discipline:
   one dataclass, validate refuses to leak the expected value into the state,
   dataset_hash is order-independent so reorder != edit."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

# Keys that must NEVER appear inside a task's state.
# Shipping the answer inside the question is the classic accident.
_FORBIDDEN_STATE_KEYS = {"expected", "label", "ground_truth", "answer_key"}


@dataclass
class Task:
    id: str
    family: str  # routing | adequacy | policy | intent | ordinal | extraction
    question_type: str  # noul | choice | score
    instructions: str
    state: dict = field(default_factory=dict)
    labels: list = field(default_factory=list)  # exact, ordered
    expected: Optional[str] = None
    criteria: Optional[str] = None
    split: str = "public"  # public | heldout
    group: Optional[str] = None  # paraphrase group id, if any
    provenance: str = ""
    topic: str = ""  # math | coding | rules_law | finance | support_ops | everyday | safety_security

    def validate(self) -> None:
        if not self.labels:
            raise ValueError(f"task {self.id!r}: empty labels")
        if self.expected is not None and self.expected not in self.labels:
            raise ValueError(
                f"task {self.id!r}: expected {self.expected!r} not in labels {self.labels!r}"
            )
        for bad in _FORBIDDEN_STATE_KEYS:
            if bad in self.state:
                raise ValueError(
                    f"task {self.id!r}: state carries forbidden key {bad!r}"
                )
        if self.question_type == "score":
            try:
                _ = [int(x) for x in self.labels]
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"task {self.id!r}: score labels must be int-castable: {e}"
                )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=d["id"],
            family=d["family"],
            question_type=d["question_type"],
            instructions=d["instructions"],
            state=d.get("state", {}) or {},
            labels=list(d["labels"]),
            expected=d.get("expected"),
            criteria=d.get("criteria"),
            split=d.get("split", "public"),
            group=d.get("group"),
            provenance=d.get("provenance", ""),
            topic=d.get("topic", ""),
        )


def load_tasks(path: str) -> list[Task]:
    """Read JSONL tasks. Empty lines skipped; every record validated."""
    out: list[Task] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            t = Task.from_dict(d)
            t.validate()
            out.append(t)
    return out


def dataset_hash(tasks: list[Task]) -> str:
    """Order-independent hash. A reordered file is the same dataset; an edited one is not."""
    h = hashlib.sha256()
    for t in sorted(tasks, key=lambda x: x.id):
        h.update(json.dumps(t.to_dict(), sort_keys=True, ensure_ascii=False).encode())
        h.update(b"\n")
    return h.hexdigest()