#!/usr/bin/env python3
"""Execute exact code-planned mazes and independently audit local model judgments.

The model is diagnostic_only: it cannot choose, veto, or modify executed actions.
Code sees the complete geometry, executes a deterministic BFS shortest route,
checks every transition, and remembers visited cells. Only scheduled local ASCII
windows are sent to the model, batched after that code-executed trajectory is
frozen. Planner completion is never credited to model capability.

Example (standard library, no API/GPU):
  python3 scripts/evaluate_composed_maze.py \
    --episodes data/scaled_games_v4/rollout_pilot.jsonl \
    --engine reference --output results/composed_reference.json

audit-every=8 audits steps 0,8,16,...; audit-every=1 audits every executed move.
All selected maze episodes run their full finite path; there is no horizon cap.
"""

import argparse
from collections import deque
import copy
import hashlib
import json
import math
from pathlib import Path
import time

from scaled_maze import DIRECTIONS, step, valid_actions, validate_state


EPSILON = 1e-12
MODEL_ROLE = "diagnostic_only"
DELTAS = {"north": "row minus one, same column", "east": "same row, column plus one",
          "south": "row plus one, same column", "west": "same row, column minus one"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def local_questions():
    questions = {}
    for action in DIRECTIONS:
        questions["clear_" + action] = {
            "type": "boolean",
            "instructions": f"If the agent attempts one cell {action} ({DELTAS[action]}), "
                "will the destination be inside the maze and not a wall? "
                "Use the local map: '.' and 'A' are traversable, '#' is a wall, and 'X' is outside the maze.",
            "criteria": {
                "true": f"The destination of the one-cell {action} attempt is inside the maze and traversable.",
                "false": f"The destination of the one-cell {action} attempt is a wall or outside the maze."}}
    return questions


def render_local_request(state, window_size=5):
    """Render visible local geometry only, including out-of-board X cells."""
    validate_state(state)
    if window_size not in (3, 5):
        raise ValueError("Local window size must be 3 or 5")
    row, col = state["position"]
    size, radius = state["size"], window_size // 2
    walls = set(map(tuple, state["walls"]))
    lines = []
    for r in range(row - radius, row + radius + 1):
        line = []
        for c in range(col - radius, col + radius + 1):
            char = "X" if not (0 <= r < size and 0 <= c < size) else "#" if (r, c) in walls else "."
            line.append("A" if (r, c) == (row, col) else char)
        lines.append("".join(line))
    text = (f"Agent coordinate: ({row},{col}); zero-based row and column. "
            "Rows increase south; columns increase east. "
            "The local window is centered on A. '#': wall; '.': open; 'A': agent; 'X': outside.\n"
            "Local map:\n" + "\n".join(lines))
    return {"state": text, "questions": local_questions()}


def local_truth(public):
    """Exact atomic reference from the same local ASCII the model receives."""
    lines = public["state"].split("Local map:\n", 1)[1].splitlines()
    if len(lines) not in (3, 5) or any(len(line) != len(lines) or set(line) - set(".#AX") for line in lines):
        raise ValueError("Malformed local window")
    center = len(lines) // 2
    if lines[center][center] != "A":
        raise ValueError("The agent must be at the local window center")
    return {action: lines[center + dr][center + dc] in ".A" for action, (dr, dc) in DIRECTIONS.items()}


def plan_shortest_path(state):
    """Deterministic BFS route using full geometry; return None when unreachable."""
    validate_state(state)
    start, goal = tuple(state["position"]), tuple(state["goal"])
    size, walls = state["size"], set(map(tuple, state["walls"]))
    predecessor, queue = {start: None}, deque([start])
    while queue and goal not in predecessor:
        cell = queue.popleft()
        for action, (dr, dc) in DIRECTIONS.items():
            dest = cell[0] + dr, cell[1] + dc
            if (0 <= dest[0] < size and 0 <= dest[1] < size and dest not in walls
                    and dest not in predecessor):
                predecessor[dest] = cell, action
                queue.append(dest)
    if goal not in predecessor:
        return None
    actions, cell = [], goal
    while predecessor[cell] is not None:
        cell, action = predecessor[cell]
        actions.append(action)
    return list(reversed(actions))


def prepare_trajectories(episodes, audit_every=8, window_size=5):
    """Execute code routes and freeze identical audit observations for every engine."""
    if type(audit_every) is not int or audit_every < 1:
        raise ValueError("audit_every must be a positive integer")
    if window_size not in (3, 5):
        raise ValueError("Local window size must be 3 or 5")
    trajectories, audits, seen_ids = [], [], set()
    for source in episodes:
        if source["id"] in seen_ids:
            raise ValueError("Duplicate episode ID")
        seen_ids.add(source["id"])
        initial = source["initial_state"]
        validate_state(initial)
        actions = plan_shortest_path(initial)
        current, trace, seen = copy.deepcopy(initial), [], {tuple(initial["position"])}
        episode_audits = []
        for index, action in enumerate(actions or []):
            if action not in valid_actions(current):
                raise RuntimeError("Code planner proposed an illegal action")
            audit_id = None
            if index % audit_every == 0:
                audit_id = f"{source['id']}:step:{index}"
                public = render_local_request(current, window_size)
                # Ground truth and selected action remain outside the model payload.
                truth = local_truth(public)
                if not truth[action]:
                    raise RuntimeError("Planner and local geometry disagree")
                audits.append({"id": audit_id, "episode_id": source["id"], "step_index": index,
                               "position": list(current["position"]), "planner_action": action,
                               "request": {"id": audit_id, **public}, "truth": truth})
                episode_audits.append(audit_id)
            following = step(current, action)
            position = tuple(following["position"])
            if position in seen:
                raise RuntimeError("Code planner revisited a cell")
            seen.add(position)
            trace.append({"step_index": index, "position": list(current["position"]),
                          "planner_action": action, "next_position": list(position), "audit_id": audit_id})
            current = following
        completed = tuple(current["position"]) == tuple(initial["goal"])
        geometry = {key: copy.deepcopy(initial[key]) for key in
                    ("game", "size", "walls", "position", "goal", "seed", "topology") if key in initial}
        trajectories.append({"id": source["id"], "split": source["split"], "game": "scaled_maze",
                             "size": initial["size"], "topology": initial.get("topology"),
                             "initial_state": geometry, "steps": trace, "audit_ids": episode_audits,
                             "planner_completion": completed,
                             "planner_status": "goal" if completed else "unreachable",
                             "shortest_path_length": None if actions is None else len(actions),
                             "executed_steps": len(trace),
                             "path_efficiency": (len(actions) / len(trace) if trace else 1.0) if completed else None,
                             "visited_cells": len(seen), "loop_count": 0, "override_count": 0})
    return trajectories, audits


class ReferenceDiagnostics:
    """A local-geometry reference, not a learned model or a route controller."""

    def predict(self, payload, **kwargs):
        states = []
        for row in payload["states"]:
            truth = local_truth(row)
            answers = {"clear_" + action: {"type": "boolean", "p_true": float(value),
                       "probabilities": {"false": float(not value), "true": float(value)}}
                       for action, value in truth.items()}
            states.append({"id": row["id"], "answers": answers})
        return {"states": states, "execution": {"network_model_calls": 0, "forward_passes": 0}}


def _validate_answer(answer):
    if not isinstance(answer, dict) or answer.get("type") != "boolean":
        raise ValueError("Expected a Boolean diagnostic answer")
    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != {"false", "true"}:
        raise ValueError("Boolean probabilities must cover false and true exactly")
    if any(type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()):
        raise ValueError("Invalid Boolean probability")
    if abs(math.fsum(probabilities.values()) - 1.0) > 1e-6:
        raise ValueError("Boolean probabilities do not sum to one")
    p = probabilities["true"]
    if "p_true" in answer:
        value = answer["p_true"]
        if type(value) not in (float, int) or not math.isfinite(value) or abs(value - p) > 1e-6:
            raise ValueError("p_true disagrees with the full distribution")
    return float(p)


def atomic_metrics(audits):
    correct, brier, nll, questions, disagreement = 0, 0.0, 0.0, 0, 0
    for row in audits:
        for action in DIRECTIONS:
            p, y = row["probabilities"][action], int(row["truth"][action])
            correct += int((p >= 0.5) == bool(y))
            brier += (p - y) ** 2
            nll -= math.log(max(EPSILON, p if y else 1 - p))
            questions += 1
        disagreement += int(row["probabilities"][row["planner_action"]] < 0.5)
    return {"atomic_questions": questions, "audited_states": len(audits),
            "atomic_accuracy": correct / questions if questions else None,
            "atomic_brier": brier / questions if questions else None,
            "atomic_nll": nll / questions if questions else None,
            "model_vs_planner_disagreement": disagreement / len(audits) if audits else None,
            "would_veto_count": disagreement, "override_count": 0}


def evaluate_audits(audits, engine, batch_states=2, batch_questions=0):
    if type(batch_states) is not int or batch_states < 1 or type(batch_questions) is not int or batch_questions < 0:
        raise ValueError("Invalid diagnostic batch limits")
    completed = []
    execution = {"predict_calls": 0, "model_forward_passes": 0, "network_model_calls": 0,
                 "audit_states": len(audits), "atomic_questions": 4 * len(audits)}
    for offset in range(0, len(audits), batch_states):
        batch = audits[offset:offset + batch_states]
        response = engine.predict({"states": [copy.deepcopy(row["request"]) for row in batch]},
                                  batch_questions=batch_questions, temperature=1.0)
        rows = response.get("states")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Missing diagnostic response states")
        ids = [row.get("id") for row in rows]
        if len(ids) != len(set(ids)) or set(ids) != {row["id"] for row in batch}:
            raise ValueError("Diagnostic response IDs mismatch")
        indexed = {row["id"]: row for row in rows}
        for expected in batch:
            actual = indexed[expected["id"]]
            if not isinstance(actual.get("answers"), dict) or set(actual["answers"]) != set(local_questions()):
                raise ValueError("Diagnostic question set mismatch")
            probabilities = {action: _validate_answer(actual["answers"]["clear_" + action]) for action in DIRECTIONS}
            record = {key: copy.deepcopy(expected[key]) for key in
                      ("id", "episode_id", "step_index", "position", "planner_action", "truth")}
            record.update(local_state=expected["request"]["state"], input_sha256=digest(expected["request"]),
                          probabilities=probabilities,
                          planner_action_judged_safe=probabilities[expected["planner_action"]] >= 0.5)
            # Preserve native Boolean values when the gateway exposes them;
            # provider/account metadata is not copied into the public trace.
            raw = {action: actual["answers"]["clear_" + action]["native_probabilities"] for action in DIRECTIONS
                   if "native_probabilities" in actual["answers"]["clear_" + action]}
            if raw:
                record["native_probabilities"] = raw
            completed.append(record)
        counts = response.get("execution", {})
        execution["predict_calls"] += 1
        execution["network_model_calls"] += counts.get("network_model_calls", 0) or 0
        forwards = counts.get("forward_passes")
        if forwards is None:
            execution["model_forward_passes"] = None
        elif execution["model_forward_passes"] is not None:
            execution["model_forward_passes"] += forwards
        if "cumulative_cost_usd" in counts:
            execution["cumulative_api_cost_usd"] = counts["cumulative_cost_usd"]
    return completed, execution


def run_composed(episodes, engine, audit_every=8, window_size=5, batch_states=2, batch_questions=0):
    started = time.perf_counter()
    trajectories, requests = prepare_trajectories(episodes, audit_every, window_size)
    observations, execution = evaluate_audits(requests, engine, batch_states, batch_questions)
    for row in trajectories:
        row["atomic_metrics"] = atomic_metrics([a for a in observations if a["episode_id"] == row["id"]])
    efficiencies = [row["path_efficiency"] for row in trajectories if row["path_efficiency"] is not None]
    summary = {"episodes": len(trajectories), "planner_completed": sum(row["planner_completion"] for row in trajectories),
               "planner_completion_rate": sum(row["planner_completion"] for row in trajectories) / len(trajectories) if trajectories else None,
               "planner_steps": sum(row["executed_steps"] for row in trajectories),
               "path_efficiency": math.fsum(efficiencies) / len(efficiencies) if efficiencies else None,
               "path_efficiency_episodes": len(efficiencies), **atomic_metrics(observations)}
    return {"schema": "nanojev-composed-maze-v1", "model_role": MODEL_ROLE,
            "control_authority": "exact_full_map_code_planner", "audit_execution": "batched_diagnostics_on_code_executed_trajectories",
            "planner": {"algorithm": "BFS", "direction_tie_order": list(DIRECTIONS),
                        "memory": "BFS predecessor map and visited execution cells", "horizon_cap": None},
            "protocol": {"audit_every": audit_every, "audit_step_rule": "step_index modulo audit_every equals zero; before the goal",
                         "window_size": window_size, "batch_states": batch_states, "batch_questions": batch_questions,
                         "threshold": 0.5, "temperature": 1.0, "temperature_fitted": False,
                         "model_receives": "agent coordinates and local ASCII only, plus four independent propositions",
                         "model_controls_actions": False,
                         "disagreement_definition": "fraction of audited planner moves assigned safety probability below 0.5",
                         "override_definition": "zero: the diagnostic model proposes no actions and has no veto authority",
                         "brier_definition": "mean scalar Bernoulli squared error, not two-class summed Brier",
                         "nll_probability_floor": EPSILON, "path_efficiency_definition": "shortest length / executed length on completed episodes; already at goal = 1"},
            "audit_inputs_sha256": digest([row["request"] for row in requests]),
            "planner_trajectories_sha256": digest([{k: row[k] for k in ("id", "initial_state", "steps")} for row in trajectories]),
            "question_template": local_questions(), "summary": summary, "execution": execution,
            "elapsed_seconds": time.perf_counter() - started, "episodes": trajectories, "audits": observations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--engine", choices=("checkpoint", "jev", "reference"), required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--env-file")
    parser.add_argument("--journal-dir", type=Path)
    parser.add_argument("--budget-usd", type=float, default=1.0)
    parser.add_argument("--splits", default="test,ood")
    parser.add_argument("--audit-every", type=int, default=8)
    parser.add_argument("--window-size", type=int, choices=(3, 5), default=5)
    parser.add_argument("--batch-states", type=int, default=2)
    parser.add_argument("--batch-questions", type=int, default=0)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--precision", choices=("bf16", "fp32"), default="bf16")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new output file")
    if min(args.audit_every, args.batch_states, args.max_length) < 1 or args.batch_questions < 0:
        parser.error("Invalid audit/batch/context limits")
    source = args.episodes.read_bytes()
    all_rows = [json.loads(line) for line in source.decode().splitlines() if line.strip()]
    splits = {part.strip() for part in args.splits.split(",") if part.strip()}
    selected = [row for row in all_rows if row["game"] == "scaled_maze" and row["split"] in splits]
    if not selected:
        raise ValueError("No selected maze episodes")
    engine, model_identity = None, {"engine": args.engine}
    try:
        if args.engine == "checkpoint":
            if args.checkpoint is None:
                parser.error("--checkpoint is required")
            from predict_toy_decisions import DecisionPredictor
            model_identity.update(checkpoint=str(args.checkpoint),
                                  checkpoint_sha256=file_digest(args.checkpoint / "best.safetensors"))
            engine = DecisionPredictor(args.checkpoint, max_length=args.max_length,
                                       precision=args.precision, disable_native_triton=True)
        elif args.engine == "jev":
            if not args.env_file or args.journal_dir is None or not math.isfinite(args.budget_usd) or not 0 < args.budget_usd <= 24:
                parser.error("Jev requires --env-file, --journal-dir, and a budget in (0,24]")
            from evaluate_scaled_games import LiveJev
            engine = LiveJev(args.env_file, args.journal_dir, args.budget_usd)
            model_identity["model"] = "typesafe-ai/jev"
        else:
            engine = ReferenceDiagnostics()
        result = run_composed(selected, engine, args.audit_every, args.window_size, args.batch_states, args.batch_questions)
        result.update(model=model_identity, selected_episode_ids=[row["id"] for row in selected],
                      selection="all maze episodes in requested splits; source order preserved; no outcome-based filtering",
                      source_episodes_sha256=hashlib.sha256(source).hexdigest(),
                      implementation_sha256=file_digest(Path(__file__)),
                      maze_environment_sha256=file_digest(Path(__file__).with_name("scaled_maze.py")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "model_role": MODEL_ROLE, "summary": result["summary"],
                          "audit_inputs_sha256": result["audit_inputs_sha256"], "execution": result["execution"]}))
    finally:
        if args.engine == "jev" and engine is not None:
            engine.close()


if __name__ == "__main__":
    main()
