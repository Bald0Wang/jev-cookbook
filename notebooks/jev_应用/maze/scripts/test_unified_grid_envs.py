"""Contract and simulator-boundary tests; run with unittest discovery."""

import copy
import json
import unittest
from unittest.mock import patch

import snake_game
from unified_grid_envs import BITS, DIRECTIONS, UnifiedMazeEnv, UnifiedSnakeEnv


def maze_state(size=8, position=(1, 1), goal=(7, 7), walls=()):
    return {"game": "scaled_maze", "size": size, "position": list(position),
            "goal": list(goal), "walls": [list(cell) for cell in walls]}


def snake_state(size=4, body=None, direction="east", food=(0, 3), score=0):
    return {"game": "snake", "size": size, "seed": 17,
            "body": body or [[1, 1], [1, 0]], "direction": direction,
            "food": list(food), "rng_state": 432109876543210987,
            "done": False, "outcome": None, "score": score, "steps": 0}


def corridor_env(max_steps):
    opened = {(1, 1), (1, 2), (1, 3), (3, 3)}
    state = maze_state(5, (1, 1), (3, 3),
                       [(r, c) for r in range(5) for c in range(5) if (r, c) not in opened])
    return UnifiedMazeEnv({"task": "maze", "size": 5, "max_steps": max_steps,
                           "initial_state": state, "history_limit": 0})


CORRIDOR_ACTIONS = ["north", "south", "east", "north", "south", "east", "north", "east", "south"]


class UnifiedGridContractTests(unittest.TestCase):
    def assert_observation(self, obs, task):
        self.assertEqual(set(obs), {"task", "state", "candidates", "remaining_steps", "step"})
        self.assertEqual(obs["task"], task)
        self.assertIsInstance(obs["state"], str)
        self.assertTrue(all(isinstance(k, str) and isinstance(v, str) for k, v in obs["candidates"].items()))
        self.assertGreaterEqual(obs["remaining_steps"], 0)
        self.assertEqual(json.loads(json.dumps(obs)), obs)

    def test_sizes_and_deterministic_reset_and_transitions(self):
        for cls, task in ((UnifiedMazeEnv, "maze"), (UnifiedSnakeEnv, "snake")):
            for size in (8, 16, 50):
                with self.subTest(task=task, size=size):
                    a, b = [cls({"task": task, "size": size, "max_steps": 32}) for _ in range(2)]
                    first = a.reset(731)
                    self.assertEqual(first, b.reset(731))
                    obs, info = first
                    self.assert_observation(obs, task)
                    self.assertIsInstance(info["success"], bool)
                    for index in range(12):
                        if not obs["candidates"]:
                            break
                        action = list(obs["candidates"])[index % len(obs["candidates"])]
                        result = a.step(action)
                        self.assertEqual(result, b.step(action))
                        obs, reward, terminated, truncated, info = result
                        self.assert_observation(obs, task)
                        self.assertEqual(reward, float(info["success"]))
                        self.assertFalse(truncated)
                        self.assertEqual(terminated, info["terminated"])
                        json.dumps(result, allow_nan=False)
                    self.assertEqual(first, a.reset(731))

    def test_invalid_actions_do_not_advance_and_close(self):
        for cls, task in ((UnifiedMazeEnv, "maze"), (UnifiedSnakeEnv, "snake")):
            env = cls({"task": task, "size": 8})
            with self.assertRaises(RuntimeError):
                env.step("north")
            original = env.reset(4)
            for invalid in ("teleport", None, [], True):
                with self.assertRaises(ValueError):
                    env.step(invalid)
                self.assertEqual(original, (env._observe(), env._info([])))
            env.close()
            env.close()
            with self.assertRaises(RuntimeError):
                env.reset(4)
            with self.assertRaises(RuntimeError):
                env.step("north")

    def test_invalid_specs_and_seed(self):
        for cls, task in ((UnifiedMazeEnv, "maze"), (UnifiedSnakeEnv, "snake")):
            for field, value in (("size", True), ("max_steps", 0), ("history_limit", -1)):
                with self.assertRaises(ValueError):
                    cls({"task": task, field: value})
            with self.assertRaises(ValueError):
                cls({"task": task}).reset(True)
        with self.assertRaises(ValueError):
            UnifiedSnakeEnv({"task": "snake", "target_food": 0})

    def test_returns_and_spec_are_detached(self):
        spec = {"task": "maze", "size": 8, "initial_state": maze_state()}
        env = UnifiedMazeEnv(spec)
        spec["initial_state"]["walls"].append([0, 1])
        obs, info = env.reset(7)
        obs["candidates"].clear()
        info["episode_metrics"]["physical_steps"] = 999
        result = env.step("east")
        self.assertEqual(result[0]["step"], 1)
        result[4]["physical_events"][0]["next_position"][0] = 999
        self.assertNotIn("999", env._observe()["state"])
        self.assertEqual(env._world["walls"], [])


