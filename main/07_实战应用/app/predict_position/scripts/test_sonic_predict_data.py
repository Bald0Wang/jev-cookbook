"""Small collector contract tests; optional Torch checks do not require weights."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest

from sonic_predict_data import (
    ACTIONS, collect_episode, digest, observed_ammo, probability_check,
    replay_standard, validate_cases, validate_episode, file_digest,
)


class FakePolicy:
    def __init__(self):
        self.forward_count = self.reset_count = 0

    def reset(self):
        self.reset_count += 1
        self.step = 0

    def predict(self, frame):
        logits = {k: float(k == "shoot") for k in ACTIONS}
        total = math.fsum(math.exp(v) for v in logits.values())
        raw = {k: math.exp(v) / total for k, v in logits.items()}
        mass = math.fsum(raw.values())
        result = {"logits": logits, "raw_probabilities": raw,
                  "probabilities": {k: v/mass for k, v in raw.items()},
                  "raw_probability_sum": mass,
                  "pixel_sha256": digest(frame), "resized_chw_sha256": digest(frame),
                  "normalized_input_sha256": digest(frame),
                  "rnn_before_sha256": digest(self.step), "rnn_after_sha256": digest(self.step+1)}
        self.step += 1
        self.forward_count += 1
        return result


class FakeEnvironment:
    def __init__(self, spec, old_game_wad=None):
        self.spec = spec
        self.step_index = 0
        self.closed = False

    def observation(self):
        terminal = self.step_index == 3
        state = {"scenario": "predict_position", "screen_size": [320, 240],
                 "observed_history": [{"ammo": 1 if self.step_index == 0 else 0}],
                 "terminal": terminal}
        return {"state": json.dumps(state), "task": "shooting", "step": self.step_index,
                "remaining_steps": 3-self.step_index,
                "candidates": {} if terminal else {k: k for k in ACTIONS}}

    def info(self):
        return {"terminated": self.step_index == 3, "truncated": False, "success": False,
                "actual_ticks": int(self.step_index > 0), "requested_ticks": 4,
                "episode_metrics": {"kills": 0, "physical_ticks": self.step_index}}

    def reset(self, seed):
        self.step_index = 0
        return self.observation(), self.info(), {"initial_physics": {"tick": 0}}

    def expert_frame(self):
        return self.step_index

    def step(self, action):
        before = {"tick": self.step_index}
        self.step_index += 1
        check = {"tick_index": self.step_index, "before_sha256": digest(before),
                 "after": {"tick": self.step_index}, "reward": -.001}
        return self.observation(), -.001, self.step_index == 3, False, self.info(), [check]

    def close(self):
        self.closed = True


class FakeStandard(FakeEnvironment):
    def reset(self, seed):
        return super().reset(seed)[:2]

    def step(self, action):
        return super().step(action)[:5]


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "unit-train-9300000", "seed": 9300000, "split": "train",
            "variant": "doom_predict_position", "spec": {"task": "shooting", "scenario": "predict_position",
            "frame_skip": 4, "max_steps": 75, "history_length": 4}}
        self.episode = collect_episode(self.case, FakePolicy(), "frozen", "unused", env_factory=FakeEnvironment)

    def test_full_failed_episode_includes_zero_ammo_states(self):
        self.assertEqual([s["pre_action_ammo"] for s in self.episode["steps"]], [1, 0, 0])
        self.assertFalse(self.episode["success"])
        self.assertTrue(replay_standard(self.episode, FakeStandard)["passed"])
        self.assertEqual(self.episode["inference_counts"]["actual_expert_forward_calls"], 3)

    def test_reject_modified_action_or_argmax(self):
        for field in ("action", "expert_argmax"):
            broken = copy.deepcopy(self.episode)
            broken["steps"][0][field] = "left"
            with self.assertRaises(ValueError):
                validate_episode(broken)

    def test_reject_missing_tick_or_broken_rnn(self):
        broken = copy.deepcopy(self.episode)
        broken["steps"][1]["mirror_tick_checks"] = []
        with self.assertRaises(ValueError):
            validate_episode(broken)
        broken = copy.deepcopy(self.episode)
        broken["steps"][1]["pixel_input"]["rnn_before_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            validate_episode(broken)

    def test_reject_reward_as_success(self):
        broken = copy.deepcopy(self.episode)
        broken["success"] = broken["final_info"]["success"] = True
        with self.assertRaises(ValueError):
            validate_episode(broken)

    def test_reject_nonfinite_or_inconsistent_probabilities(self):
        policy = FakePolicy()
        policy.reset()
        result = policy.predict(0)
        for name in ("logits", "probabilities", "raw_probabilities"):
            broken = copy.deepcopy(result)
            broken[name]["shoot"] = float("nan")
            with self.assertRaises(ValueError):
                probability_check(broken)
        result["logits"]["left"] = 100
        with self.assertRaises(ValueError):
            probability_check(result)

    def test_reject_nonstandard_observation_and_ammo_change(self):
        broken = copy.deepcopy(self.episode)
        broken["steps"][0]["pre_action_ammo"] = 9
        with self.assertRaises(ValueError):
            validate_episode(broken)
        obs = copy.deepcopy(self.episode["initial_observation"])
        state = json.loads(obs["state"])
        state["screen_size"] = [160, 120]
        obs["state"] = json.dumps(state)
        with self.assertRaises(ValueError):
            observed_ammo(obs)

    def test_registered_cohort_complete_and_disjoint(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "configs/sonic_predict_supervision_v1.json").read_text())
        path = root / config["case_file"]
        cases = [json.loads(line) for line in path.read_text().splitlines()]
        validate_cases(cases, config, file_digest(path))
        self.assertEqual(len(cases), 896)
        with self.assertRaises(ValueError):
            validate_cases(cases[:-1], config, file_digest(path))
        with self.assertRaises(ValueError):
            validate_cases(cases, config, "wrong")
        changed = copy.deepcopy(cases)
        changed[-1]["seed"] = changed[0]["seed"]
        with self.assertRaises(ValueError):
            validate_cases(changed, config, file_digest(path))


@unittest.skipUnless(importlib.util.find_spec("torch") and importlib.util.find_spec("numpy"), "Torch/NumPy optional")
class AdapterTests(unittest.TestCase):
    def test_nearest_pixels_and_recurrent_batch(self):
        import numpy as np
        import torch
        from sonic_predict_policy import VisionActor, resize_nearest
        frame = np.arange(120*160*3).reshape(120, 160, 3).astype(np.uint8)
        resized = resize_nearest(frame)
        self.assertEqual(resized.shape, (72, 128, 3))
        for row, column in ((0, 0), (71, 127), (13, 59)):
            self.assertTrue(np.array_equal(resized[row, column], frame[row*120//72, column*160//128]))
        torch.set_num_threads(1)
        model = VisionActor().eval()
        with torch.inference_mode():
            pixels = torch.zeros(2, 3, 72, 128, dtype=torch.uint8)
            logits, hidden, values, norm = model(pixels, torch.zeros(2, 512))
        self.assertEqual(tuple(logits.shape), (2, 4))
        self.assertEqual(tuple(hidden.shape), (2, 512))
        self.assertTrue(torch.isfinite(logits).all())


if __name__ == "__main__":
    unittest.main()
