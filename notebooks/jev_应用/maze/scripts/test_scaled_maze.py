#!/usr/bin/env python3
"""Standard-library tests: python -m unittest discover -s scripts -p test_scaled_maze.py."""

import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scaled_maze as maze


def fixture(size, position, goal, opened):
    opened = set(opened)
    return {"game": "scaled_maze", "size": size,
            "walls": [[r, c] for r in range(size) for c in range(size) if (r, c) not in opened],
            "position": list(position), "goal": list(goal)}


class GenerationTests(unittest.TestCase):
    def test_all_curriculum_sizes_and_topologies(self):
        for size in maze.CURRICULUM_SIZES:
            for topology in maze.TOPOLOGIES:
                with self.subTest(size=size, topology=topology):
                    state = maze.make_maze(size, 812, topology)
                    self.assertEqual(state["size"], size)
                    self.assertNotEqual(state["position"], state["goal"])
                    oracle = maze.solve(state)
                    self.assertTrue(oracle["reachable"])
                    self.assertGreater(oracle["distance"], 0)
                    metrics = maze.difficulty_metrics(state)
                    self.assertEqual(metrics["connected_components"], 1)
                    if topology in {"corridor", "tree"}:
                        self.assertEqual(metrics["cycle_rank"], 0)
                    if topology == "loops":
                        self.assertGreater(metrics["cycle_rank"], 0)
                    self.assertEqual(json.loads(json.dumps(state)), state)

    def test_seed_reproducibility_and_independent_rng(self):
        import random
        for topology in maze.TOPOLOGIES:
            first = maze.make_maze(16, -17, topology)
            random.seed(995)
            random.random()
            self.assertEqual(first, maze.make_maze(16, -17, topology))
            self.assertNotEqual(first["walls"], maze.make_maze(16, -18, topology)["walls"])

    def test_invalid_generator_inputs(self):
        for size, seed, topology in ((True, 1, "tree"), (4, 1, "tree"), (8, True, "tree"),
                                     (8.0, 1, "tree"), (8, 1, "unknown")):
            with self.subTest(args=(size, seed, topology)), self.assertRaises(ValueError):
                maze.make_maze(size, seed, topology)

    def test_minimum_supported_generation_size(self):
        for topology in maze.TOPOLOGIES:
            state = maze.make_maze(5, 3, topology)
            self.assertGreater(maze.solve(state)["distance"], 0)


