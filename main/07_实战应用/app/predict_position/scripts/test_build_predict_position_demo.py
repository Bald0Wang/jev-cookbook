"""Contracts for genuine shot timing, per-tick RGB and unfiltered aggregates."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from build_predict_position_demo import (NANOJEV_SHA, PredictCapture, add_events,
    aggregate, choose_illustrations, digest, file_digest, load_recordings, render_episode)
from test_build_shooting_demo import Env, MemoryAtlas, episode


class PredictFrames(unittest.TestCase):
    def test_real_images_keep_every_counter_tick_and_odd_tick_shot(self):
        source = episode(terminal_image=True)
        system, audit, _ = render_episode(source, "nanojev", MemoryAtlas(), Env, PredictCapture)
        add_events(system)
        frames = system["frames"]
        self.assertEqual([f["tick"] for f in frames], [0, 1, 2, 3])
        self.assertEqual([f["image_tick"] for f in frames], [0, 1, 2, 3])
        self.assertEqual([f["shot"] for f in frames], [False, False, False, True])
        self.assertEqual(system["shot_ticks"], [3])
        self.assertEqual(system["first_shot_tick"], 3)
        self.assertEqual(system["events"][0], {"type": "shot", "tick": 3,
            "decision": 2, "ammo_before": 10., "ammo_after": 9.})
        self.assertEqual(system["events"][-1]["type"], "hit")
        self.assertEqual(audit["actual_rgb_images"], 4)
        self.assertEqual(audit["physical_ticks"], 3)
        self.assertEqual(len(Env.instances[-1].raw.calls), 3)

    def test_native_terminal_without_frame_holds_real_preceding_image(self):
        system, audit, _ = render_episode(episode(False), "jev", MemoryAtlas(), Env, PredictCapture)
        add_events(system)
        self.assertEqual([f["image_tick"] for f in system["frames"]], [0, 1, 2, 2])
        self.assertFalse(system["frames"][-1]["visual_state_available"])
        self.assertTrue(system["frames"][-1]["terminal"])
        self.assertEqual(system["events"][-1]["type"], "episode_end")
        self.assertEqual(audit["fallback_image_frames"], 1)

    def test_attack_without_ammo_change_is_not_a_projectile_launch(self):
        # The weapon can receive several attack commands before a real shot.
        system = {"total_ticks": 3, "ammo_consumed": 1, "success": False, "outcome": "miss",
            "frames": [{"tick": t, "decision": t, "action": "shoot", "ammo": 1 if t < 3 else 0,
                        "shot": t == 3} for t in range(4)]}
        add_events(system)
        self.assertEqual(system["shot_ticks"], [3])
        self.assertEqual(len(system["events"]), 2)

    def test_invented_shot_or_wrong_ammo_total_fails(self):
        original = {"total_ticks": 1, "ammo_consumed": 0, "success": False, "outcome": "miss",
            "frames": [{"tick": 0, "decision": 0, "ammo": 1, "shot": False},
                       {"tick": 1, "decision": 1, "ammo": 1, "shot": False}]}
        changed = copy.deepcopy(original); changed["frames"][1]["shot"] = True
        with self.assertRaises(ValueError): add_events(changed)
        changed = copy.deepcopy(original); changed["ammo_consumed"] = 1
        with self.assertRaises(ValueError): add_events(changed)


class SelectionAndSources(unittest.TestCase):
    def test_aggregate_covers_full_cohort_not_selected_illustrations(self):
        registry = {f"{split}-{i}": {"split": split, "spec": {"scenario": "predict_position"}}
                    for split in ("test", "ood") for i in range(128)}
        sources = {k: {cid: {"success": int(cid.split("-")[1]) < threshold} for cid in registry}
                   for k, threshold in (("jev", 11), ("nanojev", 27), ("base", 11))}
        summary = aggregate(sources, registry)
        self.assertEqual(summary["nanojev"]["test"], {"episodes": 128, "successes": 27, "success_rate": 27 / 128})
        self.assertEqual(summary["jev"]["ood"]["episodes"], 128)
        del registry["test-127"]
        with self.assertRaises(ValueError): aggregate(sources, registry)

    def test_selection_preserves_real_failures_and_checks_declared_outcomes(self):
        registry = {"a": {"split": "test", "spec": {"scenario": "predict_position"}}}
        sources = {k: {"a": {"success": v}} for k, v in (("jev", True), ("nanojev", False), ("base", True))}
        config = {"cases": [{"id": "a", "expected_success": {"jev": True, "nanojev": False, "base": True}}],
                  "default_case_id": "a", "selection_rule": "An actual NanoJev failure"}
        rows, selection = choose_illustrations(config, sources, registry)
        self.assertFalse(rows[0]["expected_success"]["nanojev"])
        self.assertTrue(selection["outcome_selected"])
        config["cases"][0]["expected_success"]["nanojev"] = True
        with self.assertRaises(ValueError): choose_illustrations(config, sources, registry)

    def fixture(self, root):
        source = episode()
        source["final_info"]["episode_metrics"]["success"] = source["success"]
        policy = {"engine": "checkpoint", "controller": "greedy", "epsilon": .1,
                  "sampling_seed": 17, "tie_break": "lexicographic_first",
                  "checkpoint_sha256": {"best.safetensors": NANOJEV_SHA},
                  "source_sha256": {"unified_doom_env.py": file_digest(Path(__file__).with_name("unified_doom_env.py"))}}
        source["continuation_policy_id"] = digest(policy)
        path = root / "episodes.jsonl"
        path.write_text(json.dumps(source) + "\n")
        snapshot = root / "episodes.sources"; snapshot.mkdir()
        (snapshot / "unified_doom_env.py").write_bytes(Path(__file__).with_name("unified_doom_env.py").read_bytes())
        manifest = {"schema_version": "nanojev-unified-episodes-v1", "finished": True,
                    "episode_sha256": file_digest(path), "cases_sha256": "registry-sha", "policy": policy,
                    "continuation_policy_id": digest(policy), "selected_cases": [source["case"]["id"]],
                    "source_snapshot": "episodes.sources"}
        path.with_suffix(".manifest.json").write_text(json.dumps(manifest))
        return path, source, manifest, {source["case"]["id"]: source["case"]}

    def test_sources_bind_model_case_registry_episode_and_environment_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path, source, manifest, registry = self.fixture(Path(td))
            rows, provenance = load_recordings(path, "nanojev", registry, "registry-sha")
            self.assertEqual(rows[source["case"]["id"]], source)
            self.assertEqual(provenance["source_episode_count"], 1)
            with self.assertRaises(ValueError): load_recordings(path, "nanojev", registry, "other-registry")
            path.write_text(path.read_text() + "\n")
            with self.assertRaises(ValueError): load_recordings(path, "nanojev", registry, "registry-sha")

    def test_changed_archived_environment_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path, _, _, registry = self.fixture(Path(td))
            (path.parent / "episodes.sources/unified_doom_env.py").write_text("different environment")
            with self.assertRaises(ValueError): load_recordings(path, "nanojev", registry, "registry-sha")

    def test_false_success_cannot_enter_full_cohort_summary(self):
        with tempfile.TemporaryDirectory() as td:
            path, source, manifest, registry = self.fixture(Path(td))
            source["success"] = False
            path.write_text(json.dumps(source) + "\n")
            manifest["episode_sha256"] = file_digest(path)
            path.with_suffix(".manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): load_recordings(path, "nanojev", registry, "registry-sha")


if __name__ == "__main__":
    unittest.main()
