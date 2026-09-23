#!/usr/bin/env python3
"""Run frozen held-out maze/Snake episodes with a local model, Jev, or controls."""
import argparse
from collections import defaultdict
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import time


class LiveJev:
    def __init__(self, env_file, journal_dir, budget):
        journal_dir.mkdir(parents=True, exist_ok=True)
        self.log = (journal_dir / "worker_stderr.log").open("a")
        self.process = subprocess.Popen(["node", f"--env-file={env_file}", str(Path(__file__).with_name("jev_navigation_worker.mjs")),
                                         "--journal-dir", str(journal_dir), "--budget-usd", str(budget), "--concurrency", "4"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1)

    def predict(self, payload, batch_questions=0, temperature=1.0):
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Jev worker exited; inspect its sanitized journal")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.log.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--episodes", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--engine", choices=["checkpoint", "jev", "random", "reference"], required=True)
    p.add_argument("--checkpoint")
    p.add_argument("--env-file")
    p.add_argument("--journal-dir", type=Path)
    p.add_argument("--budget-usd", type=float, default=1.0)
    p.add_argument("--splits", default="test,ood")
    p.add_argument("--limit-per-cell", type=int, default=2)
    p.add_argument("--max-steps", type=int, default=0, help="Explicit rollout horizon; 0 uses 2*size^2")
    p.add_argument("--max-length", type=int, default=8192)
    p.add_argument("--batch-questions", type=int, default=2)
    p.add_argument("--controller", choices=["greedy", "sample"], default="greedy")
    p.add_argument("--seed", type=int, default=17)
    args = p.parse_args()
    if args.engine == "random":
        args.controller = "sample"
    if args.limit_per_cell < 1 or args.max_steps < 0:
        p.error("Invalid cohort limit or horizon")
    out = Path(args.output)
    if out.exists():
        raise ValueError("Use a new output file")
    from scaled_maze import step as maze_step, solve as maze_solve, render_request as maze_render
    from snake_game import step as snake_step, render_request as snake_render, make_record as snake_record
    source = Path(args.episodes)
    all_episodes = [json.loads(line) for line in source.read_text().splitlines() if line]
    selected, counts = [], defaultdict(int)
    for episode in all_episodes:
        cell = (episode["split"], episode["game"], episode["size"], episode["initial_state"].get("topology", "snake"))
        if episode["split"] in args.splits.split(",") and counts[cell] < args.limit_per_cell:
            selected.append(copy.deepcopy(episode))
            counts[cell] += 1
    if not selected:
        raise ValueError("No selected held-out episodes")
    engine = None
    if args.engine == "checkpoint":
        if not args.checkpoint:
            p.error("--checkpoint is required")
        from predict_toy_decisions import DecisionPredictor
        engine = DecisionPredictor(args.checkpoint, max_length=args.max_length, disable_native_triton=True)
    elif args.engine == "jev":
        if not args.env_file or not args.journal_dir or not 0 < args.budget_usd <= 24:
            p.error("Jev requires --env-file, --journal-dir and a budget in (0,24]")
        engine = LiveJev(args.env_file, args.journal_dir, args.budget_usd)
    started = time.perf_counter()
    execution = {"backbone_forwards": 0 if args.engine == "checkpoint" else None, "network_calls": 0}
    for episode in selected:
        episode.update(state=copy.deepcopy(episode["initial_state"]), steps=[], horizon=args.max_steps or 2 * episode["size"]**2,
                       active=True)
        if episode["game"] == "scaled_maze":
            episode["initial_shortest_path"] = maze_solve(episode["state"])["distance"]
        episode["rng"] = random.Random(int(hashlib.sha256((episode["id"] + str(args.seed)).encode()).hexdigest()[:16], 16))
    try:
        while any(e["active"] for e in selected):
            pending, lookup, choices = [], {}, {}
            for i, episode in enumerate(selected):
                if not episode["active"]:
                    continue
                state = episode["state"]
                terminal = state["position"] == state["goal"] if episode["game"] == "scaled_maze" else state["done"]
                if terminal or len(episode["steps"]) >= episode["horizon"]:
                    episode["active"] = False
                    continue
                render = maze_render if episode["game"] == "scaled_maze" else snake_render
                public = render(state)
                if "action" not in public["questions"]:
                    from scaled_maze import valid_actions
                    actions = valid_actions(state)
                    if len(actions) != 1:
                        episode["active"] = False
                        episode["stop_reason"] = "no_legal_actions"
                        continue
                    choices[i] = ({actions[0]: 1.0}, "forced_move")
                elif engine:
                    request_id = episode["id"] + ":" + str(len(episode["steps"]))
                    pending.append({"id": request_id, **public})
                    lookup[request_id] = i
                else:
                    actions = list(public["questions"]["action"]["criteria"])
                    if args.engine == "random":
                        probabilities = {a: 1/len(actions) for a in actions}
                    elif episode["game"] == "scaled_maze":
                        optimal = maze_solve(state)["optimal_actions"]
                        probabilities = {a: float(a in optimal)/len(optimal) for a in actions}
                    else:
                        record = snake_record(state, episode["split"])
                        probabilities = record["gold_probs"]["action"]
                    choices[i] = (probabilities, args.engine)
            if pending:
                response = engine.predict({"states": pending}, batch_questions=args.batch_questions, temperature=1.0)
                ids = [r["id"] for r in response["states"]]
                if len(ids) != len(set(ids)) or set(ids) != set(lookup):
                    raise ValueError("Prediction IDs mismatch")
                execution["network_calls"] += response["execution"].get("network_model_calls", 0)
                if args.engine == "checkpoint":
                    execution["backbone_forwards"] += response["execution"]["forward_passes"]
                for row in response["states"]:
                    choices[lookup[row["id"]]] = (row["answers"]["action"]["probabilities"], args.engine)
            for i, (probabilities, actor) in choices.items():
                episode = selected[i]
                if episode["game"] == "scaled_maze":
                    from scaled_maze import valid_actions as offered_actions
                else:
                    from snake_game import valid_actions as offered_actions
                if set(probabilities) != set(offered_actions(episode["state"])):
                    raise ValueError("Returned probabilities must cover exactly the offered actions")
                total = sum(probabilities.values())
                if not math.isfinite(total) or abs(total - 1.0) > 1e-5 or any(type(x) not in {float, int} or not math.isfinite(x) or not 0 <= x <= 1 for x in probabilities.values()):
                    raise ValueError("Invalid action probabilities")
                actions = sorted(probabilities)
                if args.controller == "greedy":
                    action = max(actions, key=probabilities.__getitem__)
                else:
                    action = episode["rng"].choices(actions, weights=[probabilities[a] for a in actions])[0]
                before = episode["state"]
                optimal = maze_solve(before)["optimal_actions"] if episode["game"] == "scaled_maze" else None
                after = (maze_step if episode["game"] == "scaled_maze" else snake_step)(before, action)
                episode["steps"].append({"action": action, "probabilities": probabilities, "actor": actor,
                                         "optimal_action": action in optimal if optimal is not None else None,
                                         "state": before, "next_state": after})
                episode["state"] = after
        for episode in selected:
            state = episode.pop("state")
            episode.pop("active"); episode.pop("rng")
            episode["final_state"] = state
            episode["steps_count"] = len(episode["steps"])
            if episode["game"] == "scaled_maze":
                episode["success"] = state["position"] == state["goal"]
                episode["outcome"] = "goal" if episode["success"] else episode.get("stop_reason", "horizon_exhausted")
                episode["score"] = int(episode["success"])
            else:
                episode["success"] = state.get("outcome") == "win"
                episode["outcome"] = state.get("outcome") if state["done"] else "horizon_survived"
                episode["score"] = state["score"]
        cells = defaultdict(list)
        for episode in selected:
            topology = episode["initial_state"].get("topology", "snake")
            cells[f"{episode['split']}/{episode['game']}/{episode['size']}/{topology}"].append(episode)
        summary = {key: {"episodes": len(rows), "mean_score": sum(r["score"] for r in rows)/len(rows),
                         "mean_steps": sum(r["steps_count"] for r in rows)/len(rows),
                         "goal_or_full_board_rate": sum(r["success"] for r in rows)/len(rows),
                         "outcomes": dict(__import__('collections').Counter(r["outcome"] for r in rows))}
                   for key, rows in cells.items()}
        result = {"schema": "nanojev-scaled-game-rollout-v1", "engine": args.engine, "controller": args.controller,
                  "checkpoint": args.checkpoint, "max_steps": args.max_steps, "episodes_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                  "selection": "first episodes per split/game/size/topology, before observing predictions", "summary": summary,
                  "execution": execution, "elapsed_seconds": time.perf_counter()-started, "episodes": selected}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"summary": summary, "execution": execution, "output": str(out)}))
    finally:
        if isinstance(engine, LiveJev):
            engine.close()


if __name__ == "__main__":
    main()
