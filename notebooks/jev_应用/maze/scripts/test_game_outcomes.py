#!/usr/bin/env python3
import copy
import unittest

from game_outcomes import event_record
from game_question_profiles import add_maze_atomic_questions
from scaled_maze import make_maze, make_record
from snake_game import make_snake
from train_pipeline_decisions import validate_training_row, target_for


class OutcomeTests(unittest.TestCase):
    def test_maze_exact_probability_and_observations(self):
        state = {"game": "scaled_maze", "size": 5, "walls": [[0, 1]],
                 "position": [0, 0], "goal": [4, 4], "seed": 17, "topology": "random_obstacle"}
        # Only south is safe: its requested actuator probability is .7.
        row = event_record(state, "train", "south", .7, 17)
        self.assertAlmostEqual(row["metadata"]["exact_event_probability"], .7)
        validate_training_row(row)
        outcomes = [event_record(state, "train", "south", .7, s)["gold"]["survive"] for s in range(1200)]
        self.assertLess(abs(sum(outcomes)/len(outcomes)-.7), .05)
        self.assertTrue(any(outcomes) and not all(outcomes))

    def test_outcome_and_oracle_hidden_from_input(self):
        state = make_maze(8, 17)
        rows = [event_record(state, "train", "north", .7, seed) for seed in (1, 2)]
        self.assertEqual(rows[0]["state"], rows[1]["state"])
        self.assertEqual(rows[0]["questions"], rows[1]["questions"])
        self.assertNotIn("exact_event_probability", rows[0]["state"])

    def test_observed_target_does_not_use_probability_argmax(self):
        state = {"game": "scaled_maze", "size": 5, "walls": [[0, 1]],
                 "position": [0, 0], "goal": [4, 4], "seed": 17, "topology": "random_obstacle"}
        row = next(event_record(state, "train", "south", .7, seed) for seed in range(100)
                   if not event_record(state, "train", "south", .7, seed)["gold"]["survive"])
        target = validate_training_row(row)["survive"]
        example = {**target, "candidate_ids": ["false", "true"]}
        self.assertEqual(target_for(example, "observed_outcome"), [1., 0.])
        self.assertAlmostEqual(target_for(example, "gold_distribution")[1], .7)
        example["gold_label_kind"] = "reference_argmax_compatibility"
        self.assertIsNone(target_for(example, "observed_outcome"))

    def test_snake_distribution_and_immutability(self):
        state = make_snake(8, 9)
        before = copy.deepcopy(state)
        from snake_game import valid_actions
        row = event_record(state, "test", valid_actions(state)[0], .3, 31)
        validate_training_row(row)
        self.assertEqual(state, before)
        self.assertAlmostEqual(sum(row["gold_probs"]["survive"].values()), 1)
        self.assertEqual(set(row["questions"]["survive"]["criteria"]), {"true", "false"})
        from snake_game import make_record as snake_record
        self.assertEqual(row["metadata"]["source_group_id"], snake_record(state, "test")["metadata"]["source_group_id"])

    def test_atomic_questions_have_explicit_meaning(self):
        row = add_maze_atomic_questions(make_record(make_maze(16, 23), "train"))
        validate_training_row(row)
        for qid in row["metadata"]["question_profiles"]["atomic"]:
            self.assertIn(qid.removeprefix("clear_"), row["questions"][qid]["instructions"])
            self.assertEqual(set(row["questions"][qid]["criteria"]), {"true", "false"})


if __name__ == "__main__":
    unittest.main()
