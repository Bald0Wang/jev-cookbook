#!/usr/bin/env python3
"""Offline tests for model-dependent edge exploration and strict state separation."""

import ast
import copy
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import evaluate_model_edges_maze as runner
from evaluate_native_qwen_maze import NativeBooleanPredictor
from evaluate_composed_maze import ReferenceDiagnostics
import scaled_maze as maze


def episode(state, identifier="maze"):
    return {"id": identifier, "game": "scaled_maze", "split": "test", "size": state["size"], "initial_state": state}


class ChangedDiagnostics(ReferenceDiagnostics):
    def __init__(self, mode):
        self.mode = mode

    def predict(self, payload, **kwargs):
        response = super().predict(payload, **kwargs)
        for row in response["states"]:
            for answer in row["answers"].values():
                p = 1 - answer["p_true"] if self.mode == "inverted" else float(self.mode)
                answer["p_true"] = p
                answer["probabilities"] = {"false": 1 - p, "true": p}
        response["states"].reverse()
        return response


class EnvironmentAndMemoryTests(unittest.TestCase):
    def test_collision_is_nonfatal_and_verified_edges_are_symmetric(self):
        state = {"game": "scaled_maze", "size": 4, "position": [0, 0], "goal": [3, 3], "walls": [[0, 1]]}
        env = runner.MazeEnvironment(state)
        policy = runner.EdgeExplorer(**env.public_coordinates())
        for action in ("north", "east"):
            feedback = env.attempt(action)
            self.assertTrue(feedback["collision"])
            self.assertEqual(feedback["next_position"], [0, 0])
            policy.observe_transition(action, feedback["next_position"], feedback["collision"])
            target = runner.destination((0, 0), action)
            self.assertEqual(policy.edges[runner.edge_key(target, (0, 0))], "blocked")
        feedback = env.attempt("south")
        self.assertFalse(feedback["collision"])
        policy.observe_transition("south", feedback["next_position"], False)
        self.assertIn((1, 0), policy.adjacency[(0, 0)])
        self.assertIn((0, 0), policy.adjacency[(1, 0)])
        self.assertEqual(state["position"], [0, 0])

    def test_policy_has_no_environment_oracle_or_wall_access(self):
        source = inspect.getsource(runner.EdgeExplorer)
        tree = ast.parse(source)
        forbidden = {"walls", "_walls", "env", "environment", "solve", "valid_actions", "render_local_request", "local_truth"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, forbidden)
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, forbidden)
        policy = runner.EdgeExplorer((0, 0), (3, 3), 4)
        self.assertEqual(set(vars(policy)), {"position", "goal", "size", "predictions", "edges", "adjacency", "visits"})
        self.assertTrue(all(not callable(value) for value in vars(policy).values()))

    def test_verified_graph_bfs_repositions_to_remaining_frontier(self):
        policy = runner.EdgeExplorer((0, 0), (3, 3), 4)
        policy.remember_prediction(dict.fromkeys(maze.DIRECTIONS, .5))
        policy.observe_transition("east", (0, 1), False)
        policy.remember_prediction(dict.fromkeys(maze.DIRECTIONS, .5))
        for action in ("north", "east", "south"):
            policy.observe_transition(action, (0, 1), True)
        decision = policy.choose()
        self.assertEqual(decision["action"], "west")
        self.assertEqual(decision["mode"], "verified_edge_reposition")
        self.assertFalse(decision["untried_edge"])

    def test_high_probability_goal_progress_and_low_probability_probe_order(self):
        policy = runner.EdgeExplorer((2, 2), (2, 4), 5)
        policy.remember_prediction({"north": .999, "east": .998, "south": .9, "west": .8})
        self.assertEqual(policy.choose()["action"], "east")
        policy.remember_prediction({"north": .49, "east": .2, "south": .1, "west": .1})
        self.assertEqual(policy.choose()["action"], "north")
        self.assertEqual(policy.choose()["mode"], "low_probability_probe")

    def test_remote_geometry_cannot_change_policy_but_predictions_can(self):
        base = {"game": "scaled_maze", "size": 8, "position": [1, 1], "goal": [6, 6], "walls": []}
        other = copy.deepcopy(base)
        other["walls"] = [[5, 5], [5, 6], [6, 5]]
        first, second = runner.MazeEnvironment(base), runner.MazeEnvironment(other)
        self.assertEqual(first.public_coordinates(), second.public_coordinates())
        self.assertEqual(first.observe(), second.observe())
        policies = [runner.EdgeExplorer(**env.public_coordinates()) for env in (first, second)]
        for policy in policies:
            policy.remember_prediction({"north": .1, "east": .9, "south": .8, "west": .1})
        self.assertEqual(policies[0].choose(), policies[1].choose())
        policies[1].remember_prediction({"north": .1, "east": .1, "south": .9, "west": .1})
        self.assertNotEqual(policies[0].choose()["action"], policies[1].choose()["action"])


