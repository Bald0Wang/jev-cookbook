#!/usr/bin/env python3
"""Dev-only controller diagnostic for the frozen RGB/RNN Predict Position expert.

This separate entry point uses greedy epsilon .1 and the benchmark's per-case
seed-17 RNG. It never changes the frozen training collector or its epsilon-zero
reference. Both controllers still use expert RGB/RNN inputs, not student text.
"""
import argparse
from collections import Counter
import copy
import json
import math
from pathlib import Path
import random
import time

from sonic_predict_data import (
    ACTIONS, SOURCES, MirroredPredictEnvironment, behavior_distribution, digest,
    encode, expert_argmax, file_digest, load_policy, observed_ammo, policy_request,
    probability_check, read_rows, replay_standard, sample_with_receipt, write_json,
)


def require_dev(case):
    expected = {"task": "shooting", "scenario": "predict_position", "frame_skip": 4,
                "max_steps": 75, "history_length": 4}
    if case.get("split") != "dev" or case.get("spec") != expected:
        raise ValueError("Only the registered four-tick PP development cases are accepted")


def collect(case, actor, policy_id, old_wad, env_factory=MirroredPredictEnvironment):
    require_dev(case)
    rng = random.Random(int(digest([case["id"], 17])[:16], 16))
    env = env_factory(case["spec"], old_wad)
    episode = {"case": copy.deepcopy(case), "continuation_policy_id": policy_id,
               "steps": [], "complete": False, "success": None}
    forwards, resets = actor.forward_count, actor.reset_count
    try:
        obs, info, initial = env.reset(case["seed"])
        episode.update(initial_observation=copy.deepcopy(obs), mirror_initial=initial)
        actor.reset()
        while not info["terminated"]:
            result = actor.predict(env.expert_frame())
            probs = probability_check(result)
            behavior = behavior_distribution(probs, "greedy", .1)
            action, draw = sample_with_receipt(behavior, rng)
            following, reward, done, truncated, info, checks = env.step(action)
            episode["steps"].append({
                "observation": copy.deepcopy(obs), "request": policy_request(obs, case["id"]),
                "pre_action_ammo": observed_ammo(obs), "action": action,
                "expert_argmax": expert_argmax(probs), "scores": probs,
                "policy_probs": probs, "policy_probs_raw": result["raw_probabilities"],
                "raw_probability_sum": result["raw_probability_sum"],
                "expert": {"probs": probs, "argmax": expert_argmax(probs), "raw_logits": result["logits"]},
                "behavior_probs": behavior, "sampling_draw": draw,
                "pixel_input": {k: result[k] for k in ("pixel_sha256", "resized_chw_sha256",
                    "normalized_input_sha256", "rnn_before_sha256", "rnn_after_sha256")},
                "reward": reward, "terminated": done, "truncated": truncated,
                "info": copy.deepcopy(info), "mirror_tick_checks": checks,
                "next_observation_sha256": digest(following)})
            obs = following
        episode.update(complete=True, success=info["success"], final_info=copy.deepcopy(info),
            final_observation=copy.deepcopy(obs),
            mirrored_physical_ticks=sum(len(s["mirror_tick_checks"]) for s in episode["steps"]),
            inference_counts={"actual_expert_forward_calls": actor.forward_count-forwards,
                              "actual_recurrent_resets": actor.reset_count-resets})
        validate(episode, .1)
        return episode
    finally:
        env.close()


