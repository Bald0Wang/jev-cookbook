#!/usr/bin/env python3
"""Materialize the v2 planned train/dev/calibration/test splits without approving labels."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


EXPECTED = {"train": 1200, "dev": 200, "calibration": 100, "test": 400}
PSEUDO_SOURCES = {"deepseek_pseudo_label", "deepseek_flash_independent_vote_proxy"}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_questions(record, line_no):
    for q in record.get("qs", []):
        if q.get("t") == "choice":
            k = len(q.get("crit") or {})
        elif q.get("t") == "score":
            k = len(q.get("crit") or [])
        elif q.get("t") == "noul":
            k = 2
        else:
            raise ValueError("第 %d 行包含未知题型" % line_no)
        y, soft = q.get("y"), q.get("soft")
        if not isinstance(y, int) or not 0 <= y < k:
            raise ValueError("第 %d 行标签索引越界" % line_no)
        if not isinstance(soft, list) or len(soft) != k or any(float(x) < 0 for x in soft):
            raise ValueError("第 %d 行 soft target 长度或取值无效" % line_no)
        if abs(sum(map(float, soft)) - 1.0) > 1e-5:
            raise ValueError("第 %d 行 soft target 未归一化" % line_no)


def main():
    parser = argparse.ArgumentParser(description="按 v2 planned_split 导出训练与独立评估数据")
    parser.add_argument("--input", required=True, help="v2/laya_candidates.jsonl")
    parser.add_argument("--output-dir", required=True, help="新目录；不会覆盖已有文件")
    args = parser.parse_args()
    input_path = Path(args.input)
    out_dir = Path(args.output_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        parser.error("输出目录非空，请使用新目录: %s" % out_dir)

    records = []
    counts = Counter()
    ids, groups = set(), {}
    with input_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit("第 %d 行 JSON 无效: %s" % (line_no, exc))
            metadata = row.get("metadata") or {}
            split = metadata.get("planned_split")
            if row.get("split") != "train_candidate" or metadata.get("review_status") != "needs_human_review":
                raise SystemExit("第 %d 行不是预期的 v2 待审核候选" % line_no)
            if split not in EXPECTED or metadata.get("label_source") not in PSEUDO_SOURCES:
                raise SystemExit("第 %d 行缺少认可的 planned_split / 伪标签来源" % line_no)
            if row.get("id") in ids or not row.get("id"):
                raise SystemExit("第 %d 行 id 缺失或重复" % line_no)
            group_id = row.get("source_group_id")
            if not group_id or group_id in groups:
                raise SystemExit("第 %d 行 source_group_id 缺失或重复" % line_no)
            ids.add(row["id"])
            groups[group_id] = split
            validate_questions(row, line_no)
            row["split"] = split
            records.append(row)
            counts[split] += 1

    if dict(counts) != EXPECTED:
        raise SystemExit("planned_split 数量不符: got=%s expected=%s" % (dict(counts), EXPECTED))
    if sum(len(row["qs"]) for row in records) != 9500:
        raise SystemExit("决策题总数不符，拒绝导出")

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    outputs = {
        "train-dev.jsonl": [r for r in records if r["split"] in ("train", "dev")],
        "calibration.jsonl": [r for r in records if r["split"] == "calibration"],
        "test.jsonl": [r for r in records if r["split"] == "test"],
    }
    for filename, selected in outputs.items():
        output = out_dir / filename
        with output.open("w", encoding="utf-8", newline="\n") as f:
            for row in selected:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        files[output.name] = {"records": len(selected), "sha256": sha256(output)}

    manifest = {
        "source": str(input_path),
        "source_sha256": sha256(input_path),
        "records": len(records),
        "questions": 9500,
        "planned_split_counts": dict(counts),
        "review_status": "needs_human_review",
        "label_source": "DeepSeek independent vote proxy; not human gold or calibrated probability",
        "files": files,
        "note": "This export preserves review_status and only materializes planned splits. Use explicit --allow-unreviewed-pseudolabels for a research run; do not treat this as human approval.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