class ExplorationTests(unittest.TestCase):
    def test_probabilities_change_executed_actions(self):
        state = maze.make_maze(8, 921, "loops")
        engines = [ReferenceDiagnostics(), ChangedDiagnostics("inverted"), runner.ConstantDiagnostics()]
        results = [runner.run_exploration([episode(state)], engine, max_steps=128) for engine in engines]
        traces = [tuple(step["action"] for step in r["episodes"][0]["steps"]) for r in results]
        self.assertEqual(len(set(traces)), 3)
        self.assertEqual(results[0]["summary"]["atomic_accuracy"], 1)
        self.assertEqual(results[1]["summary"]["atomic_accuracy"], 0)
        self.assertGreater(results[1]["summary"]["collisions"], 0)
        self.assertTrue(all(r["model_role"] == "model_guided_local_edge_exploration" for r in results))

    def test_constant_engine_ignores_input_and_truth(self):
        with patch.object(runner, "local_truth", side_effect=AssertionError("truth accessed")):
            result = runner.ConstantDiagnostics().predict({"states": [{"id": "one", "state": object()}]})
        self.assertEqual(len(result["states"][0]["answers"]), 4)
        self.assertTrue(all(answer["p_true"] == .5 for answer in result["states"][0]["answers"].values()))

    def test_false_negative_edges_are_physically_probed_and_no_blocked_edge_repeats(self):
        state = {"game": "scaled_maze", "size": 4, "position": [1, 1], "goal": [1, 2], "walls": []}
        result = runner.run_exploration([episode(state)], ChangedDiagnostics(0))
        row = result["episodes"][0]
        self.assertTrue(row["goal_completion"])
        self.assertEqual(row["steps"][0]["mode"], "low_probability_probe")
        self.assertGreater(row["probe_count"], 0)
        maze_state = maze.make_maze(8, 291, "tree")
        result = runner.run_exploration([episode(maze_state)], ChangedDiagnostics("inverted"))
        attempted_blocked = set()
        for trace in result["episodes"][0]["steps"]:
            edge = runner.edge_key(trace["position"], runner.destination(trace["position"], trace["action"]))
            self.assertNotIn(edge, attempted_blocked)
            if trace["collision"]:
                attempted_blocked.add(edge)

    def test_no_full_solver_or_legal_action_oracle_is_called(self):
        state = maze.make_maze(8, 113, "tree")
        with patch.object(maze, "solve", side_effect=AssertionError("full solver called")), \
             patch.object(maze, "valid_actions", side_effect=AssertionError("safe actions called")), \
             patch.object(maze, "_distances", side_effect=AssertionError("full BFS called")):
            result = runner.run_exploration([episode(state)], ReferenceDiagnostics(), max_steps=128)
        self.assertLessEqual(result["summary"]["attempts"], 128)
        self.assertFalse(result["protocol"]["full_map_bfs_used"])

    def test_unreachable_component_exhausts_and_horizon_is_honored(self):
        state = {"game": "scaled_maze", "size": 3, "position": [0, 0], "goal": [2, 2],
                 "walls": [[r, c] for r in range(3) for c in range(3) if (r, c) not in {(0, 0), (0, 1), (2, 2)}]}
        result = runner.run_exploration([episode(state)], ChangedDiagnostics(0), max_steps=0)
        row = result["episodes"][0]
        self.assertEqual(row["status"], "frontier_exhausted")
        self.assertFalse(row["goal_completion"])
        self.assertLess(row["attempts"], 18)
        short = runner.run_exploration([episode(state)], ChangedDiagnostics(0), max_steps=1)
        self.assertEqual(short["episodes"][0]["status"], "horizon_exhausted")
        self.assertEqual(short["summary"]["attempts"], 1)

    def test_batches_and_response_order_do_not_change_a_models_trajectory(self):
        rows = [episode(maze.make_maze(8, 511, "tree"), "one"), episode(maze.make_maze(8, 512, "loops"), "two")]
        first = runner.run_exploration(rows, ChangedDiagnostics(.5), batch_states=1, max_steps=40)
        second = runner.run_exploration(rows, ChangedDiagnostics(.5), batch_states=2, max_steps=40)
        for a, b in zip(first["episodes"], second["episodes"]):
            self.assertEqual(a["steps"], b["steps"])
            self.assertEqual(a["observations"], b["observations"])