def validate(episode, epsilon):
    require_dev(episode["case"])
    case, steps, final = episode["case"], episode["steps"], episode["final_info"]
    if (episode.get("complete") is not True or type(episode.get("success")) is not bool or
            not final["terminated"] or final["truncated"] or not steps or
            final["success"] != episode["success"] or
            episode["success"] != (final["episode_metrics"]["kills"] > 0) or
            episode["final_observation"]["candidates"]):
        raise ValueError("Incomplete or inconsistent genuine terminal outcome")
    rng = random.Random(int(digest([case["id"], 17])[:16], 16))
    previous, ticks = episode["mirror_initial"]["initial_physics"], 0
    for i, step in enumerate(steps):
        obs = step["observation"]
        if (set(obs["candidates"]) != set(ACTIONS) or observed_ammo(obs) != step["pre_action_ammo"] or
                step["request"] != policy_request(obs, case["id"]) or
                (i == 0 and obs != episode["initial_observation"])):
            raise ValueError("Public observation or request changed")
        probs = probability_check({"probabilities": step["policy_probs"],
            "raw_probabilities": step["policy_probs_raw"], "logits": step["expert"]["raw_logits"],
            "raw_probability_sum": step["raw_probability_sum"]})
        if step["expert_argmax"] != expert_argmax(probs):
            raise ValueError("Expert argmax changed")
        behavior = behavior_distribution(probs, "greedy", epsilon)
        action, draw = sample_with_receipt(behavior, rng)
        if (step["behavior_probs"], step["action"], step["sampling_draw"]) != (behavior, action, draw):
            raise ValueError("Action does not match the fixed per-case controller RNG")
        checks = step["mirror_tick_checks"]
        if not 1 <= len(checks) <= 4 or len(checks) != step["info"]["actual_ticks"]:
            raise ValueError("Incorrect physical tick duration")
        for check in checks:
            ticks += 1
            if check["tick_index"] != ticks or check["before_sha256"] != digest(previous):
                raise ValueError("Broken mirrored physical audit chain")
            previous = check["after"]
        if not math.isclose(math.fsum(c["reward"] for c in checks), step["reward"], abs_tol=1e-10):
            raise ValueError("Per-tick reward differs")
        following = steps[i+1]["observation"] if i+1 < len(steps) else episode["final_observation"]
        if digest(following) != step["next_observation_sha256"] or step["truncated"] or step["terminated"] != (i == len(steps)-1):
            raise ValueError("Broken visible observation or terminal chain")
        if i and step["pixel_input"]["rnn_before_sha256"] != steps[i-1]["pixel_input"]["rnn_after_sha256"]:
            raise ValueError("Broken RNN state chain")
    if ticks != episode["mirrored_physical_ticks"] or ticks != final["episode_metrics"]["physical_ticks"]:
        raise ValueError("Physical tick totals disagree")


def episode_diagnostic(episode):
    first_command, first_consumption = None, None
    tick = 0
    non_argmax = pre_ammo_non_argmax = 0
    for i, step in enumerate(episode["steps"]):
        different = step["action"] != step["expert_argmax"]
        non_argmax += different
        pre_ammo_non_argmax += different and step["pre_action_ammo"] > 0
        detail = {"decision_index": i, "start_physical_tick": tick,
                  "action": step["action"], "expert_argmax": step["expert_argmax"],
                  "pre_action_ammo": step["pre_action_ammo"], "non_argmax": different}
        if step["action"] == "shoot" and first_command is None:
            first_command = detail
        previous_ammo = step["pre_action_ammo"]
        for check in step["mirror_tick_checks"]:
            tick = check["tick_index"]
            current = check["after"]["variables"]["SELECTED_WEAPON_AMMO"]
            if current < previous_ammo and first_consumption is None:
                first_consumption = {**detail, "consumption_physical_tick": tick,
                                     "ammo_before": previous_ammo, "ammo_after": current}
            previous_ammo = current
    return {"id": episode["case"]["id"], "success": episode["success"],
            "decisions": len(episode["steps"]), "physical_ticks": episode["mirrored_physical_ticks"],
            "non_argmax_decisions": non_argmax, "pre_ammo_non_argmax_decisions": pre_ammo_non_argmax,
            "positive_ammo_decisions": sum(s["pre_action_ammo"] > 0 for s in episode["steps"]),
            "first_shoot_command": first_command, "first_ammo_consumption": first_consumption}


