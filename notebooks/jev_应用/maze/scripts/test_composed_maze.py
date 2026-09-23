#!/usr/bin/env python3
"""Standard-library tests for code planning plus diagnostic-only model audits."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evaluate_composed_maze as composed
import scaled_maze as maze


ROOT = Path(__file__).resolve().parents[1]


def episode(state, identifier="example", split="test"):
    return {"id": identifier, "split": split, "game": "scaled_maze", "size": state["size"], "initial_state": state}


class WrongDiagnostics(composed.ReferenceDiagnostics):
    def predict(self, payload, **kwargs):
        response = super().predict(payload, **kwargs)
        for row in response["states"]:
            for answer in row["answers"].values():
                answer["p_true"] = 1 - answer["p_true"]
                answer["probabilities"] = {key: 1 - value for key, value in answer["probabilities"].items()}
        response["states"].reverse()
        return response


class LocalObservationTests(unittest.TestCase):
    def test_local_input_ignores_goal_remote_geometry_and_oracle(self):
        state = {"game": "scaled_maze", "size": 8, "walls": [[0, 0]], "position": [3, 3], "goal": [7, 7]}
        expected = composed.render_local_request(state)
        altered = {**state, "walls": [[7, 0]], "goal": [0, 7], "oracle": {"distance": 991},
                   "planner_action": "south", "gold": "SECRET_ANSWER", "seed": 9821}
        self.assertEqual(expected, composed.render_local_request(altered))
        with patch.object(composed, "plan_shortest_path", side_effect=AssertionError("planner reached")), \
             patch.object(maze, "solve", side_effect=AssertionError("oracle reached")):
            self.assertEqual(expected, composed.render_local_request(state))
        self.assertNotIn("goal", expected["state"].lower())
        self.assertNotIn("distance", expected["state"].lower())
        self.assertNotIn("SECRET_", expected["state"])

    def test_boundaries_and_local_truth_match_geometric_neighbors(self):
        for size in (3, 5):
            state = {"game": "scaled_maze", "size": 8, "walls": [[0, 1]], "position": [0, 0], "goal": [7, 7]}
            public = composed.render_local_request(state, size)
            grid = public["state"].split("Local map:\n")[1].splitlines()
            self.assertEqual(len(grid), size)
            self.assertTrue(all(len(row) == size for row in grid))
            self.assertEqual(composed.local_truth(public), {"north": False, "east": False, "south": True, "west": False})
            from predict_toy_decisions import validate_request
            validate_request({"states": [{"id": "local", **public}]})
            for action in maze.DIRECTIONS:
                question = public["questions"]["clear_" + action]
                self.assertIn(action, question["instructions"])
                self.assertEqual(set(question["criteria"]), {"false", "true"})


class PlannerAndDiagnosticsTests(unittest.TestCase):
    def test_bfs_matches_exact_oracle_and_remembers_unique_cells(self):
        for topology in maze.TOPOLOGIES:
            state = maze.make_maze(16, 901, topology)
            route = composed.plan_shortest_path(state)
            self.assertEqual(len(route), maze.solve(state)["distance"])
            traces, _ = composed.prepare_trajectories([episode(state)], audit_every=3)
            trace = traces[0]
            self.assertTrue(trace["planner_completion"])
            self.assertEqual(trace["visited_cells"], len(route) + 1)
            self.assertEqual(trace["loop_count"], 0)
            self.assertEqual(trace["path_efficiency"], 1)

    def test_perfect_and_wrong_models_execute_identical_routes_and_audit_states(self):
        states = [episode(maze.make_maze(8, 43, "tree"), "tree"),
                  episode(maze.make_maze(16, 44, "loops"), "loops", "ood")]
        reference = composed.run_composed(states, composed.ReferenceDiagnostics(), audit_every=4)
        wrong = composed.run_composed(states, WrongDiagnostics(), audit_every=4)
        self.assertEqual(reference["audit_inputs_sha256"], wrong["audit_inputs_sha256"])
        self.assertEqual(reference["planner_trajectories_sha256"], wrong["planner_trajectories_sha256"])
        for result in (reference, wrong):
            self.assertEqual(result["model_role"], "diagnostic_only")
            self.assertEqual(result["summary"]["planner_completion_rate"], 1)
            self.assertEqual(result["summary"]["override_count"], 0)
        self.assertEqual(reference["summary"]["atomic_accuracy"], 1)
        self.assertEqual(reference["summary"]["atomic_brier"], 0)
        self.assertEqual(reference["summary"]["atomic_nll"], 0)
        self.assertEqual(wrong["summary"]["atomic_accuracy"], 0)
        self.assertEqual(wrong["summary"]["atomic_brier"], 1)
        self.assertEqual(wrong["summary"]["model_vs_planner_disagreement"], 1)
        self.assertGreater(wrong["summary"]["atomic_nll"], 20)

    def test_all_step_audit_and_batch_order_independence(self):
        state = maze.make_maze(8, 63, "tree")
        a = composed.run_composed([episode(state)], composed.ReferenceDiagnostics(), audit_every=1, batch_states=1)
        b = composed.run_composed([episode(state)], composed.ReferenceDiagnostics(), audit_every=1, batch_states=7)
        self.assertEqual(a["audits"], b["audits"])
        self.assertEqual(a["audit_inputs_sha256"], b["audit_inputs_sha256"])
        self.assertEqual(a["summary"]["audited_states"], a["summary"]["planner_steps"])
        self.assertEqual(a["summary"]["atomic_questions"], 4 * a["summary"]["planner_steps"])

    def test_unreachable_and_already_complete_states(self):
        state = {"game": "scaled_maze", "size": 3, "position": [0, 0], "goal": [2, 2],
                 "walls": [[r, c] for r in range(3) for c in range(3) if (r, c) not in {(0, 0), (2, 2)}]}
        self.assertIsNone(composed.plan_shortest_path(state))
        done = copy.deepcopy(state)
        done["position"] = done["goal"][:]
        result = composed.run_composed([episode(state, "unreachable"), episode(done, "done")], composed.ReferenceDiagnostics())
        self.assertEqual(result["episodes"][0]["planner_status"], "unreachable")
        self.assertEqual(result["episodes"][1]["planner_status"], "goal")
        self.assertEqual(result["summary"]["planner_completed"], 1)
        self.assertEqual(result["summary"]["audited_states"], 0)
        self.assertIsNone(result["summary"]["atomic_accuracy"])

    def test_invalid_diagnostic_probabilities_rejected(self):
        for probabilities in ({"true": 1}, {"false": .2, "true": .2},
                              {"false": float("nan"), "true": 1}, {"false": 0, "true": True}):
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                composed._validate_answer({"type": "boolean", "probabilities": probabilities})

    def test_actual_three_map_pilot_has_full_16_24_96_paths(self):
        source = ROOT / "data/scaled_games_v4/rollout_pilot.jsonl"
        if not source.exists():
            self.skipTest("The optional frozen three-map pilot is absent")
        episodes = [r for r in map(json.loads, source.read_text().splitlines()) if r["game"] == "scaled_maze"]
        result = composed.run_composed(episodes, composed.ReferenceDiagnostics())
        self.assertEqual([row["executed_steps"] for row in result["episodes"]], [16, 24, 96])
        self.assertEqual(result["summary"]["planner_completed"], 3)
        self.assertEqual(result["summary"]["planner_steps"], 136)
        self.assertEqual(result["summary"]["audited_states"], 17)
        self.assertEqual(result["summary"]["atomic_questions"], 68)
        self.assertEqual(result["summary"]["atomic_accuracy"], 1)
        self.assertEqual(result["summary"]["path_efficiency"], 1)
        # Compact trace: geometry appears once, not again in every step.
        self.assertTrue(all("walls" not in step and "state" not in step for row in result["episodes"] for step in row["steps"]))


if __name__ == "__main__":
    unittest.main()
