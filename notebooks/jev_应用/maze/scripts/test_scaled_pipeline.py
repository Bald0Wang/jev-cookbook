#!/usr/bin/env python3
"""Independent standard-library integration checks for scaled game pipelines.

Run: python3 -m unittest discover -s scripts -p test_scaled_pipeline.py -v
Only random/reference controllers and an explicit in-memory fake predictor run.
No weights, GPU, API, network, credential files, or persistent datasets are used.
The optional existing-data audit reads data/scaled_games_v4 without changing it.
"""

from collections import defaultdict
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

import build_scaled_games as builder
import evaluate_scaled_games as evaluator
import game_outcomes
import predict_toy_decisions as predictor_module
import scaled_maze as maze
import snake_game as snake
from train_pipeline_decisions import load_training_examples, target_for, validate_training_row


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "scaled_games_v4"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def episode(state, identifier, split="test"):
    return {"id": identifier, "split": split, "game": state["game"],
            "size": state["size"], "initial_state": copy.deepcopy(state)}


def evaluate(rows, engine="reference", controller=None, seed=17, max_steps=None, fake=None):
    """Run the real CLI main while replacing only model loading when requested."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        source, output = path / "episodes.jsonl", path / "rollout.json"
        source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        argv = ["evaluate_scaled_games.py", "--episodes", str(source), "--output", str(output),
                "--engine", engine, "--limit-per-cell", "1", "--seed", str(seed)]
        if controller is not None:
            argv += ["--controller", controller]
        if max_steps is not None:
            argv += ["--max-steps", str(max_steps)]
        if engine == "checkpoint":
            if fake is None:
                raise AssertionError("A real checkpoint is forbidden in these tests")
            argv += ["--checkpoint", "unused_fake_checkpoint"]
        with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()), \
             patch.object(predictor_module, "DecisionPredictor", return_value=fake):
            evaluator.main()
        result = json.loads(output.read_text())
        if result["episodes_sha256"] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise AssertionError("Evaluator did not record the exact input cohort hash")
        return result


class FakePredictor:
    def __init__(self, mutate=None):
        self.payloads, self.mutate = [], mutate

    def predict(self, payload, **kwargs):
        self.payloads.append(copy.deepcopy(payload))
        states = []
        for row in payload["states"]:
            actions = list(row["questions"]["action"]["criteria"])
            probabilities = {action: float(index == 0) for index, action in enumerate(actions)}
            if self.mutate is not None:
                probabilities = self.mutate(probabilities)
            states.append({"id": row["id"], "answers": {"action": {"probabilities": probabilities}}})
        # Reverse response order deliberately: mapping must use request IDs.
        return {"states": list(reversed(states)), "execution": {"forward_passes": 1, "network_model_calls": 0}}


class CharacterTokenizer:
    eos_token_id = 0

    def encode(self, text, add_special_tokens=False):
        return [ord(char) + 1 for char in text]


def decision_maze(position=(1, 1), size=8):
    return {"game": "scaled_maze", "size": size, "walls": [], "position": list(position),
            "goal": [size - 1, size - 1], "seed": 123, "topology": "random_obstacle"}


class ClosedLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (DATA / "episodes.jsonl").exists():
            records = read_jsonl(DATA / "episodes.jsonl")
            cls.cohort = [row for row in records if row["split"] == "test" and row["size"] == 8]
            cls.cohort += [row for row in records if row["split"] == "test" and row["size"] == 16
                           and row["game"] == "scaled_maze" and row["initial_state"]["topology"] == "corridor"][:1]
        else:
            cls.cohort = [episode(maze.make_maze(8, 71 + i, topology), "maze:" + topology)
                          for i, topology in enumerate(maze.TOPOLOGIES)]
            cls.cohort.append(episode(snake.make_snake(8, 77), "snake:77"))
        cls.reference = evaluate(cls.cohort, engine="reference")
        cls.random = evaluate(cls.cohort, engine="random")

    def test_reference_finishes_maze_in_exact_shortest_length(self):
        mazes = [row for row in self.reference["episodes"] if row["game"] == "scaled_maze"]
        self.assertTrue(mazes)
        for row in mazes:
            self.assertTrue(row["success"], row["id"])
            self.assertEqual(row["steps_count"], maze.solve(row["initial_state"])["distance"])
            self.assertTrue(all(step["optimal_action"] for step in row["steps"]))

    def test_default_horizon_and_topology_stratified_frozen_selection(self):
        expected, seen = [], set()
        for row in self.cohort:
            key = row["split"], row["game"], row["size"], row["initial_state"].get("topology", "snake")
            if key not in seen:
                expected.append(row["id"])
                seen.add(key)
        self.assertEqual([row["id"] for row in self.reference["episodes"]], expected)
        self.assertEqual([row["id"] for row in self.random["episodes"]], expected)
        for result in (self.reference, self.random):
            self.assertEqual(result["max_steps"], 0)
            self.assertEqual(result["execution"]["network_calls"], 0)
            for row in result["episodes"]:
                self.assertEqual(row["horizon"], 2 * row["size"] ** 2)
                self.assertLessEqual(row["steps_count"], row["horizon"])
            self.assertEqual(len(result["summary"]), len(seen))

    def test_default_random_engine_actually_samples(self):
        self.assertEqual(self.random["controller"], "sample")
        strict_non_argmax = False
        for row in self.random["episodes"]:
            for step in row["steps"]:
                probabilities = step["probabilities"]
                self.assertTrue(all(abs(p - 1 / len(probabilities)) < 1e-12 for p in probabilities.values()))
                if len(probabilities) > 1 and step["action"] != sorted(probabilities)[0]:
                    strict_non_argmax = True
        self.assertTrue(strict_non_argmax, "The random controller behaves like deterministic argmax ties")

    def test_transition_and_action_probability_mapping(self):
        for result in (self.reference, self.random):
            for row in result["episodes"]:
                state = row["initial_state"]
                game = maze if row["game"] == "scaled_maze" else snake
                for trace in row["steps"]:
                    self.assertEqual(trace["state"], state)
                    self.assertEqual(set(trace["probabilities"]), set(game.valid_actions(state)))
                    self.assertAlmostEqual(sum(trace["probabilities"].values()), 1)
                    state = game.step(state, trace["action"])
                    self.assertEqual(trace["next_state"], state)
                self.assertEqual(row["final_state"], state)

    def test_per_episode_seed_is_reproducible_and_batch_composition_independent(self):
        rows = [episode(decision_maze(), "same_episode")]
        first = evaluate(rows, "random", max_steps=12, seed=91)
        repeated = evaluate(rows, "random", max_steps=12, seed=91)
        extra = episode(maze.make_maze(8, 71, "tree"), "unrelated_episode", "ood")
        expanded = evaluate([extra] + rows, "random", max_steps=12, seed=91)
        self.assertEqual(first["episodes"], repeated["episodes"])
        self.assertEqual(first["episodes"][0], next(r for r in expanded["episodes"] if r["id"] == "same_episode"))

    def test_first_episode_is_not_replaced_by_an_easier_same_cell(self):
        hard = episode(maze.make_maze(8, 34, "tree"), "first_hard")
        easy = copy.deepcopy(hard)
        easy["id"] = "later_already_solved"
        easy["initial_state"]["position"] = easy["initial_state"]["goal"][:]
        result = evaluate([hard, easy], "reference", max_steps=1)
        self.assertEqual([r["id"] for r in result["episodes"]], ["first_hard"])
        self.assertFalse(result["episodes"][0]["success"])


class ModelBoundaryTests(unittest.TestCase):
    def test_reversed_responses_map_by_id_and_never_receive_oracle_fields(self):
        first, second = decision_maze((1, 1)), decision_maze((0, 0))
        first["oracle"] = {"optimal_action": "SECRET_ORACLE_SENTINEL"}
        second["future_food"] = "SECRET_FUTURE_SENTINEL"
        rows = [episode(first, "first"), episode(second, "second", "ood")]
        fake = FakePredictor()
        result = evaluate(rows, "checkpoint", max_steps=1, fake=fake)
        self.assertTrue(fake.payloads)
        for payload in fake.payloads:
            for row in payload["states"]:
                self.assertEqual(set(row), {"id", "state", "questions"})
                self.assertNotIn("SECRET_", json.dumps(row))
        expected = {"first": "north", "second": "east"}
        for row in result["episodes"]:
            self.assertEqual(row["steps"][0]["action"], expected[row["id"]])

    def test_invalid_response_distributions_are_rejected(self):
        rows = [episode(decision_maze(), "bad_distribution")]
        mutations = {
            "missing": lambda p: {next(iter(p)): 1.0},
            "extra": lambda p: {**p, "teleport": 0.0},
            "nonunit": lambda p: {k: 0.1 for k in p},
            "nonfinite": lambda p: {k: float("nan") for k in p},
            "negative": lambda p: {k: (-1.0 if i == 0 else 2.0) for i, k in enumerate(p)},
            "boolean": lambda p: {k: bool(i == 0) for i, k in enumerate(p)},
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                evaluate(rows, "checkpoint", max_steps=1, fake=FakePredictor(mutate))


class OutcomeIsolationTests(unittest.TestCase):
    def test_event_seed_changes_only_realization_not_observation_or_probability(self):
        state = maze.make_maze(8, 41, "tree")
        intended = maze.valid_actions(state)[0]
        before = random.getstate()
        records = [game_outcomes.event_record(state, "train", intended, .5, seed) for seed in range(24)]
        self.assertEqual(random.getstate(), before)
        self.assertEqual({row["gold"]["survive"] for row in records}, {False, True})
        for row in records:
            self.assertEqual(row["id"], records[0]["id"])
            self.assertEqual(row["state"], records[0]["state"])
            self.assertEqual(row["questions"], records[0]["questions"])
            self.assertEqual(row["gold_probs"], records[0]["gold_probs"])
            self.assertEqual(row["gold_label_kind"]["survive"], "observed_outcome")
            validate_training_row(row)
            realized = row["metadata"]["realized_actuator_action"]
            self.assertEqual(row["gold"]["survive"], row["metadata"]["safe_actions"][realized])

    def test_exact_event_truth_cannot_change_observed_training_target_or_tokens(self):
        state = maze.make_maze(8, 41, "tree")
        record = game_outcomes.event_record(state, "train", maze.valid_actions(state)[0], .7, 7)
        altered = copy.deepcopy(record)
        altered["gold_probs"]["survive"] = {"false": .87654321, "true": .12345679}
        altered["metadata"]["exact_event_probability"] = .12345679
        altered["metadata"]["safe_actions"] = {"SECRET_EVALUATION_ONLY": True}
        with tempfile.TemporaryDirectory() as directory:
            examples = []
            for index, row in enumerate((record, altered)):
                path = Path(directory) / f"source_{index}.jsonl"
                path.write_text(json.dumps(row) + "\n")
                loaded, _ = load_training_examples(path, CharacterTokenizer(), 100000)
                examples.append(loaded[0])
        self.assertEqual(examples[0]["leaf_tokens"], examples[1]["leaf_tokens"])
        self.assertEqual(target_for(examples[0], "observed_outcome"), target_for(examples[1], "observed_outcome"))
        self.assertNotEqual(target_for(examples[0], "gold_distribution"), target_for(examples[1], "gold_distribution"))

    def test_snake_future_food_rng_does_not_enter_observation_or_safety_labels(self):
        original = snake.make_snake(8, 17)
        original["food"] = [original["body"][0][0], original["body"][0][1] + 1]
        snake.validate_state(original)
        public = snake.render_request(original)
        labels = snake.make_record(original, "train")["gold_probs"]
        future_foods = set()
        for rng_state in range(12):
            changed = copy.deepcopy(original)
            changed.update(seed=100000 + rng_state, rng_state=rng_state,
                           oracle="SECRET_ORACLE", future_food="SECRET_FUTURE_FOOD")
            self.assertEqual(snake.render_request(changed), public)
            self.assertEqual(snake.make_record(changed, "train")["gold_probs"], labels)
            future_foods.add(tuple(snake.step(changed, "east")["food"]))
            event = game_outcomes.event_record(changed, "train", "east", .7, 91)
            self.assertNotIn("SECRET_", event["state"])
        self.assertGreater(len(future_foods), 1)
        with patch.object(snake, "step", side_effect=AssertionError("renderer called dynamics")), \
             patch.object(snake, "one_step_safe", side_effect=AssertionError("renderer called labels")), \
             patch.object(snake, "_food", side_effect=AssertionError("renderer sampled future food")):
            self.assertEqual(snake.render_request(original), public)


class ExistingDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DATA / "manifest.json").exists():
            raise unittest.SkipTest("Optional existing data/scaled_games_v4 artifact is absent")
        cls.manifest = json.loads((DATA / "manifest.json").read_text())
        cls.rows = [row for folder in ("policy", "events") for path in sorted((DATA / folder).glob("*.jsonl"))
                    for row in read_jsonl(path)]

    def test_frozen_artifact_hashes_and_record_schema(self):
        for relative, expected in self.manifest["files"].items():
            self.assertEqual(hashlib.sha256((DATA / relative).read_bytes()).hexdigest(), expected, relative)
        for row in self.rows:
            validate_training_row(row)

    def test_source_groups_and_identical_public_inputs_do_not_cross_splits(self):
        groups, visible = defaultdict(set), defaultdict(set)
        for row in self.rows:
            groups[row["metadata"]["source_group_id"]].add(row["split"])
            visible[json.dumps({k: row[k] for k in ("state", "questions")}, sort_keys=True)].add(row["split"])
        self.assertFalse([key for key, splits in groups.items() if len(splits) > 1])
        self.assertFalse([key for key, splits in visible.items() if len(splits) > 1])

    def test_maze_group_matches_geometry_and_sampled_positions_are_distinct(self):
        by_group, by_sampler = defaultdict(list), defaultdict(list)
        for row in self.rows:
            if row["family_id"] != "scaled_maze":
                continue
            state = row["metadata"]["environment_state"]
            group = maze.source_group_id(state)
            self.assertEqual(row["metadata"]["source_group_id"], group)
            source = row["metadata"]["maze_position_source"]
            self.assertEqual(source["position"], state["position"])
            self.assertEqual(source["shortest_path_distance_to_goal"], maze.solve(state)["distance"])
            if source["sample_index"]:
                self.assertGreaterEqual(len(maze.valid_actions(state)), 2)
            # D4-equivalent layouts can use the same coordinate for different
            # physical cells. Deduplicate actual states within a source group,
            # and positions only within one generation/sampling invocation.
            by_group[group].append(maze.state_id(state))
            by_sampler[(state["size"], state["seed"], state["topology"])].append(tuple(state["position"]))
        self.assertTrue(by_group)
        for identities in by_group.values():
            self.assertEqual(len(identities), len(set(identities)))
        for positions in by_sampler.values():
            self.assertEqual(len(positions), len(set(positions)))

    def test_existing_snake_d4_physical_states_do_not_cross_splits(self):
        canonical = defaultdict(set)
        for row in self.rows:
            state = row["metadata"]["environment_state"]
            if state["game"] != "snake" or row["gold_label_kind"].get("survive") == "observed_outcome":
                continue
            size, variants = state["size"], []
            for symmetry in range(8):
                body = tuple(maze.transform_cell(cell, size, symmetry) for cell in state["body"])
                food = maze.transform_cell(state["food"], size, symmetry)
                # All current records have body length >= 2, so head/neck fixes
                # heading; it is not an omitted independent state variable.
                self.assertGreaterEqual(len(body), 2)
                variants.append((body, food))
            canonical[(size, min(variants))].add(row["split"])
        self.assertTrue(canonical)
        self.assertFalse([key for key, splits in canonical.items() if len(splits) > 1])

    def test_event_distribution_recomputes_from_public_geometry(self):
        for row in self.rows:
            if row["gold_label_kind"].get("survive") != "observed_outcome":
                continue
            metadata = row["metadata"]
            spec = metadata["event_spec"]
            rebuilt = game_outcomes.event_record(metadata["environment_state"], row["split"],
                                                spec["intended_action"], spec["reliability"], metadata["outcome_seed"])
            self.assertEqual(row["state"], rebuilt["state"])
            self.assertEqual(row["questions"], rebuilt["questions"])
            self.assertEqual(row["gold"], rebuilt["gold"])
            self.assertEqual(row["gold_probs"], rebuilt["gold_probs"])


if __name__ == "__main__":
    unittest.main()