def compare(reference, evaluated):
    pairs = []
    for old, new in zip(reference, evaluated):
        if old["case"] != new["case"] or old["mirror_initial"] != new["mirror_initial"]:
            raise ValueError("Reference and epsilon .1 did not start in identical physical/rendering conditions")
        left, right = episode_diagnostic(old), episode_diagnostic(new)
        old_tick = left["first_ammo_consumption"]
        new_tick = right["first_ammo_consumption"]
        delta = (new_tick["consumption_physical_tick"]-old_tick["consumption_physical_tick"]
                 if old_tick and new_tick else None)
        pairs.append({"id": old["case"]["id"], "epsilon_0": left, "epsilon_0_1": right,
                      "first_consumption_tick_delta": delta})
    cells = Counter((p["epsilon_0"]["success"], p["epsilon_0_1"]["success"]) for p in pairs)
    aggregates = {}
    for label in ("epsilon_0", "epsilon_0_1"):
        rows = [p[label] for p in pairs]
        decisions = sum(r["decisions"] for r in rows)
        positive = sum(r["positive_ammo_decisions"] for r in rows)
        aggregates[label] = {"episodes": len(rows), "successes": sum(r["success"] for r in rows),
            "decisions": decisions, "non_argmax_decisions": sum(r["non_argmax_decisions"] for r in rows),
            "non_argmax_rate": sum(r["non_argmax_decisions"] for r in rows)/decisions,
            "positive_ammo_decisions": positive,
            "pre_ammo_non_argmax_decisions": sum(r["pre_ammo_non_argmax_decisions"] for r in rows),
            "first_shoot_command_non_argmax_episodes": sum(bool(r["first_shoot_command"] and r["first_shoot_command"]["non_argmax"]) for r in rows),
            "first_consumption_non_argmax_episodes": sum(bool(r["first_ammo_consumption"] and r["first_ammo_consumption"]["non_argmax"]) for r in rows)}
    return {"aggregates": aggregates,
        "paired_success": {"both_success": cells[True, True], "epsilon_0_only": cells[True, False],
                           "epsilon_0_1_only": cells[False, True], "both_failure": cells[False, False]},
        "first_consumption_timing": {"earlier": sum(p["first_consumption_tick_delta"] is not None and p["first_consumption_tick_delta"] < 0 for p in pairs),
            "same": sum(p["first_consumption_tick_delta"] == 0 for p in pairs),
            "later": sum(p["first_consumption_tick_delta"] is not None and p["first_consumption_tick_delta"] > 0 for p in pairs),
            "not_comparable": sum(p["first_consumption_tick_delta"] is None for p in pairs)},
        "cases": pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cases", "reference-dev-episodes", "protocol", "checkpoint", "expert-config", "old-game-wad", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh diagnostic output directory")
    cases, reference = read_rows(args.cases), read_rows(args.reference_dev_episodes)
    expected_ids = [f"dev-sonic_predict_position-{seed}" for seed in range(9300512, 9300576)]
    if len(cases) != 64 or [c["id"] for c in cases] != expected_ids or [e["case"] for e in reference] != cases:
        parser.error("Require exactly the 64 original PP dev cases and their ordered epsilon-zero reference")
    for case, episode in zip(cases, reference):
        require_dev(case)
        if case["seed"] != int(case["id"].rsplit("-", 1)[1]):
            raise ValueError("Case seed differs from its registered identity")
        validate(episode, 0.0)
        if episode["standard_independent_replay"].get("passed") is not True:
            raise ValueError("Original dev reference lacks independent replay")
    protocol = json.loads(args.protocol.read_text())
    actor, identity = load_policy(args.checkpoint, args.expert_config, protocol, "cpu")
    sources = {name: file_digest(Path(__file__).with_name(name)) for name in (*SOURCES, Path(__file__).name)}
    declaration = {"engine": "sonic_doom_pure_vision_pp", "model": identity,
        "controller": "greedy", "epsilon": .1, "sampling_seed": 17,
        "tie_break": "lexicographic_first", "source_sha256": sources,
        "input_role": "Expert RGB/RNN; student text is recorded but is not the expert input",
        "scope": "Development-only controller diagnostic; no training or test selection"}
    policy_id = digest(declaration)
    args.output.mkdir(parents=True)
    manifest = {"finished": False, "cases_sha256": file_digest(args.cases),
        "reference_dev_sha256": file_digest(args.reference_dev_episodes), "policy": declaration,
        "continuation_policy_id": policy_id, "selected_cases": expected_ids}
    write_json(args.output / "manifest.json", manifest)
    collected, start = [], time.monotonic()
    try:
        with (args.output / "episodes.jsonl").open("x") as handle:
            for case in cases:
                episode = collect(case, actor, policy_id, args.old_game_wad)
                episode["standard_independent_replay"] = replay_standard(episode)
                handle.write(encode(episode) + "\n")
                handle.flush()
                collected.append(episode)
                print(encode({"id": case["id"], "success": episode["success"], "completed": len(collected)}), flush=True)
        summary = compare(reference, collected)
        summary.update(scope=declaration["scope"], input_role=declaration["input_role"],
                       epsilon_fixed_before_results=.1, sampling_seed=17,
                       first_shot_interpretation="Shoot commands and actual ammo consumption are reported separately; weapon animation can delay consumption, so the action during consumption is not necessarily its cause.",
                       all_physical_mirrors_and_independent_replays_passed=True)
        write_json(args.output / "summary.json", summary)
        manifest.update(finished=True, episodes=64, actual_forward_calls=actor.forward_count,
                        recurrent_resets=actor.reset_count, elapsed_seconds=time.monotonic()-start,
                        episode_sha256=file_digest(args.output / "episodes.jsonl"),
                        summary_sha256=file_digest(args.output / "summary.json"))
    finally:
        write_json(args.output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
