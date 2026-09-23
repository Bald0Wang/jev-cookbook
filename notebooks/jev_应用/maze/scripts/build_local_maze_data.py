#!/usr/bin/env python3
"""Convert frozen maze snapshots to local geometric questions without resampling.

Example:
  python scripts/build_local_maze_data.py \
    --input data/scaled_games_v4b/policy --output data/local_maze_v4

Only the five split files are read. Existing split, record/state identifiers and
map source groups are retained. Full geometry is metadata, never model input.
The evaluator owns the shared renderer and question wording. No API is used.
"""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

from evaluate_composed_maze import local_questions, local_truth, render_local_request
from predict_toy_decisions import reject_nonfinite, unique_object
from scaled_maze import DIRECTIONS
from train_pipeline_decisions import SPLITS, validate_training_row


FORMAT_VERSION = "local_maze_geometry_v1"
WINDOW_SIZE = 5


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def convert_record(source):
    """Return one local record, preserving snapshot identity and source grouping."""
    metadata = source["metadata"]
    group = metadata.get("source_group_id")
    if not isinstance(group, str) or not group.strip():
        raise ValueError("Maze source_group_id must be a nonempty string")
    state = metadata["environment_state"]
    public = render_local_request(state, window_size=WINDOW_SIZE)
    truth = local_truth(public)
    # Independently check the local parser against one-step full-map geometry.
    # Do not use valid_actions: at-goal states still have geometric neighbors.
    row, col = state["position"]
    walls = set(map(tuple, state["walls"]))
    for action, (dr, dc) in DIRECTIONS.items():
        dest = (row + dr, col + dc)
        expected = (0 <= dest[0] < state["size"] and 0 <= dest[1] < state["size"]
                    and dest not in walls)
        if truth[action] is not expected:
            raise ValueError("Local renderer truth conflicts with geometric truth")
    gold = {"clear_" + action: value for action, value in truth.items()}
    result = {
        **{key: source[key] for key in ("id", "state_id", "family_id", "split")},
        **public,
        "gold": gold,
        "gold_probs": {qid: {"false": float(not value), "true": float(value)}
                       for qid, value in gold.items()},
        "gold_probs_kind": {qid: "deterministic_truth" for qid in gold},
        "gold_label_kind": {qid: "deterministic_truth" for qid in gold},
        "metadata": {
            "source": "self_authored_programmatic",
            "format_version": FORMAT_VERSION,
            "source_group_id": group,
            "split_assignment": metadata.get("split_assignment", "preserved_input_split"),
            "source_record_id": source["id"],
            "source_state_id": source["state_id"],
            "environment_state": copy.deepcopy(state),
            "window_size": WINDOW_SIZE,
            "renderer": "evaluate_composed_maze.render_local_request",
            "target_semantics": "deterministic_one_step_geometric_truth",
            "model_input_fields": ["state", "questions"],
            "resampled": False,
        },
    }
    validate_training_row(result)
    return result


def label_counts(rows):
    def summarize(values):
        counts = Counter(values)
        total = counts[True] + counts[False]
        return {"true": counts[True], "false": counts[False], "total": total,
                "true_prevalence": counts[True] / total if total else None}
    return {
        "all": summarize(value for row in rows for value in row["gold"].values()),
        "by_question": {qid: summarize(row["gold"][qid] for row in rows)
                        for qid in local_questions()},
    }


def build_dataset(input_dir, output_dir):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Refusing to overwrite output: {output_dir}")
    if not input_dir.is_dir():
        raise ValueError("--input must be a directory containing all five split files")
    converted = {split: [] for split in SPLITS}
    inputs, ids, state_splits, group_splits = {}, set(), {}, {}
    for split in SPLITS:
        filename = input_dir / f"{split}.jsonl"
        data = filename.read_bytes()
        input_count, skipped = 0, Counter()
        for lineno, line in enumerate(data.decode("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line, object_pairs_hook=unique_object, parse_constant=reject_nonfinite)
                if not isinstance(row, dict) or row.get("split") != split:
                    raise ValueError("Row split must match the split filename")
                input_count += 1
                game = row.get("metadata", {}).get("environment_state", {}).get("game")
                if game != "scaled_maze":
                    skipped[str(game)] += 1
                    continue
                result = convert_record(row)
                if result["id"] in ids:
                    raise ValueError("Duplicate maze record ID")
                ids.add(result["id"])
                for key, registry in ((result["state_id"], state_splits),
                                      (result["metadata"]["source_group_id"], group_splits)):
                    if key in registry and registry[key] != split:
                        raise ValueError("A maze state/source group crosses splits")
                    registry[key] = split
                converted[split].append(result)
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                raise ValueError(f"{filename.name}:{lineno}: {exc}") from exc
        inputs[split] = {"path": str(filename), "sha256": sha256(data), "rows": input_count,
                         "skipped_by_game": dict(sorted(skipped.items()))}
    if not ids:
        raise ValueError("No maze snapshots found")
    outputs, payloads = {}, {}
    for split, rows in converted.items():
        payload = b"".join(encode(row) + b"\n" for row in rows)
        payloads[split] = payload
        outputs[split] = {
            "path": f"{split}.jsonl", "sha256": sha256(payload), "bytes": len(payload),
            "rows": len(rows), "questions": 4 * len(rows),
            "source_groups": len({row["metadata"]["source_group_id"] for row in rows}),
            "labels": label_counts(rows),
        }
    code_dir = Path(__file__).resolve().parent
    manifest = {
        "format_version": FORMAT_VERSION,
        "window_size": WINDOW_SIZE,
        "inputs": inputs,
        "outputs": outputs,
        "total_rows": len(ids), "total_questions": 4 * len(ids),
        "labels": label_counts([row for rows in converted.values() for row in rows]),
        "source_sha256": {name: sha256((code_dir / name).read_bytes()) for name in
                          (Path(__file__).name, "evaluate_composed_maze.py", "scaled_maze.py")},
        "checks": {"one_output_per_maze_snapshot": True, "source_groups_preserved": True,
                   "split_assignments_preserved": True, "cross_split_source_groups": 0,
                   "cross_split_state_ids": 0, "local_and_geometric_truth_agree": True,
                   "training_schema_valid": True, "resampling": False, "api_calls": 0},
        "model_input_fields": ["state", "questions"],
        "scope": "Four local Boolean geometry questions per existing maze snapshot; no navigation policy labels.",
    }
    # All validation precedes output creation. mkdir itself refuses a racing writer.
    output_dir.mkdir(parents=True, exist_ok=False)
    for split, payload in payloads.items():
        with (output_dir / f"{split}.jsonl").open("xb") as handle:
            handle.write(payload)
    with (output_dir / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=Path("data/scaled_games_v4b/policy"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_dataset(args.input, args.output)
    print(json.dumps({"output": str(args.output), "rows": manifest["total_rows"],
                      "questions": manifest["total_questions"],
                      "split_rows": {split: value["rows"] for split, value in manifest["outputs"].items()}},
                     indent=2))


if __name__ == "__main__":
    main()