class UnifiedMazeTests(unittest.TestCase):
    def test_risky_candidates_and_deadline(self):
        env = UnifiedMazeEnv({"task": "maze", "size": 8, "max_steps": 1,
                              "initial_state": maze_state(position=(0, 0), walls=[(0, 1)])})
        obs, _ = env.reset(0)
        self.assertEqual(list(obs["candidates"]), list(DIRECTIONS))
        obs, reward, terminated, truncated, info = env.step("north")
        self.assertEqual((reward, terminated, truncated), (0, True, False))
        self.assertEqual(obs["candidates"], {})
        self.assertEqual(obs["remaining_steps"], 0)
        self.assertEqual(info["outcome"], "deadline")
        self.assertEqual(info["episode_metrics"]["collisions"], 1)
        self.assertEqual(info["physical_events"][0]["collision_reason"], "boundary")
        with self.assertRaises(RuntimeError):
            env.step("east")

    def test_goal_on_last_step_and_initial_goal(self):
        env = UnifiedMazeEnv({"task": "maze", "size": 8, "max_steps": 1,
                              "initial_state": maze_state(goal=(1, 2))})
        env.reset(0)
        obs, reward, terminated, truncated, info = env.step("east")
        self.assertEqual((reward, terminated, truncated), (1, True, False))
        self.assertTrue(info["success"])
        self.assertEqual(info["outcome"], "goal_reached")
        self.assertFalse(obs["candidates"])
        initial = UnifiedMazeEnv({"task": "maze", "size": 8,
                                  "initial_state": maze_state(goal=(1, 1))})
        obs, info = initial.reset(0)
        self.assertTrue(info["success"])
        self.assertEqual(obs["step"], 0)
        self.assertFalse(obs["candidates"])

    def test_macro_uses_known_edges_and_charges_physical_budget(self):
        for budget, expected_steps, expected_macro, expected_position, terminal in (
                (10, 10, 1, [1, 2], True), (20, 11, 2, [1, 1], False)):
            with self.subTest(budget=budget):
                env = corridor_env(budget)
                env.reset(0)
                for action in CORRIDOR_ACTIONS:
                    result = env.step(action)
                obs, reward, terminated, truncated, info = result
                self.assertEqual(obs["step"], expected_steps)
                self.assertEqual(info["macro_physical_steps"], expected_macro)
                self.assertEqual(info["physical_steps_this_action"], 1 + expected_macro)
                self.assertEqual(info["episode_metrics"]["decision_steps"], 9)
                self.assertEqual(info["episode_metrics"]["reposition_steps"], expected_macro)
                self.assertEqual(env._world["position"], expected_position)
                self.assertEqual((reward, terminated, truncated), (0, terminal, False))
                for event in info["physical_events"][1:]:
                    self.assertEqual(event["actor"], "verified_edge_reposition")
                    self.assertFalse(event["collision"])
                    self.assertEqual(event["action"], "west")
                if not terminal:
                    self.assertEqual(list(obs["candidates"]), ["west"])
                    end = env.step("west")
                    self.assertEqual(end[4]["outcome"], "frontier_exhausted")
                    self.assertTrue(end[2])
                    self.assertEqual(end[0]["candidates"], {})

    def test_complete_memory_can_reconstruct_every_observed_edge(self):
        env = corridor_env(20)
        env.reset(0)
        for action in CORRIDOR_ACTIONS:
            env.step(action)
        observed = {}
        for line in env._memory_rows().splitlines():
            row_text, encoded = line.split(":")
            row, col = int(row_text), 0
            for run in encoded.split(","):
                code, *repeat = run.split("x")
                count = int(repeat[0]) if repeat else 1
                tried, opened = int(code[0], 16), int(code[1], 16)
                self.assertEqual(opened & ~tried, 0)
                for _ in range(count):
                    for action, bit in BITS.items():
                        if tried & bit:
                            observed[((row, col), action)] = "open" if opened & bit else "blocked"
                    col += 1
            self.assertEqual(col, env.size)
        self.assertEqual(observed, env._edges)
        self.assertIn(env._memory_rows(), env._observe()["state"])
        self.assertEqual(env.history_limit, 0)

    def test_observation_hides_remote_geometry_and_no_oracle_called(self):
        one = maze_state(position=(3, 3))
        two = copy.deepcopy(one)
        two["walls"] = [[7, 0]]
        two["secret_oracle"] = "NOT_PUBLIC_9183"
        with patch("scaled_maze.solve", side_effect=AssertionError("No oracle")):
            a, b = [UnifiedMazeEnv({"task": "maze", "size": 8, "initial_state": state}) for state in (one, two)]
            self.assertEqual(a.reset(11), b.reset(984))
            self.assertEqual(a.step("east"), b.step("east"))
            self.assertNotIn("NOT_PUBLIC_9183", a._observe()["state"])