class NativeBooleanAdapterTests(unittest.TestCase):
    def test_independent_boolean_mapping_batch_and_native_receipts(self):
        public = runner.render_local_request(maze.make_maze(8, 77, "tree"))
        payload = {"states": [{"id": "first", **public}, {"id": "second", **public}]}
        class FakeNative:
            def predict(inner, request, **kwargs):
                self.assertEqual(kwargs, {"batch_questions": 0, "temperature": 1.0})
                self.assertEqual(len(request["states"]), 8)
                rows = []
                for index, row in enumerate(request["states"]):
                    question = row["questions"]["action"]
                    self.assertEqual(question["type"], "choice")
                    self.assertEqual(list(question["criteria"]), ["false", "true"])
                    original = list(public["questions"].values())[index % 4]
                    self.assertEqual(question["instructions"], original["instructions"])
                    self.assertEqual(question["criteria"], original["criteria"])
                    self.assertEqual(row["state"], public["state"])
                    p = .1 + .1 * index
                    rows.append({"id": row["id"], "answers": {"action": {"type": "choice",
                        "probabilities": {"false": 1-p, "true": p},
                        "candidate_to_token": {"false": {"text": "A", "id": 32}, "true": {"text": "B", "id": 33}},
                        "native_option_logits": {"false": -1.0, "true": 1.0}, "offered_token_mass": .02}}})
                return {"states": list(reversed(rows)), "execution": {"forward_passes": 1, "network_model_calls": 0}}
        response = NativeBooleanPredictor(FakeNative()).predict(payload)
        self.assertEqual(response["execution"]["forward_passes"], 1)
        self.assertEqual(response["execution"]["boolean_questions"], 8)
        first = response["states"][0]["answers"]
        self.assertAlmostEqual(first["clear_north"]["p_true"], .1)
        self.assertAlmostEqual(first["clear_west"]["p_true"], .4)
        self.assertEqual(first["clear_north"]["target_kind"], "native_token_conditional_probabilities")
        self.assertEqual(first["clear_north"]["offered_token_mass"], .02)
        self.assertEqual(first["clear_north"]["candidate_to_token"]["true"]["text"], "B")

    def test_native_adapter_rejects_nonunit_outputs(self):
        class BadNative:
            def predict(inner, request, **kwargs):
                return {"states": [{"id": row["id"], "answers": {"action": {
                    "type": "choice", "probabilities": {"false": .8, "true": .8}}}} for row in request["states"]]}
        public = runner.render_local_request(maze.make_maze(8, 77, "tree"))
        adapter = NativeBooleanPredictor(BadNative())
        with self.assertRaises(ValueError):
            adapter.predict({"states": [{"id": "case", **public}]})
        with self.assertRaises(ValueError):
            adapter.predict({"states": [{"id": "case", **public}]}, temperature=.5)


if __name__ == "__main__":
    unittest.main()
