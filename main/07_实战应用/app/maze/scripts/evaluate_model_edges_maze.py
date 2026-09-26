#!/usr/bin/env python3
"""Model-guided local-edge exploration, separate from diagnostic code planning.

Only MazeEnvironment owns full walls. EdgeExplorer receives coordinates, model
safety probabilities, and actual transition feedback. It prioritizes untried
edges predicted open, probes remaining low-probability edges when necessary,
and uses BFS only on physically verified open edges to reach a known frontier.
There is no full-map solver, safe-action oracle, or hidden route fallback.
"""

import argparse
from collections import deque
import copy
import hashlib
import json
import math
from pathlib import Path
import time

from evaluate_composed_maze import (
    EPSILON, ReferenceDiagnostics, _validate_answer, digest, file_digest,
    local_questions, local_truth, render_local_request,
)
from scaled_maze import DIRECTIONS, validate_state


def destination(position, action):
    dr, dc = DIRECTIONS[action]
    return position[0] + dr, position[1] + dc


def edge_key(first, second):
    return tuple(sorted((tuple(first), tuple(second))))


class MazeEnvironment:
    """Simulator boundary: geometry enters observations and transition feedback."""

    def __init__(self, initial, window_size=5):
        validate_state(initial)
        self._initial = {key: copy.deepcopy(initial[key]) for key in
                         ("game", "size", "walls", "position", "goal", "seed", "topology") if key in initial}
        self._state = copy.deepcopy(self._initial)
        self._walls = set(map(tuple, initial["walls"]))
        self.window_size = window_size

    def public_coordinates(self):
        return {"position": tuple(self._state["position"]), "goal": tuple(self._state["goal"]), "size": self._state["size"]}

    def observe(self):
        return render_local_request(self._state, self.window_size)

    def reached_goal(self):
        return tuple(self._state["position"]) == tuple(self._state["goal"])

    def attempt(self, action):
        if action not in DIRECTIONS:
            raise ValueError("Unknown direction")
        before = tuple(self._state["position"])
        dest = destination(before, action)
        size = self._state["size"]
        reason = ("boundary" if not all(0 <= value < size for value in dest)
                  else "wall" if dest in self._walls else None)
        if reason is None:
            self._state["position"] = list(dest)
        return {"position": list(before), "next_position": list(self._state["position"]),
                "collision": reason is not None, "collision_reason": reason, "goal_reached": self.reached_goal()}

    def initial_geometry_for_report(self):
        return copy.deepcopy(self._initial)


class EdgeExplorer:
    """Policy state contains no environment, wall map, renderer, or oracle handle."""

    def __init__(self, position, goal, size):
        self.position, self.goal, self.size = tuple(position), tuple(goal), size
        self.predictions = {}
        self.edges = {}
        self.adjacency = {self.position: set()}
        self.visits = {self.position: 1}

    def needs_prediction(self):
        return self.position not in self.predictions

    def remember_prediction(self, probabilities):
        if set(probabilities) != set(DIRECTIONS) or any(
                type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()):
            raise ValueError("Expected four finite direction probabilities")
        self.predictions[self.position] = dict(probabilities)

    def untried(self, position):
        return [action for action in DIRECTIONS if edge_key(position, destination(position, action)) not in self.edges]

    def _rank(self, action, low_probability=False):
        dest = destination(self.position, action)
        distance = sum(abs(a - b) for a, b in zip(dest, self.goal))
        probability, visits = self.predictions[self.position][action], self.visits.get(dest, 0)
        order = list(DIRECTIONS).index(action)
        # Once predicted open, prefer goal progress over tiny confidence changes.
        # With no predicted-open edge, probe the strongest remaining prediction.
        return (-probability, distance, visits, order) if low_probability else (distance, visits, -probability, order)

    def choose(self):
        if self.needs_prediction():
            raise RuntimeError("A local prediction is required before choosing an edge")
        unknown = self.untried(self.position)
        if unknown:
            high = [action for action in unknown if self.predictions[self.position][action] >= 0.5]
            candidates, mode = (high, "model_predicted_open") if high else (unknown, "low_probability_probe")
            action = min(candidates, key=lambda item: self._rank(item, low_probability=not high))
            return {"action": action, "mode": mode, "predicted_safe_probability": self.predictions[self.position][action],
                    "untried_edge": True}
        # Reposition exclusively on edges already traversed without collision.
        predecessor, queue, target = {self.position: None}, deque([self.position]), None
        while queue:
            node = queue.popleft()
            if node != self.position and self.untried(node):
                target = node
                break
            for action in DIRECTIONS:
                nxt = destination(node, action)
                if nxt in self.adjacency.get(node, set()) and nxt not in predecessor:
                    predecessor[nxt] = node, action
                    queue.append(nxt)
        if target is None:
            return None
        route = []
        while predecessor[target] is not None:
            target, action = predecessor[target]
            route.append(action)
        action = route[-1]
        return {"action": action, "mode": "verified_edge_reposition", "untried_edge": False,
                "predicted_safe_probability": self.predictions[self.position][action]}

    def observe_transition(self, action, next_position, collision):
        dest = destination(self.position, action)
        key, old = edge_key(self.position, dest), self.position
        status = "blocked" if collision else "open"
        if key in self.edges and self.edges[key] != status:
            raise RuntimeError("Static-maze edge feedback changed")
        if collision:
            if tuple(next_position) != old:
                raise RuntimeError("A collision must preserve position")
        else:
            if tuple(next_position) != dest:
                raise RuntimeError("Transition feedback disagrees with attempted direction")
            self.adjacency.setdefault(old, set()).add(dest)
            self.adjacency.setdefault(dest, set()).add(old)
            self.position = dest
            self.visits[dest] = self.visits.get(dest, 0) + 1
        self.edges[key] = status