class GeometryTests(unittest.TestCase):
    def test_legal_step_and_no_input_mutation(self):
        state = fixture(3, (1, 1), (0, 2), [(1, 1), (0, 1), (0, 2), (1, 2)])
        original = copy.deepcopy(state)
        self.assertEqual(maze.valid_actions(state), ["north", "east"])
        nxt = maze.step(state, "east")
        self.assertEqual(nxt["position"], [1, 2])
        nxt["walls"].clear()
        self.assertEqual(state, original)
        for action in ("west", "south", "diagonal", 0, None, []):
            with self.subTest(action=action), self.assertRaises(ValueError):
                maze.step(state, action)

    def test_no_wrapping_and_terminal_stop(self):
        state = fixture(2, (0, 0), (1, 1), [(0, 0), (0, 1), (1, 0), (1, 1)])
        self.assertEqual(maze.valid_actions(state), ["east", "south"])
        state["position"] = [1, 1]
        self.assertEqual(maze.valid_actions(state), [])
        oracle = maze.solve(state)
        self.assertTrue(oracle["terminal"])
        self.assertTrue(oracle["at_goal"])
        self.assertEqual(oracle["distance"], 0)
        with self.assertRaises(ValueError):
            maze.step(state, "west")

    def test_malformed_geometry_rejected(self):
        base = fixture(3, (0, 0), (0, 1), [(0, 0), (0, 1)])
        changes = ({"walls": [[2, 2], [2, 2]]}, {"position": [True, 0]},
                   {"goal": [3, 0]}, {"position": [1, 1]}, {"walls": [[1]]},
                   {"size": True}, {"game": "grid_navigation"}, {"position": None})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                maze.validate_state({**base, **change})

    def test_oracle_ties_and_shortest_path_execution(self):
        square = fixture(3, (0, 0), (1, 1), [(0, 0), (0, 1), (1, 0), (1, 1)])
        oracle = maze.solve(square)
        self.assertEqual(oracle["distance"], 2)
        self.assertEqual(oracle["optimal_actions"], ["east", "south"])
        self.assertEqual(oracle["action_costs"], {"east": 2, "south": 2})
        state = maze.make_maze(16, 19, "loops")
        remaining = maze.solve(state)["distance"]
        while remaining:
            state = maze.step(state, maze.solve(state)["optimal_actions"][0])
            remaining -= 1
            self.assertEqual(maze.solve(state)["distance"], remaining)
        self.assertEqual(state["position"], state["goal"])

    def test_unreachable_and_isolated_are_not_success(self):
        state = fixture(4, (0, 0), (3, 3), [(0, 0), (0, 1), (1, 0), (3, 3)])
        oracle = maze.solve(state)
        self.assertFalse(oracle["reachable"])
        self.assertFalse(oracle["terminal"])
        self.assertEqual(oracle["optimal_actions"], ["east", "south"])
        self.assertIsNone(oracle["distance"])
        record = maze.make_record(state, "test")
        self.assertEqual(record["gold_probs"]["action"], {"east": 0.5, "south": 0.5})
        self.assertFalse(record["gold"]["solvable"])
        self.assertEqual(record["gold"]["value"], 6)
        isolated = fixture(3, (0, 0), (2, 2), [(0, 0), (2, 2)])
        self.assertTrue(maze.solve(isolated)["terminal"])
        self.assertFalse(maze.solve(isolated)["at_goal"])
        self.assertNotIn("action", maze.render_request(isolated)["questions"])


class IdentityTests(unittest.TestCase):
    def test_d4_start_goal_seed_and_wall_order_group_invariance(self):
        state = maze.make_maze(16, 11, "loops")
        group, split = maze.source_group_id(state), maze.split_for_state(state)
        for symmetry in range(8):
            changed = maze.transform_state(state, symmetry)
            changed["position"], changed["goal"] = changed["goal"], changed["position"]
            changed["walls"].reverse()
            changed["seed"], changed["topology"] = 200, "tree"
            changed["oracle"] = {"distance": -123}
            self.assertEqual(maze.source_group_id(changed), group)
            self.assertEqual(maze.split_for_state(changed), split)
        self.assertNotEqual(group, maze.source_group_id(maze.make_maze(16, 12, "loops")))

    def test_state_identity_ignores_metadata_but_not_position(self):
        state = maze.make_maze(8, 9)
        changed = copy.deepcopy(state)
        changed["seed"], changed["topology"], changed["oracle"] = 888, "tree", {"reachable": False}
        changed["walls"].reverse()
        self.assertEqual(maze.state_id(state), maze.state_id(changed))
        nxt = maze.step(state, maze.valid_actions(state)[0])
        self.assertNotEqual(maze.state_id(state), maze.state_id(nxt))
        self.assertEqual(maze.source_group_id(state), maze.source_group_id(nxt))

    def test_cross_split_map_is_rejected_by_training_loader(self):
        from train_pipeline_decisions import read_training_records
        state = maze.make_maze(8, 1)
        next_state = maze.step(state, maze.valid_actions(state)[0])
        rows = [maze.make_record(state, "train"), maze.make_record(next_state, "test")]
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "records.jsonl"
            filename.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "split"):
                read_training_records(filename)


