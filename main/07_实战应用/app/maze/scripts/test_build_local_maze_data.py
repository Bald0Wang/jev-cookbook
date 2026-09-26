#!/usr/bin/env python3
"""Verify local input identity, geometric targets, split isolation and safe writes."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from build_local_maze_data import SPLITS, build_dataset, convert_record
from evaluate_composed_maze import render_local_request
from train_pipeline_decisions import read_training_records


def record(split="train", identifier=None, group=None):
    identifier = identifier or "snapshot-" + split
    state = {"game": "scaled_maze", "size": 8, "walls": [[0, 1]],
             "position": [0, 0], "goal": [7, 7], "seed": 987}
    return {"id": identifier, "state_id": identifier, "family_id": "scaled_maze", "split": split,
            "state": "OLD_FULL_MAP", "questions": {},
            "metadata": {"source_group_id": group or "map-" + split,
                         "environment_state": state, "oracle": {"distance": 14},
                         "unused_source_payload": "MUST_NOT_COPY"}}


def write_input(directory, rows=None):
    directory.mkdir()
    rows = rows if rows is not None else {split: [record(split)] for split in SPLITS}
    for split in SPLITS:
        (directory / (split + ".jsonl")).write_text(
            "".join(json.dumps(row) + "\n" for row in rows.get(split, [])), encoding="utf-8")


class LocalMazeDatasetTests(unittest.TestCase):
    def test_exact_renderer_boundary_truth_and_metadata_isolation(self):
        source = record()
        original = copy.deepcopy(source)
        result = convert_record(source)
        public = render_local_request(source["metadata"]["environment_state"], window_size=5)
        self.assertEqual({key: result[key] for key in ("state", "questions")}, public)
        self.assertEqual(result["gold"], {"clear_north": False, "clear_east": False,
                                          "clear_south": True, "clear_west": False})
        self.assertEqual(result["gold_probs"]["clear_south"], {"false": 0.0, "true": 1.0})
        self.assertEqual(result["metadata"]["environment_state"], source["metadata"]["environment_state"])
        self.assertNotIn("oracle", result["metadata"])
        self.assertNotIn("MUST_NOT_COPY", json.dumps(result))
        self.assertNotIn("OLD_FULL_MAP", result["state"])
        self.assertNotIn("goal", result["state"])
        self.assertEqual(source, original)
        result["metadata"]["environment_state"]["position"][0] = 6
        self.assertEqual(source, original)

    def test_at_goal_keeps_geometric_truth(self):
        source = record()
        source["metadata"]["environment_state"]["goal"] = [0, 0]
        self.assertTrue(convert_record(source)["gold"]["clear_south"])

    def test_five_splits_one_to_one_filter_and_training_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            input_dir, output_dir = Path(temp) / "input", Path(temp) / "output"
            rows = {split: [record(split)] for split in SPLITS}
            rows["train"].append({"split": "train", "metadata": {"environment_state": {"game": "snake"}}})
            write_input(input_dir, rows)
            manifest = build_dataset(input_dir, output_dir)
            actual, _ = read_training_records(output_dir)
            self.assertEqual(len(actual), 5)
            self.assertEqual(manifest["total_questions"], 20)
            self.assertEqual(manifest["labels"]["all"], {"true": 5, "false": 15, "total": 20,
                                                         "true_prevalence": 0.25})
            self.assertEqual(manifest["inputs"]["train"]["skipped_by_game"], {"snake": 1})
            for row in actual:
                source = rows[row["split"]][0]
                for key in ("id", "state_id", "family_id", "split"):
                    self.assertEqual(row[key], source[key])
                self.assertEqual(row["metadata"]["source_group_id"], source["metadata"]["source_group_id"])
                data = (output_dir / (row["split"] + ".jsonl")).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["outputs"][row["split"]]["sha256"])
            second_dir = Path(temp) / "second"
            self.assertEqual(build_dataset(input_dir, second_dir), manifest)
            for split in SPLITS:
                self.assertEqual((output_dir / (split + ".jsonl")).read_bytes(),
                                 (second_dir / (split + ".jsonl")).read_bytes())

    def test_cross_split_group_or_state_and_filename_mismatch_rejected_before_writes(self):
        for problem in ("group", "state", "split"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as temp:
                input_dir, output_dir = Path(temp) / "input", Path(temp) / "output"
                rows = {split: [record(split)] for split in SPLITS}
                if problem == "group":
                    rows["dev"][0]["metadata"]["source_group_id"] = rows["train"][0]["metadata"]["source_group_id"]
                elif problem == "state":
                    rows["dev"][0]["state_id"] = rows["train"][0]["state_id"]
                else:
                    rows["dev"][0]["split"] = "train"
                write_input(input_dir, rows)
                with self.assertRaises(ValueError):
                    build_dataset(input_dir, output_dir)
                self.assertFalse(output_dir.exists())

    def test_existing_output_is_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "existing"
            output_dir.mkdir()
            sentinel = output_dir / "keep.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                build_dataset(Path(temp) / "missing_input", output_dir)
            self.assertEqual(sentinel.read_text(), "unchanged")


if __name__ == "__main__":
    unittest.main()