def score_atomic(observations):
    correct, brier, nll, count = 0, 0.0, 0.0, 0
    for row in observations:
        for action in DIRECTIONS:
            p, truth = row["probabilities"][action], row["truth"][action]
            correct += int((p >= .5) == truth)
            brier += (p - int(truth)) ** 2
            nll -= math.log(max(EPSILON, p if truth else 1 - p))
            count += 1
    return {"atomic_questions": count, "prediction_sites": len(observations),
            "atomic_accuracy": correct / count if count else None,
            "atomic_brier": brier / count if count else None,
            "atomic_nll": nll / count if count else None}


class ConstantDiagnostics:
    """Information-free p=0.5 baseline: never inspect local state or its truth."""

    def predict(self, payload, **kwargs):
        return {"states": [{"id": row["id"], "answers": {
            qid: {"type": "boolean", "p_true": .5, "probabilities": {"false": .5, "true": .5}}
            for qid in local_questions()}} for row in payload["states"]],
            "execution": {"forward_passes": 0, "network_model_calls": 0}}


def run_exploration(episodes, engine, window_size=5, max_steps=0, batch_states=2, batch_questions=0):
    if type(max_steps) is not int or max_steps < 0 or type(batch_states) is not int or batch_states < 1:
        raise ValueError("Invalid exploration horizon or state batch")
    if type(batch_questions) is not int or batch_questions < 0 or window_size not in (3, 5):
        raise ValueError("Invalid question batch or local window")
    if len({row["id"] for row in episodes}) != len(episodes):
        raise ValueError("Duplicate episode IDs")
    started, sessions = time.perf_counter(), []
    for source in episodes:
        env = MazeEnvironment(source["initial_state"], window_size)
        coordinates = env.public_coordinates()
        policy = EdgeExplorer(**coordinates)
        sessions.append({"source": source, "env": env, "policy": policy,
                         "horizon": max_steps or 2 * coordinates["size"] ** 2,
                         "status": None, "steps": [], "observations": []})
    execution = {"predict_calls": 0, "model_forward_passes": 0, "network_model_calls": 0}
    audit_inputs = []
    while any(session["status"] is None for session in sessions):
        pending = []
        for index, session in enumerate(sessions):
            if session["status"] is not None:
                continue
            env, policy = session["env"], session["policy"]
            if env.reached_goal():
                session["status"] = "goal"
            elif len(session["steps"]) >= session["horizon"]:
                session["status"] = "horizon_exhausted"
            elif policy.needs_prediction():
                public = env.observe()
                request = {"id": f"{session['source']['id']}:node:{policy.position[0]},{policy.position[1]}", **public}
                pending.append((index, request))
        for offset in range(0, len(pending), batch_states):
            batch = pending[offset:offset + batch_states]
            requests = [request for _, request in batch]
            audit_inputs.extend(copy.deepcopy(requests))
            response = engine.predict({"states": copy.deepcopy(requests)}, batch_questions=batch_questions, temperature=1.0)
            returned = response.get("states", [])
            ids = [row.get("id") for row in returned]
            if len(ids) != len(set(ids)) or set(ids) != {row["id"] for row in requests}:
                raise ValueError("Local-edge response IDs mismatch")
            indexed = {row["id"]: row for row in returned}
            for index, request in batch:
                session = sessions[index]
                answers = indexed[request["id"]].get("answers")
                if not isinstance(answers, dict) or set(answers) != set(local_questions()):
                    raise ValueError("Local-edge question coverage mismatch")
                probabilities = {action: _validate_answer(answers["clear_" + action]) for action in DIRECTIONS}
                session["policy"].remember_prediction(probabilities)
                # Evaluation-only truth is never passed to EdgeExplorer.
                receipts = {qid: {key: answer[key] for key in (
                    "native_probabilities", "native_sum", "normalization_applied", "target_kind",
                    "source_api_call_id", "source_input_sha256", "cache_hit") if key in answer}
                    for qid, answer in answers.items()}
                session["observations"].append({"id": request["id"], "position": list(session["policy"].position),
                    "local_state": request["state"], "input_sha256": digest(request),
                    "probabilities": probabilities, "truth": local_truth(request), "primitive_receipts": receipts})
            execution["predict_calls"] += 1
            counts = response.get("execution", {})
            execution["network_model_calls"] += counts.get("network_model_calls", 0) or 0
            forwards = counts.get("forward_passes")
            if forwards is None:
                execution["model_forward_passes"] = None
            elif execution["model_forward_passes"] is not None:
                execution["model_forward_passes"] += forwards
            if "cumulative_cost_usd" in counts:
                execution["cumulative_api_cost_usd"] = counts["cumulative_cost_usd"]
        for session in sessions:
            if session["status"] is not None:
                continue
            policy = session["policy"]
            decision = policy.choose()
            if decision is None:
                session["status"] = "frontier_exhausted"
                continue
            feedback = session["env"].attempt(decision["action"])
            policy.observe_transition(decision["action"], feedback["next_position"], feedback["collision"])
            session["steps"].append({"step_index": len(session["steps"]), **decision, **feedback})
    results, observations = [], []
    for session in sessions:
        source, policy, trace = session["source"], session["policy"], session["steps"]
        local_observations = session["observations"]
        probes = sum(row["mode"] == "low_probability_probe" for row in trace)
        collisions = sum(row["collision"] for row in trace)
        verified = [{"cells": [list(cell) for cell in cells], "status": status} for cells, status in sorted(policy.edges.items())]
        row = {"id": source["id"], "split": source["split"], "size": policy.size,
               "initial_state": session["env"].initial_geometry_for_report(), "status": session["status"],
               "goal_completion": session["status"] == "goal", "horizon": session["horizon"],
               "attempts": len(trace), "successful_moves": len(trace) - collisions, "collisions": collisions,
               "probe_count": probes, "fallback_count": probes,
               "verified_edge_reposition_count": sum(item["mode"] == "verified_edge_reposition" for item in trace),
               "visited_cells": len(policy.visits), "revisited_cell_entries": sum(count - 1 for count in policy.visits.values()),
               "steps": trace, "observations": local_observations, "verified_edges": verified,
               "atomic_metrics": score_atomic(local_observations)}
        results.append(row)
        observations.extend(local_observations)
    summary = {"episodes": len(results), "goal_completed": sum(row["goal_completion"] for row in results),
               "goal_completion_rate": sum(row["goal_completion"] for row in results) / len(results) if results else None,
               **{name: sum(row[name] for row in results) for name in
                  ("attempts", "successful_moves", "collisions", "probe_count", "fallback_count", "verified_edge_reposition_count")},
               **score_atomic(observations)}
    return {"schema": "nanojev-model-edges-maze-v1", "model_role": "model_guided_local_edge_exploration",
            "model_controls": "ordering of untried local edges via predicted safety; code applies exploration and verified-edge repositioning",
            "protocol": {"window_size": window_size, "max_steps": max_steps, "default_horizon": "2*size^2 attempts including collisions",
                         "threshold": .5, "temperature": 1.0, "prediction_cache": "once per visited coordinate in a static maze",
                         "selection_rule": "untried p>=0.5 edges first; goal Manhattan distance, destination visits, descending p, N/E/S/W",
                         "probe_rule": "if all untried edges have p<0.5, physically attempt by descending p, goal Manhattan distance, destination visits, N/E/S/W",
                         "reposition_rule": "BFS to nearest frontier using only physically traversed open edges",
                         "collision_rule": "nonfatal; preserve position; mark the undirected edge blocked and never retry it",
                         "fallback_definition": "low-probability probes only; no full-map route or safe-action fallback",
                         "memory_termination": "all frontiers exhausted, goal reached, or attempt budget exhausted",
                         "oracle_used_for_policy": False, "full_map_bfs_used": False,
                         "atomic_metric_scope": "first-visit states chosen by this model-guided trajectory; not an identical cross-model audit cohort",
                         "brier_definition": "mean scalar Bernoulli squared error", "nll_probability_floor": EPSILON},
            "audit_inputs_sha256": digest(audit_inputs), "summary": summary, "execution": execution,
            "elapsed_seconds": time.perf_counter() - started, "question_template": local_questions(), "episodes": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--engine", required=True, choices=("checkpoint", "jev", "reference", "constant"))
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--env-file")
    parser.add_argument("--journal-dir", type=Path)
    parser.add_argument("--budget-usd", type=float, default=1.0)
    parser.add_argument("--splits", default="test,ood")
    parser.add_argument("--window-size", type=int, choices=(3, 5), default=5)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--batch-states", type=int, default=2)
    parser.add_argument("--batch-questions", type=int, default=0)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--precision", choices=("bf16", "fp32"), default="bf16")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new output file")
    if args.max_steps < 0 or args.batch_states < 1 or args.batch_questions < 0 or args.max_length < 1:
        parser.error("Invalid horizon, batch, or context limit")
    source = args.episodes.read_bytes()
    splits = {value.strip() for value in args.splits.split(",") if value.strip()}
    selected = [row for row in map(json.loads, filter(str.strip, source.decode().splitlines()))
                if row["game"] == "scaled_maze" and row["split"] in splits]
    if not selected:
        raise ValueError("No selected maze episodes")
    engine, identity = None, {"engine": args.engine}
    try:
        if args.engine == "checkpoint":
            if args.checkpoint is None:
                parser.error("--checkpoint is required")
            from predict_toy_decisions import DecisionPredictor
            identity.update(checkpoint=str(args.checkpoint), checkpoint_sha256=file_digest(args.checkpoint / "best.safetensors"))
            engine = DecisionPredictor(args.checkpoint, max_length=args.max_length, precision=args.precision, disable_native_triton=True)
        elif args.engine == "jev":
            if not args.env_file or args.journal_dir is None or not math.isfinite(args.budget_usd) or not 0 < args.budget_usd <= 24:
                parser.error("Jev requires credentials/journal paths and a budget in (0,24]")
            from evaluate_scaled_games import LiveJev
            engine = LiveJev(args.env_file, args.journal_dir, args.budget_usd)
            identity["model"] = "typesafe-ai/jev"
        elif args.engine == "reference":
            engine = ReferenceDiagnostics()
        else:
            engine = ConstantDiagnostics()
            identity["constant_probability"] = .5
        result = run_exploration(selected, engine, args.window_size, args.max_steps, args.batch_states, args.batch_questions)
        result.update(model=identity, selected_episode_ids=[row["id"] for row in selected],
                      source_episodes_sha256=hashlib.sha256(source).hexdigest(),
                      implementation_sha256=file_digest(Path(__file__)),
                      local_renderer_sha256=file_digest(Path(__file__).with_name("evaluate_composed_maze.py")),
                      selection="all maze episodes in requested splits; original order; no outcome-based filtering")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "model_role": result["model_role"], "summary": result["summary"], "execution": result["execution"]}))
    finally:
        if args.engine == "jev" and engine is not None:
            engine.close()


if __name__ == "__main__":
    main()
