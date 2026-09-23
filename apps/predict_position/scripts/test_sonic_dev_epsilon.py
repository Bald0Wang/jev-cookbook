"""Offline guards for the separate development-only controller diagnostic."""
import copy
import unittest
from evaluate_sonic_dev_epsilon import collect, require_dev, validate
from test_sonic_predict_data import FakeEnvironment, FakePolicy


class DevDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "dev-sonic_predict_position-9300512", "seed": 9300512,
            "split": "dev", "variant": "doom_predict_position", "spec": {
                "task": "shooting", "scenario": "predict_position", "frame_skip": 4,
                "max_steps": 75, "history_length": 4}}

    def test_reject_other_splits_and_cadences(self):
        for split in ("train", "calibration", "test", "ood"):
            changed = copy.deepcopy(self.case)
            changed["split"] = split
            with self.assertRaises(ValueError):
                require_dev(changed)
        changed = copy.deepcopy(self.case)
        changed["spec"]["frame_skip"] = 8
        with self.assertRaises(ValueError):
            require_dev(changed)

    def test_fixed_epsilon_and_rng_replay(self):
        episode = collect(self.case, FakePolicy(), "diagnostic", "unused", FakeEnvironment)
        validate(episode, .1)
        self.assertEqual(episode["steps"][0]["behavior_probs"],
                         {"left": .025, "noop": .025, "right": .025, "shoot": .925})
        with self.assertRaises(ValueError):
            validate(episode, 0)
        changed = copy.deepcopy(episode)
        changed["steps"][0]["sampling_draw"] = .999
        with self.assertRaises(ValueError):
            validate(changed, .1)


if __name__ == "__main__":
    unittest.main()