class UnifiedSnakeTests(unittest.TestCase):
    def environment(self, state, **options):
        return UnifiedSnakeEnv({"task": "snake", "size": state["size"],
                                "initial_state": state, **options})

    def test_target_last_step_and_reset_relative_food(self):
        env = self.environment(snake_state(food=(1, 2), score=5), target_food=1, max_steps=1)
        obs, _ = env.reset(0)
        self.assertEqual(set(obs["candidates"]), {"north", "east", "south"})
        original = copy.deepcopy(env._world)
        with self.assertRaises(ValueError):
            env.step("west")
        self.assertEqual(original, env._world)
        obs, reward, terminated, truncated, info = env.step("east")
        self.assertEqual((reward, terminated, truncated), (1, True, False))
        self.assertEqual(info["outcome"], "target_food_reached")
        self.assertEqual(info["episode_metrics"]["food_collected"], 1)
        self.assertEqual(info["episode_metrics"]["score"], 6)
        self.assertEqual(info["episode_metrics"]["survival_steps"], 1)
        self.assertEqual(obs["candidates"], {})
        with self.assertRaises(RuntimeError):
            env.step("east")

    def test_deadline_without_collision_is_failure(self):
        env = self.environment(snake_state(), max_steps=1)
        env.reset(0)
        obs, reward, terminated, truncated, info = env.step("east")
        self.assertEqual((reward, terminated, truncated), (0, True, False))
        self.assertEqual(info["outcome"], "deadline")
        self.assertEqual(info["episode_metrics"]["survival_steps"], 1)
        self.assertFalse(obs["candidates"])

    def test_wall_and_body_collisions_remain_candidates(self):
        fixtures = [
            (snake_state(body=[[0, 1], [0, 0]]), "wall_collision"),
            (snake_state(body=[[1, 1], [1, 0], [0, 0], [0, 1], [0, 2]], food=(3, 3)), "self_collision"),
        ]
        for state, outcome in fixtures:
            env = self.environment(state, max_steps=1)
            with patch("snake_game.one_step_safe", side_effect=AssertionError("No action filtering")):
                obs, _ = env.reset(0)
                self.assertIn("north", obs["candidates"])
                obs, reward, terminated, truncated, info = env.step("north")
            self.assertEqual((reward, terminated, truncated), (0, True, False))
            self.assertEqual(info["outcome"], outcome)
            self.assertEqual(info["episode_metrics"]["collisions"], 1)
            self.assertEqual(info["episode_metrics"]["survival_steps"], 0)

    def test_vacating_tail_is_enterable(self):
        env = self.environment(snake_state(body=[[1, 1], [1, 0], [2, 0], [2, 1]]))
        env.reset(0)
        _, _, terminated, _, info = env.step("south")
        self.assertFalse(terminated)
        self.assertEqual(env._world["body"][0], [2, 1])
        self.assertFalse(info["physical_events"][0]["collision"])

    def test_full_board_success_and_unmet_task_target(self):
        state = snake_state(2, [[0, 0], [1, 0], [1, 1]], "north", (0, 1))
        for target in (1, 2):
            env = self.environment(state, target_food=target)
            env.reset(0)
            obs, reward, terminated, truncated, info = env.step("east")
            self.assertTrue(terminated)
            self.assertFalse(truncated)
            self.assertEqual(reward, float(target == 1))
            self.assertTrue(info["episode_metrics"]["full_board_win"])
            self.assertEqual(info["success"], target == 1)
            self.assertEqual(obs["candidates"], {})

    def test_hidden_rng_is_not_rendered_but_snapshot_stream_preserved(self):
        one = snake_state(food=(1, 2))
        two = copy.deepcopy(one)
        two["seed"], two["rng_state"] = 876543210987654321, 123456789098765432
        a, b = self.environment(one, target_food=4), self.environment(two, target_food=4)
        self.assertEqual(a.reset(1), b.reset(2))
        for marker in ("rng", "seed", str(one["rng_state"]), str(two["rng_state"]), str(two["seed"])):
            self.assertNotIn(marker, a._observe()["state"].lower())
        expected = snake_game.step(one, "east")
        a.step("east")
        self.assertEqual(a._world, expected)
        fresh = self.environment(one, target_food=4)
        fresh.reset(999)
        self.assertEqual(fresh.step("east")[0], a._observe())


if __name__ == "__main__":
    unittest.main()
