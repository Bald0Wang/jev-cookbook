"""Standard-library adapter tests; add --real to run actual ViZDoom smoke tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from unified_doom_env import UnifiedDoomEnv


class _Pixels:
    def __eq__(self, value):
        return SimpleNamespace(any=lambda: value == 7)


class _State:
    labels_buffer = _Pixels()

    def __init__(self, seed):
        self.labels = [
            SimpleNamespace(value=7, object_id=2, object_name="Cacodemon",
                            x=seed % 100, y=80, width=40, height=45),
            SimpleNamespace(value=8, object_id=3, object_name="INVISIBLE_SENTINEL",
                            x=50, y=50, width=20, height=20),
        ]

    @property
    def objects(self):
        raise AssertionError("Hidden objects must not be inspected")

    @property
    def sectors(self):
        raise AssertionError("Full map geometry must not be inspected")


class FakeGame:
    def __init__(self, **options):
        self.options = options
        self.configured = {}
        self.calls = []
        self.seed = 0
        self.time = 14
        self.closed = False

    def __getattr__(self, name):
        if name.startswith("set_"):
            return lambda value: self.configured.__setitem__(name, value)
        raise AttributeError(name)

    def load_config(self, path):
        self.configured["load_config"] = path

    def set_seed(self, seed):
        self.seed = seed

    def init(self):
        self.new_episode()

    def new_episode(self):
        self.time = 14
        self.finished = False
        self.dead = False
        self.total = 0.0
        self.calls = []
        self.values = dict.fromkeys(UnifiedDoomEnv._VARIABLES, 0.0)
        self.values.update(HEALTH=100.0, SELECTED_WEAPON_AMMO=20.0, ANGLE=90.0,
                           KILLCOUNT=self.options.get("initial_kills", 0.0))

    def get_episode_timeout(self):
        return self.options.get("timeout", 300)

    def get_episode_time(self):
        return self.time

    def get_game_variable(self, name):
        return self.values[name]

    def get_state(self):
        return None if self.finished else _State(self.seed)

    def get_total_reward(self):
        return self.total

    def is_episode_finished(self):
        return self.finished

    def is_player_dead(self):
        return self.dead

    def is_episode_timeout_reached(self):
        return self.get_episode_timeout() > 0 and self.time >= self.get_episode_timeout()

    def make_action(self, action, tics):
        if self.finished:
            raise AssertionError("No action may follow a finished episode")
        actual = tics
        if self.get_episode_timeout():
            actual = min(actual, self.get_episode_timeout() - self.time)
        if self.options.get("early_stop"):
            actual = min(actual, self.options["early_stop"])
        self.calls.append((action, tics, actual))
        self.time += actual
        if action[2]:
            self.values["SELECTED_WEAPON_AMMO"] -= 1
        self.values["DAMAGECOUNT"] += self.options.get("damage", 0)
        self.values["DAMAGE_TAKEN"] += self.options.get("damage_taken", 0)
        if self.options.get("kill") and len(self.calls) >= self.options.get("kill_after_calls", 1):
            self.values["KILLCOUNT"] += 1
            self.finished = True
        elif self.options.get("dead"):
            self.values["HEALTH"] = 0
            self.dead = self.finished = True
        elif self.options.get("finish_without_kill"):
            self.finished = True
        elif self.is_episode_timeout_reached():
            self.finished = True
        if self.finished and self.options.get("reset_terminal_clock"):
            self.time = 0
        reward = self.options.get("reward", -float(actual))
        self.total += reward
        return reward

    def close(self):
        self.closed = True


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        for scenario in ("basic", "predict_position"):
            (root / f"{scenario}.cfg").write_text("test fixture", encoding="utf-8")
            (root / f"{scenario}.wad").write_bytes(b"test fixture")
        self.environments = []

    def tearDown(self):
        for env in self.environments:
            env.close()
        self.directory.cleanup()

    def env(self, spec=None, **options):
        game = FakeGame(**options)
        module = SimpleNamespace(
            __file__=str(Path(self.directory.name) / "__init__.py"),
            __version__="mock", scenarios_path=self.directory.name, DoomGame=lambda: game,
            Mode=SimpleNamespace(PLAYER="PLAYER"),
            ScreenResolution=SimpleNamespace(RES_320X240="RES_320X240"),
            ScreenFormat=SimpleNamespace(RGB24="RGB24"),
            Button=SimpleNamespace(**{name: name for name in (
                "MOVE_LEFT", "MOVE_RIGHT", "TURN_LEFT", "TURN_RIGHT", "ATTACK"
            )}),
            GameVariable=SimpleNamespace(**{name: name for name in UnifiedDoomEnv._VARIABLES}),
        )
        env = UnifiedDoomEnv(spec or {"task": "shooting", "max_steps": 4})
        self.environments.append(env)
        with patch("unified_doom_env._load_vizdoom", return_value=module):
            obs, info = env.reset(17)
        return env, game, obs, info

    def test_optional_dependency_is_loaded_only_on_reset(self):
        env = UnifiedDoomEnv({"max_steps": 1})
        with patch("unified_doom_env._load_vizdoom", side_effect=ImportError("optional")):
            with self.assertRaises(ImportError):
                env.reset(0)
        env.close()

    def test_visible_boundary_and_json_schema(self):
        env, game, obs, info = self.env()
        self.assertEqual(set(obs), {"task", "state", "candidates", "remaining_steps", "step"})
        self.assertEqual(list(obs["candidates"]), ["left", "right", "shoot", "noop"])
        self.assertIn("Cacodemon", obs["state"])
        self.assertNotIn("INVISIBLE_SENTINEL", obs["state"])
        self.assertNotIn("KILLCOUNT", obs["state"])
        self.assertFalse(game.configured["set_objects_info_enabled"])
        self.assertFalse(game.configured["set_sectors_info_enabled"])
        self.assertFalse(game.configured["set_automap_buffer_enabled"])
        self.assertFalse(game.configured["set_window_visible"])
        self.assertEqual(game.configured["set_mode"], "PLAYER")
        json.dumps((obs, info), allow_nan=False)

    def test_basic_and_predict_position_button_meanings(self):
        for scenario, button, wording in (
            ("basic", "MOVE_LEFT", "Strafe"), ("predict_position", "TURN_LEFT", "Turn")
        ):
            env, game, obs, _ = self.env({"scenario": scenario})
            self.assertEqual(game.configured["set_available_buttons"][0], button)
            self.assertIn(wording, obs["candidates"]["left"])
            env.step("left")
            self.assertEqual(game.calls[0][0], [True, False, False])

    def test_task_deadline_is_terminal_with_no_bootstrap(self):
        env, game, _, _ = self.env({"max_steps": 1}, reward=50.0)
        obs, reward, terminated, truncated, info = env.step("noop")
        self.assertEqual(reward, 200.0)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertFalse(info["success"])
        self.assertFalse(info["bootstrap_allowed"])
        self.assertEqual(info["terminal_reason"], "task_deadline")
        self.assertEqual(obs["candidates"], {})
        self.assertEqual(obs["remaining_steps"], 0)
        with self.assertRaises(RuntimeError):
            env.step("noop")

    def test_partial_final_action_at_native_timeout(self):
        env, game, _, _ = self.env({"max_steps": 99, "frame_skip": 4}, timeout=20)
        obs, _, done, _, _ = env.step("noop")
        self.assertFalse(done)
        self.assertIn("2 Doom ticks", obs["candidates"]["noop"])
        obs, _, done, truncated, info = env.step("noop")
        self.assertEqual([call[1] for call in game.calls], [1] * 6)
        self.assertEqual(info["requested_ticks"], 2)
        self.assertEqual(info["episode_metrics"]["physical_ticks"], 6)
        self.assertEqual(info["terminal_reason"], "native_timeout")
        self.assertTrue(done)
        self.assertFalse(truncated)

    def test_partial_final_action_at_explicit_tick_deadline(self):
        env, game, _, _ = self.env({"max_steps": 5, "frame_skip": 4, "max_ticks": 5})
        env.step("noop")
        _, _, done, _, info = env.step("noop")
        self.assertEqual([call[1] for call in game.calls], [1] * 5)
        self.assertEqual(info["requested_ticks"], 1)
        self.assertTrue(done)
        self.assertEqual(info["terminal_reason"], "task_deadline")

    def test_success_uses_kill_delta_even_when_reward_is_negative(self):
        env, _, _, _ = self.env(kill=True, kill_after_calls=2, reward=-10, initial_kills=5, damage=40)
        obs, reward, done, truncated, info = env.step("shoot")
        self.assertEqual(reward, -20)
        self.assertTrue(done and info["success"])
        self.assertFalse(truncated)
        self.assertEqual(info["episode_metrics"]["kills"], 1)
        self.assertEqual(info["episode_metrics"]["physical_ticks"], 2)
        self.assertEqual(info["episode_metrics"]["ammo_consumed"], 2)
        self.assertEqual(info["episode_metrics"]["damage_dealt"], 80)
        self.assertFalse(json.loads(obs["state"])["observed_history"][-1]["visual_state_available"])

    def test_positive_initial_killcount_and_positive_reward_are_not_success(self):
        env, _, _, _ = self.env(initial_kills=5, reward=100, finish_without_kill=True)
        _, _, done, _, info = env.step("noop")
        self.assertTrue(done)
        self.assertFalse(info["success"])
        self.assertEqual(info["terminal_reason"], "native_terminal_without_kill")

    def test_death_failure_is_recorded(self):
        env, _, _, _ = self.env(dead=True, damage_taken=100)
        _, _, done, _, info = env.step("noop")
        self.assertTrue(done)
        self.assertEqual(info["terminal_reason"], "player_dead")
        self.assertFalse(info["success"])
        self.assertEqual(info["episode_metrics"]["damage_taken"], 100)

    def test_terminal_clock_reset_does_not_erase_executed_tick(self):
        env, _, _, _ = self.env(finish_without_kill=True, reset_terminal_clock=True)
        _, _, done, _, info = env.step("noop")
        self.assertTrue(done)
        self.assertEqual(info["actual_ticks"], 1)
        self.assertEqual(info["episode_metrics"]["physical_ticks"], 1)
        self.assertEqual(info["native_episode_tick"], 0)
        self.assertEqual(info["native_clock_resets"], 1)

    def test_reset_seed_repeats_and_history_does_not_leak_between_episodes(self):
        env, _, initial, _ = self.env({"history_length": 2, "max_steps": 8})
        for _ in range(4):
            obs, *_ = env.step("noop")
        self.assertEqual(len(json.loads(obs["state"])["observed_history"]), 2)
        repeated, _ = env.reset(17)
        self.assertEqual(initial, repeated)
        changed, _ = env.reset(18)
        self.assertNotEqual(initial["state"], changed["state"])

    def test_invalid_specs_seeds_and_actions(self):
        for spec in ({"task": "snake"}, {"scenario": "deathmatch"}, {"max_steps": 0},
                     {"frame_skip": True}, {"history_length": 5}, {"max_ticks": -1}):
            with self.assertRaises(ValueError):
                UnifiedDoomEnv(spec)
        env, game, _, _ = self.env()
        for seed in (-1, 2**32, True, 1.5):
            with self.assertRaises(ValueError):
                env.reset(seed)
        for action in ("forward", 0, None):
            with self.assertRaises(ValueError):
                env.step(action)
        self.assertEqual(game.calls, [])

    def test_close_is_idempotent(self):
        env, game, _, _ = self.env()
        env.close()
        env.close()
        self.assertTrue(game.closed)
        with self.assertRaises(RuntimeError):
            env.step("noop")


def real_smoke():
    """No learning: reproducible fixed actions and native timeout on both maps."""
    reports = []
    for scenario in ("basic", "predict_position"):
        spec = {"task": "shooting", "scenario": scenario, "max_steps": 1000, "frame_skip": 4}
        with UnifiedDoomEnv(spec) as env:
            traces = []
            for _ in range(2):
                obs, reset_info = env.reset(17)
                trace = [obs]
                while obs["candidates"]:
                    obs, reward, done, truncated, info = env.step("noop")
                    assert not truncated
                    trace.append((obs, reward, done, info["actual_ticks"], info["episode_metrics"]))
                assert done and not info["success"]
                assert info["terminal_reason"] == "native_timeout"
                assert info["episode_metrics"]["physical_ticks"] <= reset_info["native_timeout_tick"]
                traces.append(trace)
            assert traces[0] == traces[1], f"Fixed-seed replay differs for {scenario}"
            reports.append({"scenario": scenario, "seed_replay_equal": True,
                            "version": reset_info["vizdoom_version"], **info["episode_metrics"]})
        with UnifiedDoomEnv({**spec, "max_ticks": 5}) as env:
            env.reset(17)
            first = env.step("noop")
            last = env.step("noop")
            assert first[4]["actual_ticks"] == 4 and last[4]["actual_ticks"] == 1
            assert last[2] and not last[3] and last[4]["terminal_reason"] == "task_deadline"
    # Exercise an actual kill, including the final partial action. This tiny
    # screen-box script verifies the adapter, not a learned policy benchmark.
    with UnifiedDoomEnv({"scenario": "basic", "max_steps": 1000, "frame_skip": 4}) as env:
        obs, _ = env.reset(17)
        while obs["candidates"]:
            visible = json.loads(obs["state"])["observed_history"][-1]["visible_labels"]
            monsters = [label for label in visible if label["name"] == "Cacodemon"]
            center = monsters[0]["bbox"][0] + monsters[0]["bbox"][2] / 2 if monsters else 160
            action = "shoot" if abs(center - 160) < 15 else ("left" if center < 160 else "right")
            obs, _, done, truncated, info = env.step(action)
        assert done and not truncated and info["success"]
        assert info["episode_metrics"]["kills"] == 1
        assert info["terminal_reason"] == "target_killed"
        reports.append({"scenario": "basic", "controller": "scripted_visible_bbox_smoke_only",
                        **info["episode_metrics"]})
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true", help="Also run installed ViZDoom, without learning")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AdapterTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.real:
        print(json.dumps({"real_smoke": real_smoke()}, indent=2, allow_nan=False))