class ObservationAndTargetTests(unittest.TestCase):
    def test_complete_fifty_map_and_local_destinations(self):
        state = maze.make_maze(50, 23, "random_obstacle")
        state["position"] = maze.step(state, maze.valid_actions(state)[0])["position"]
        request = maze.render_request(state)
        rows = request["state"].splitlines()[-50:]
        self.assertEqual(len(rows), 50)
        self.assertTrue(all(len(row) == 50 for row in rows))
        self.assertLess(len(request["state"]), 3000)
        self.assertEqual(sum(row.count("#") for row in rows), len(state["walls"]))
        self.assertEqual(sum(row.count("A") for row in rows), 1)
        self.assertEqual(sum(row.count("G") for row in rows), 1)
        for action, text in request["questions"].get("action", {}).get("criteria", {}).items():
            dest = maze.step(state, action)["position"]
            self.assertEqual(text, f"Move {action} to ({dest[0]},{dest[1]}).")

    def test_renderer_independent_of_oracle_search_and_extra_fields(self):
        state = maze.make_maze(16, 53, "loops")
        expected = maze.render_request(state)
        altered = {**state, "oracle": {"distance": 999, "optimal_actions": ["north"]},
                   "gold": "secret answer", "metadata": {"reachable": False}, "split": "test"}
        with patch.object(maze, "solve", side_effect=AssertionError("oracle reached")), \
             patch.object(maze, "_distances", side_effect=AssertionError("BFS reached")), \
             patch.object(maze, "difficulty_metrics", side_effect=AssertionError("difficulty reached")):
            self.assertEqual(maze.render_request(altered), expected)

    def test_forced_terminal_and_choice_schema(self):
        from predict_toy_decisions import validate_request
        from train_pipeline_decisions import validate_training_row
        states = [
            fixture(3, (0, 0), (0, 2), [(0, 0), (0, 1), (0, 2)]),
            fixture(3, (0, 2), (0, 2), [(0, 0), (0, 1), (0, 2)]),
            fixture(3, (1, 1), (0, 0), [(r, c) for r in range(3) for c in range(3)]),
        ]
        for index, state in enumerate(states):
            row = maze.make_record(state, "calibration")
            validate_request({"states": [{key: row[key] for key in ("id", "state", "questions")}]})
            targets = validate_training_row(row)
            self.assertEqual(set(targets), set(row["questions"]))
            self.assertEqual("action" in targets, index == 2)
            if index == 0:
                self.assertEqual(row["metadata"]["forced_action"], "east")
            if index == 1:
                self.assertEqual(row["gold"]["value"], 0)
                self.assertTrue(row["gold"]["solvable"])
                self.assertIn("@", row["state"])
            for qid, distribution in row["gold_probs"].items():
                self.assertTrue(math.isclose(sum(distribution.values()), 1.0))
                kind = row["gold_probs_kind"][qid]
                self.assertEqual(kind, "optimal_action_policy" if qid == "action" else "deterministic_truth")

    def test_all_score_boundaries(self):
        cases = {None: 6, 0: 0, 1: 1, 4: 1, 5: 2, 16: 2, 17: 3, 64: 3,
                 65: 4, 256: 4, 257: 5, 2499: 5}
        for distance, expected in cases.items():
            with self.subTest(distance=distance):
                self.assertEqual(maze._distance_level(distance), expected)

    def test_mixed_records_full_curriculum_train_contract(self):
        from train_pipeline_decisions import validate_training_row
        for size in maze.CURRICULUM_SIZES:
            for topology in maze.TOPOLOGIES:
                state = maze.make_maze(size, 143, topology)
                # Include an interior decision, since farthest endpoints in trees
                # usually have exactly one forced move and no Choice question.
                state = maze.step(state, maze.valid_actions(state)[0])
                row = maze.make_record(state, maze.split_for_state(state))
                validate_training_row(row)
                self.assertIn("action", row["questions"])
                self.assertGreaterEqual(len(row["questions"]["action"]["criteria"]), 2)
                self.assertEqual(row["gold_label_kind"]["action"], "reference_argmax_compatibility")
                self.assertEqual(row, json.loads(json.dumps(row, allow_nan=False)))


if __name__ == "__main__":
    unittest.main()
