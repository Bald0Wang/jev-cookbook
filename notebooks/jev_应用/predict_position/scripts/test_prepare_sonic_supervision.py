#!/usr/bin/env python3
"""Offline source, split and action-target contracts for Sonic PP preparation."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

import prepare_sonic_supervision as prepare
from test_unified_training import FakeTokenizer, record
from train_unified_games import (prepare_unified_examples, population_weights,
                                 validate_sampling_pools, target_for, objective_for)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def observation(ammo, terminal=False):
    return {"task": "shooting", "state": prepare.encode({
        "scenario": "predict_position", "screen_size": [320, 240], "terminal": terminal,
        "observed_history": [{"ammo": ammo, "visible_labels": []}], "remaining_ticks": 8}),
        "candidates": {} if terminal else {k: k + " for 4 Doom ticks." for k in ("left", "right", "shoot", "noop")},
        "remaining_steps": 0 if terminal else 2}


def episode(case, policy_id, success=False):
    probs = {"left": .1, "right": .2, "shoot": .6, "noop": .1}
    observations = [observation(1), observation(0), observation(0, True)]
    steps = []
    behavior = prepare.behavior_distribution(probs, "greedy", .1)
    for index in range(2):
        steps.append({"observation": observations[index],
            "request": prepare.policy_request(observations[index], case["id"]),
            "policy_probs": copy.deepcopy(probs), "policy_probs_raw": copy.deepcopy(probs),
            "raw_probability_sum": 1., "normalization_applied": False,
            "expert_argmax": "shoot", "action": "left",  # Exploration is NOT the label.
            "expert": {"probs": copy.deepcopy(probs), "argmax": "shoot",
                       "raw_logits": {k: math.log(p) for k, p in probs.items()}},
            "behavior_probs": behavior, "sampling_draw": .01,
            "pixel_input": {"sha256": "example-only"}, "mirror_tick_checks": [],
            "pre_action_ammo": 1 if index == 0 else 0,
            "next_observation_sha256": prepare.digest(observations[index + 1]),
            "terminated": index == 1, "truncated": False})
    return {"case": case, "continuation_policy_id": policy_id, "complete": True,
            "success": success, "steps": steps, "initial_observation": observations[0],
            "final_observation": observations[-1],
            "final_info": {"terminated": True, "truncated": False, "success": success},
            "standard_independent_replay": {"passed": True, "decisions": 2}}


def fixture(root):
    original, expert = root / "original", root / "expert"
    original.mkdir()
    expert.mkdir()
    original_rows, retained_bytes, cases = [], {}, []
    for split_index, split in enumerate(prepare.SPLITS):
        rows = []
        for task, suffix in (("maze", "maze"), ("snake", "snake"), ("shooting", "basic"), ("shooting", "pp")):
            row = record(task=task, split=split, suffix=suffix)
            if task == "shooting":
                row["metadata"]["spec"] = {"task": task, "scenario": "basic" if suffix == "basic" else "predict_position"}
            rows.append(row)
        original_rows.extend(rows)
        # Test both spacing and CRLF preservation, rather than equivalent JSON.
        lines = [(json.dumps(row, separators=(", ", ": ")) + "\r\n").encode() for row in rows]
        (original / (split + ".jsonl")).write_bytes(b"".join(lines))
        retained_bytes[split] = b"".join(lines[:-1])
        for j in range(2):
            cases.append({"id": f"{split}-pp-{j}", "split": split, "seed": 100 + split_index * 2 + j,
                "spec": {"task": "shooting", "scenario": "predict_position", "history_length": 4,
                         "frame_skip": 8 if split == "ood" else 4, "max_steps": 75}})
    write_json(original / "manifest.json", {"continuation_policy_id": None,
        "split_sha256": {s: prepare.file_sha256(original / (s + ".jsonl")) for s in prepare.SPLITS}})
    case_path = root / "cases.jsonl"
    case_path.write_text("".join(prepare.encode(c) + "\n" for c in cases))
    primary = {"checkpoint_repository": "fixture/sonic", "checkpoint_revision": "fixed",
               "checkpoint_sha256": "a" * 64, "controller": "greedy", "epsilon": .1, "sampling_seed": 17}
    protocol = {"schema_version": "nanojev-sonic-supervision-v1", "case_file": str(case_path),
                "case_sha256": prepare.file_sha256(case_path), "case_counts": {s: 2 for s in prepare.SPLITS},
                "primary": primary}
    protocol_path = root / "protocol.json"
    write_json(protocol_path, protocol)
    policy = {"engine": "sonic_doom_pure_vision_pp", "controller": "greedy", "epsilon": .1,
              "sampling_seed": 17, "model": {"model": primary["checkpoint_repository"],
                "revision": primary["checkpoint_revision"], "checkpoint_sha256": primary["checkpoint_sha256"]}}
    policy_id = prepare.digest(policy)
    episodes = [episode(case, policy_id, index % 2 == 0) for index, case in enumerate(cases)]
    (expert / "episodes.jsonl").write_text("".join(prepare.encode(e) + "\n" for e in episodes))
    collection = {"finished": True, "limit": 0, "cases_sha256": protocol["case_sha256"],
                  "config_sha256": prepare.file_sha256(protocol_path), "selected_cases": [c["id"] for c in cases],
                  "selected_cases_sha256": prepare.digest(cases), "episodes": len(cases),
                  "selected_episodes": len(cases), "selected_before_limit": len(cases),
                  "split_episodes": protocol["case_counts"], "split_records": {s: 4 for s in prepare.SPLITS},
                  "continuation_policy_id": policy_id, "policy": policy,
                  "episode_sha256": prepare.file_sha256(expert / "episodes.jsonl")}
    write_json(expert / "episodes.manifest.json", collection)
    return {"original": original, "expert": expert, "protocol_path": protocol_path,
            "protocol": protocol, "cases": cases, "collection": collection,
            "episodes": episodes, "retained_bytes": retained_bytes, "original_rows": original_rows}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.f = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def run_prepare(self):
        return prepare.prepare(self.f["original"], self.f["expert"], self.root / "output", self.f["protocol_path"])

    def test_only_preammo_filters_failure_kept_and_retained_bytes_exact(self):
        raw_before = (self.f["expert"] / "episodes.jsonl").read_bytes()
        report = self.run_prepare()
        self.assertEqual(raw_before, (self.f["expert"] / "episodes.jsonl").read_bytes())
        for split in prepare.SPLITS:
            audit = report["new_pp"][split]
            self.assertEqual((audit["raw_decisions"], audit["kept_decisions"], audit["filtered_no_ammo"]), (4, 2, 2))
            self.assertEqual((audit["kept_from_successes"], audit["kept_from_failures"]), (1, 1))
            for arm in ("hard", "soft"):
                content = (self.root / "output" / arm / (split + ".jsonl")).read_bytes()
                self.assertTrue(content.startswith(self.f["retained_bytes"][split]))
                new = [json.loads(line) for line in content.splitlines() if line.strip()][3:]
                self.assertTrue(all(r["metadata"]["decision_index"] == 0 for r in new))
                self.assertTrue(all(r["metadata"]["pre_action_ammo"] == 1 for r in new))

    def test_hard_and_soft_use_expert_not_exploration_and_keep_same_inputs(self):
        self.run_prepare()
        views = {}
        for arm in ("hard", "soft"):
            rows, _, _, _ = prepare.read_unified_dataset(self.root / "output" / arm)
            views[arm] = {r["id"]: r for r in rows if prepare.is_pp(r)}
        self.assertEqual(views["hard"].keys(), views["soft"].keys())
        for identity, hard in views["hard"].items():
            soft = views["soft"][identity]
            for field in ("id", "state_id", "state", "questions", "split", "gold"):
                self.assertEqual(hard[field], soft[field])
            self.assertEqual(hard["gold"]["action"], "shoot")
            self.assertEqual(hard["metadata"]["executed_action"], "left")
            self.assertNotIn("gold_probs", hard)
            self.assertEqual(soft["gold_probs"]["action"]["shoot"], .6)
            self.assertNotEqual(soft["gold_probs"]["action"], soft["metadata"]["behavior_probs"])
            examples, _ = prepare_unified_examples([hard, soft], FakeTokenizer(), 8192)
            self.assertEqual(dict(zip(examples[0]["candidate_ids"], target_for(examples[0], objective_for(examples[0])))),
                             {"left": 0., "right": 0., "shoot": 1., "noop": 0.})
            self.assertEqual(dict(zip(examples[1]["candidate_ids"], target_for(examples[1], objective_for(examples[1])))),
                             {"left": .1, "right": .2, "shoot": .6, "noop": .1})
            break

    def test_identical_visible_text_across_distinct_latent_splits_allowed(self):
        report = self.run_prepare()
        self.assertTrue(report["passed"])
        self.assertEqual(self.f["episodes"][0]["steps"][0]["observation"]["state"],
                         self.f["episodes"][-1]["steps"][0]["observation"]["state"])

    def test_group_alias_same_seed_different_split_rejected(self):
        path = Path(self.f["protocol"]["case_file"])
        cases = copy.deepcopy(self.f["cases"])
        cases[-1]["seed"] = cases[0]["seed"]
        path.write_text("".join(prepare.encode(c) + "\n" for c in cases))
        protocol = self.f["protocol"]
        protocol["case_sha256"] = prepare.file_sha256(path)
        write_json(self.f["protocol_path"], protocol)
        with self.assertRaisesRegex(ValueError, "unique PP"):
            self.run_prepare()

    def test_raw_modified_or_incomplete_cohort_rejected(self):
        path = self.f["expert"] / "episodes.jsonl"
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "episode file hash"):
            self.run_prepare()
        collection = self.f["collection"]
        collection["finished"] = False
        write_json(self.f["expert"] / "episodes.manifest.json", collection)
        with self.assertRaisesRegex(ValueError, "completed full"):
            self.run_prepare()
        self.assertFalse((self.root / "output").exists())

    def test_previously_used_pp_latent_group_cannot_enter_new_cohort(self):
        path = self.f["original"] / "train.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[-1]["metadata"]["source_group_id"] = prepare.environment_group(self.f["cases"][-1])
        path.write_text("".join(prepare.encode(r) + "\n" for r in rows))
        manifest_path = self.f["original"] / "manifest.json"
        manifest = prepare.read_json(manifest_path)
        manifest["split_sha256"]["train"] = prepare.file_sha256(path)
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "previous PP environment groups"):
            self.run_prepare()

    def test_retained_corpus_cannot_change_after_its_manifest(self):
        path = self.f["original"] / "train.jsonl"
        path.write_bytes(path.read_bytes().replace(b"intersection", b"crossroads"))
        with self.assertRaisesRegex(ValueError, "Original split hash"):
            self.run_prepare()

    def test_expert_target_receipt_and_public_request_tampering_rejected(self):
        original = self.f["episodes"][0]
        for field in ("expert_argmax", "request", "pre_action_ammo"):
            ep = copy.deepcopy(original)
            ep["steps"][0][field] = {"id": "fake"} if field == "request" else (0 if field == "pre_action_ammo" else "left")
            with self.assertRaises(ValueError):
                prepare.validate_episode(ep, self.f["cases"][0], self.f["collection"])

    def test_no_renormalizing_invalid_expert_distribution(self):
        ep = copy.deepcopy(self.f["episodes"][0])
        ep["steps"][0]["policy_probs"]["shoot"] = .8
        with self.assertRaisesRegex(ValueError, "simplex"):
            prepare.validate_episode(ep, self.f["cases"][0], self.f["collection"])

    def test_soft_distribution_must_still_match_original_logits(self):
        ep = copy.deepcopy(self.f["episodes"][0])
        ep["steps"][0]["expert"]["raw_logits"]["left"] += 2
        with self.assertRaisesRegex(ValueError, "logits"):
            prepare.validate_episode(ep, self.f["cases"][0], self.f["collection"])

    def test_model_identity_and_protocol_coverage_are_bound(self):
        collection = copy.deepcopy(self.f["collection"])
        collection["policy"]["model"]["checkpoint_sha256"] = "b" * 64
        collection["continuation_policy_id"] = prepare.digest(collection["policy"])
        with self.assertRaisesRegex(ValueError, "checkpoint identity"):
            prepare.validate_collection(collection, self.f["protocol"], self.f["cases"],
                                        prepare.file_sha256(self.f["protocol_path"]))
        collection = copy.deepcopy(self.f["collection"])
        collection["selected_cases"].pop()
        with self.assertRaisesRegex(ValueError, "missing registered"):
            prepare.validate_collection(collection, self.f["protocol"], self.f["cases"],
                                        prepare.file_sha256(self.f["protocol_path"]))

    def test_declared_equal_task_and_shooting_pool_weights(self):
        weights = json.loads(Path(__file__).parents[1].joinpath("configs/sonic_policy_pool_weights.json").read_text())
        population = population_weights("sft", policy_pool_weights=weights)
        self.assertAlmostEqual(sum(population.values()), 1.)
        self.assertEqual(population[("shooting", "policy", "basic")], 1/6)
        self.assertEqual(population[("shooting", "policy", "predict_position")], 1/6)
        self.run_prepare()
        rows, _, _, _ = prepare.read_unified_dataset(self.root / "output" / "hard")
        validate_sampling_pools(rows, population)


if __name__ == "__main__":
    unittest.main()
