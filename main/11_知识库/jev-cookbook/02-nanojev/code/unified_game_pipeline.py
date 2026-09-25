#!/usr/bin/env python3
"""Reproducible multi-game collection, observed outcomes, and policy iteration.

One checkpoint answers dynamic Choice and action-conditioned Boolean questions.
Environment RPC lets a local API client control remote ViZDoom without copying
credentials. All episode files contain complete trajectories, not imagined labels.
"""
import argparse
from collections import Counter, defaultdict
import contextlib
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

SPLITS = ("train", "dev", "calibration", "test", "ood")
POLICY_QUESTION = "Choose the next action that maximizes the probability of completing the stated task successfully before its deadline. Use the visible state, action descriptions, remaining time, and recorded history."


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_hashes():
    names = ("unified_game_pipeline.py", "unified_grid_envs.py", "unified_doom_env.py",
             "scaled_maze.py", "snake_game.py", "evaluate_composed_maze.py",
             "predict_toy_decisions.py", "train_toy_decisions.py", "unified_jev_worker.mjs", "teachers.mjs")
    return {name: file_digest(Path(__file__).with_name(name)) for name in names}


def environment_group(case):
    spec, seed = case["spec"], case["seed"]
    if spec["task"] == "maze":
        from scaled_maze import make_maze, source_group_id
        initial = spec.get("initial_state") or make_maze(spec["size"], seed, spec.get("topology", "corridor"))
        return source_group_id(initial)
    if spec["task"] == "snake":
        from snake_game import make_snake
        initial = spec.get("initial_state") or make_snake(spec["size"], seed)
        return "snake:" + digest({k: v for k, v in initial.items() if k != "seed"})
    return "shooting:" + digest([spec["scenario"], seed])


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def factory(spec):
    if spec["task"] == "shooting":
        from unified_doom_env import UnifiedDoomEnv
        return UnifiedDoomEnv(spec)
    from unified_grid_envs import UnifiedMazeEnv, UnifiedSnakeEnv
    return {"maze": UnifiedMazeEnv, "snake": UnifiedSnakeEnv}[spec["task"]](spec)


class LocalEnvironments:
    def __init__(self):
        self.envs = {}

    def reset(self, cases):
        result = {}
        for case in cases:
            env = self.envs[case["id"]] = factory(case["spec"])
            obs, info = env.reset(case["seed"])
            result[case["id"]] = {"observation": obs, "info": info}
        return result

    def step(self, actions):
        result = {}
        for key, action in actions.items():
            obs, reward, terminated, truncated, info = self.envs[key].step(action)
            result[key] = dict(observation=obs, reward=reward, terminated=terminated,
                               truncated=truncated, info=info)
        return result

    def close(self):
        for env in self.envs.values():
            env.close()
        self.envs.clear()

    def describe(self, _=None):
        return source_hashes()


class RemoteEnvironments:
    def __init__(self, host, command):
        self.process = subprocess.Popen(["ssh", "-o", "BatchMode=yes", host, command],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, bufsize=1)
        if self.call("describe", None) != source_hashes():
            self.close()
            raise ValueError("Remote environment implementation differs from the frozen local source manifest")

    def call(self, op, value):
        self.process.stdin.write(encode({"op": op, "value": value}) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Remote environment process exited")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["result"]

    def reset(self, cases):
        return self.call("reset", cases)

    def step(self, actions):
        return self.call("step", actions)

    def close(self):
        if self.process.poll() is None:
            try:
                self.call("close", None)
            finally:
                self.process.stdin.close()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.terminate()


def serve():
    envs = LocalEnvironments()
    try:
        for line in sys.stdin:
            request = json.loads(line)
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    op = request["op"]
                    result = envs.close() if op == "close" else getattr(envs, op)(request["value"])
                print(encode({"result": result}), flush=True)
                if op == "close":
                    break
            except Exception as exc:
                print(encode({"error": f"{type(exc).__name__}: {exc}"}), flush=True)
                break
    finally:
        envs.close()


def policy_request(obs, identity):
    return {"id": identity, "state": obs["state"], "questions": {
        "action": {"type": "choice", "instructions": POLICY_QUESTION, "criteria": obs["candidates"]}}}


def outcome_question(action, description):
    return {"type": "boolean", "instructions": (
        f"Take action '{action}' now: {description} Then continue with the frozen behavior policy "
        "whose completed episodes define this prediction task. Will the stated task reach success "
        "before its remaining deadline? Predict eventual task success, including all later decisions."),
        "criteria": {"true": "Task success occurs within the remaining task deadline.",
                     "false": "The task ends without success, including collision, death, or deadline."}}


def outcome_request(obs, identity, actions=None):
    actions = list(obs["candidates"]) if actions is None else actions
    return {"id": identity, "state": obs["state"], "questions": {
        "success_" + action: outcome_question(action, obs["candidates"][action]) for action in actions}}


def behavior_distribution(scores, mode, epsilon):
    if not scores or not 0 <= epsilon <= 1 or any(not math.isfinite(x) for x in scores.values()):
        raise ValueError("Invalid policy scores/epsilon")
    keys = sorted(scores)
    if mode == "sample":
        total = sum(scores.values())
        if total <= 0 or min(scores.values()) < 0:
            raise ValueError("Sampling policy requires nonnegative probability mass")
        base = {key: scores[key] / total for key in keys}
    else:
        maximum = max(scores.values())
        best = [key for key in keys if scores[key] == maximum]
        # Deterministic tie breaking is part of the frozen controller.
        base = {key: float(key == best[0]) for key in keys}
    return {key: (1 - epsilon) * base[key] + epsilon / len(keys) for key in keys}


def choose(probs, rng):
    draw, cumulative = rng.random(), 0.0
    for key in sorted(probs):
        cumulative += probs[key]
        if draw < cumulative:
            return key
    return sorted(probs)[-1]


def policy_identity(args):
    result = {"engine": args.engine, "controller": args.controller, "epsilon": args.epsilon,
              "sampling_seed": args.seed, "temperature": 1.0,
              "source_sha256": source_hashes(),
              "tie_break": "lexicographic_first", "environment_contract": "finite_task_deadline_v1"}
    if args.engine == "checkpoint":
        root = Path(args.checkpoint)
        result["checkpoint_sha256"] = {name: file_digest(root / name) for name in
            ("config.json", "best.safetensors", "tokenizer/tokenizer.json", "backbone_config/config.json")}
    if args.engine == "jev":
        result["model"] = "typesafe-ai/jev"
    return result


def validate_cases(cases):
    ids, groups = set(), {}
    for case in cases:
        if case["id"] in ids or case["split"] not in SPLITS:
            raise ValueError("Duplicate case ID or invalid split")
        ids.add(case["id"])
        group = environment_group(case)
        if group in groups and groups[group] != case["split"]:
            raise ValueError("An underlying environment group crosses splits")
        groups[group] = case["split"]


def generate_cases(args):
    variants = [
        ("maze8", {"task": "maze", "size": 8, "topology": "tree", "max_steps": 32}),
        ("snake8", {"task": "snake", "size": 8, "target_food": 2, "max_steps": 96}),
        ("doom_basic", {"task": "shooting", "scenario": "basic", "max_steps": 75, "frame_skip": 4}),
        ("doom_predict_position", {"task": "shooting", "scenario": "predict_position", "max_steps": 75, "frame_skip": 4}),
    ]
    cases, assigned_groups = [], set()
    for split_index, split in enumerate(SPLITS):
        count = args.train_episodes if split == "train" else args.dev_episodes if split == "dev" else args.eval_episodes
        for variant_index, (variant, original) in enumerate(variants):
            spec = dict(original)
            if split == "ood":
                if spec["task"] == "maze":
                    spec.update(size=16, max_steps=160)
                elif spec["task"] == "snake":
                    spec.update(size=10, target_food=3, max_steps=160)
                else:
                    spec.update(frame_skip=8, max_steps=38)
            for index in range(count):
                seed = args.seed + split_index * 100000 + variant_index * 10000 + index
                for retry in range(10000):
                    candidate = {"id": f"{split}-{variant}-{seed}", "split": split, "seed": seed,
                                 "variant": variant, "spec": spec}
                    group = environment_group(candidate)
                    if group not in assigned_groups:
                        assigned_groups.add(group)
                        cases.append(candidate)
                        break
                    seed += 1
                else:
                    raise ValueError("Unable to generate enough distinct underlying environment groups")
    validate_cases(cases)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        for case in cases:
            handle.write(encode(case) + "\n")
    print(encode({"cases": len(cases), "output": str(output), "sha256": file_digest(output)}))


def summarize(episodes):
    groups = defaultdict(list)
    for episode in episodes:
        groups[(episode["case"]["split"], episode["case"]["spec"]["task"], episode["case"]["variant"])].append(episode)
    summary = {}
    for key, rows in sorted(groups.items()):
        completed = [e for e in rows if e["complete"]]
        metrics = defaultdict(list)
        for episode in completed:
            for name, value in episode["final_info"].get("episode_metrics", {}).items():
                if type(value) in (float, int) and math.isfinite(value):
                    metrics[name].append(value)
        summary["/".join(key)] = {"episodes": len(rows), "complete": len(completed),
            "successes": sum(e["success"] for e in completed),
            "success_rate": sum(e["success"] for e in completed) / len(completed) if completed else None,
            "mean_decisions": sum(len(e["steps"]) for e in completed) / len(completed) if completed else None,
            "mean_metrics": {k: sum(v) / len(v) for k, v in metrics.items()}}
    return summary


def rollout(args):
    if not 0 <= args.epsilon <= 1 or args.env_batch < 1:
        raise ValueError("Invalid rollout parameters")
    if args.controller == "q_greedy" and args.engine != "checkpoint":
        raise ValueError("Q policy requires a checkpoint")
    cases = read_rows(args.cases)
    validate_cases(cases)
    cases = [c for c in cases if c["split"] in args.splits.split(",")]
    if args.limit_per_variant:
        counts, selected = Counter(), []
        for case in cases:
            key = (case["split"], case["variant"])
            if counts[key] < args.limit_per_variant:
                counts[key] += 1
                selected.append(case)
        cases = selected
    if not cases:
        raise ValueError("No selected cases")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("Use a fresh episode output path")
    declaration = policy_identity(args)
    policy_id = digest(declaration)
    snapshot_dir = output.with_suffix(".sources")
    snapshot_dir.mkdir(exist_ok=False)
    for name in declaration["source_sha256"]:
        shutil.copy2(Path(__file__).with_name(name), snapshot_dir / name)
    manifest_path = output.with_suffix(".manifest.json")
    manifest = {"schema_version": "nanojev-unified-episodes-v1", "policy": declaration,
                "continuation_policy_id": policy_id, "cases_sha256": file_digest(args.cases),
                "selected_cases": [c["id"] for c in cases], "source_snapshot": snapshot_dir.name,
                "finished": False}
    write_json(manifest_path, manifest)
    predictor = None
    if args.engine == "checkpoint":
        from predict_toy_decisions import DecisionPredictor
        predictor = DecisionPredictor(args.checkpoint, max_length=args.max_length,
                                      disable_native_triton=True)
    elif args.engine == "jev":
        from evaluate_scaled_games import LiveJev
        if not args.env_file or not args.journal_dir:
            raise ValueError("Jev requires an env file and journal directory")
        # Reuse the transport interface with a dedicated bounded-retry worker.
        predictor = LiveJev.__new__(LiveJev)
        journal = Path(args.journal_dir)
        journal.mkdir(parents=True, exist_ok=True)
        predictor.log = (journal / "worker_stderr.log").open("a")
        predictor.process = subprocess.Popen([
            "node", f"--env-file={args.env_file}", str(Path(__file__).with_name("unified_jev_worker.mjs")),
            "--journal-dir", str(journal), "--budget-usd", str(args.budget_usd), "--concurrency", "4"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=predictor.log, text=True, bufsize=1)
    all_episodes = []
    started = time.monotonic()
    try:
        with output.open("x") as handle:
            for offset in range(0, len(cases), args.env_batch):
                batch = cases[offset:offset + args.env_batch]
                environments = RemoteEnvironments(args.remote_host, args.remote_command) if args.remote_host else LocalEnvironments()
                try:
                    current = environments.reset(batch)
                    episodes = {c["id"]: {"case": c, "continuation_policy_id": policy_id, "steps": [],
                                           "complete": False, "success": None} for c in batch}
                    rngs = {c["id"]: random.Random(int(digest([c["id"], args.seed])[:16], 16)) for c in batch}
                    active = set(episodes)
                    while active:
                        requests, decisions = [], {}
                        for key in sorted(active):
                            obs = current[key]["observation"]
                            candidates = obs["candidates"]
                            if not candidates:
                                episodes[key].update(complete=True, success=bool(current[key]["info"]["success"]),
                                                     final_info=current[key]["info"])
                                continue
                            if len(candidates) == 1:
                                decisions[key] = {"scores": {next(iter(candidates)): 1.0}, "answers": {}, "forced": True}
                            elif predictor is None:
                                decisions[key] = {"scores": {a: 1 / len(candidates) for a in candidates}, "answers": {}}
                            else:
                                request = outcome_request if args.controller == "q_greedy" else policy_request
                                requests.append(request(obs, key))
                        active = {key for key in active if not episodes[key]["complete"]}
                        if requests:
                            response = predictor.predict({"states": requests}, batch_questions=args.batch_questions, temperature=1.0)
                            answers_by_id = {r["id"]: r["answers"] for r in response["states"]}
                            if len(answers_by_id) != len(requests) or set(answers_by_id) != {r["id"] for r in requests}:
                                raise ValueError("Prediction IDs do not match requests")
                            for req in requests:
                                answers = answers_by_id[req["id"]]
                                scores = ({a: answers["success_" + a]["probabilities"]["true"]
                                           for a in current[req["id"]]["observation"]["candidates"]}
                                          if args.controller == "q_greedy" else answers["action"]["probabilities"])
                                decisions[req["id"]] = {"scores": scores, "answers": answers}
                        actions = {}
                        for key in sorted(active):
                            d = decisions[key]
                            mode = "sample" if args.engine == "random" or args.controller == "sample" else "greedy"
                            d["behavior_probs"] = behavior_distribution(d["scores"], mode, args.epsilon)
                            actions[key] = choose(d["behavior_probs"], rngs[key])
                        if not actions:
                            break
                        following = environments.step(actions)
                        for key, action in actions.items():
                            transition = following[key]
                            episodes[key]["steps"].append({"observation": current[key]["observation"],
                                "action": action, **decisions[key], "reward": transition["reward"],
                                "terminated": transition["terminated"], "truncated": transition["truncated"],
                                "info": transition["info"]})
                            if transition["truncated"]:
                                raise RuntimeError("External truncation cannot be labeled as failure")
                            if transition["terminated"]:
                                episodes[key].update(complete=True, success=bool(transition["info"]["success"]),
                                                     final_info=transition["info"])
                                active.remove(key)
                        current.update(following)
                    for case in batch:
                        episode = episodes[case["id"]]
                        handle.write(encode(episode) + "\n")
                        handle.flush()
                        all_episodes.append(episode)
                    print(encode({"completed": len(all_episodes), "total": len(cases),
                                  "elapsed_seconds": round(time.monotonic() - started, 2)}), flush=True)
                finally:
                    environments.close()
    finally:
        if hasattr(predictor, "close"):
            predictor.close()
    manifest.update(finished=True, episode_sha256=file_digest(output),
                    elapsed_seconds=time.monotonic() - started, summary=summarize(all_episodes))
    write_json(manifest_path, manifest)
    print(encode(manifest["summary"]), flush=True)


def make_dataset(args):
    state_limit = args.max_states_per_episode
    if state_limit is None:
        state_limit = 24 if args.role == "policy" else 0
    if state_limit < 0 or (args.role == "outcome" and state_limit != 0):
        raise ValueError("Outcome data must retain every executed transition: thinning by final episode length biases future-success labels. Use --max-states-per-episode 0.")
    episodes = read_rows(args.episodes)
    source_manifest = json.loads(Path(args.episodes).with_suffix(".manifest.json").read_text())
    if not source_manifest["finished"] or file_digest(args.episodes) != source_manifest["episode_sha256"]:
        raise ValueError("Only a completed, hash-verified collection can enter a dataset")
    policy_id = source_manifest["continuation_policy_id"]
    validate_cases([e["case"] for e in episodes])
    rows = []
    journal = {}
    if args.journal_dir:
        journal = {r["id"]: r for r in read_rows(Path(args.journal_dir) / "calls.jsonl") if r["status"] == "succeeded"}
    if args.retention:
        for split in SPLITS:
            retained = read_rows(Path(args.retention) / f"{split}.jsonl")
            rows.extend(row for row in retained if row["metadata"]["record_role"] == "policy")
    counts = Counter()
    for episode in episodes:
        if not episode["complete"] or episode["continuation_policy_id"] != policy_id:
            raise ValueError("Incomplete or mixed-policy episodes are not observed outcomes")
        case = episode["case"]
        steps = episode["steps"]
        if type(episode["success"]) is not bool or episode.get("final_info", {}).get("success") != episode["success"]:
            raise ValueError("Episode success must be a Boolean matching terminal environment information")
        if steps:
            terminal = steps[-1]
            if not terminal["terminated"] or terminal["truncated"] or terminal["info"].get("success") != episode["success"]:
                raise ValueError("Observed outcomes require a consistent genuine terminal transition")
            if any(step["terminated"] or step["truncated"] for step in steps[:-1]):
                raise ValueError("An episode cannot continue after termination or external truncation")
        elif not episode["final_info"].get("terminated"):
            raise ValueError("An empty trajectory requires a genuinely terminal reset")
        group = environment_group(case)
        selected = list(range(len(steps)))
        if state_limit and len(selected) > state_limit:
            rng = random.Random(int(digest([case["id"], "state_subsample"])[:16], 16))
            selected = sorted(rng.sample(selected, state_limit))
        for index in selected:
            step = steps[index]
            obs, action = step["observation"], step["action"]
            if action not in obs["candidates"] or step["truncated"]:
                raise ValueError("Invalid physical action provenance")
            identity = digest([policy_id, case["id"], index, args.role])
            if args.role == "policy":
                answer = step["answers"].get("action")
                if answer is None:
                    continue  # Forced singleton actions are executable but not Choice supervision.
                request = policy_request(obs, identity)
            else:
                request = outcome_request(obs, identity, [action])
            row = {**request, "state_id": digest([group, case["seed"], index, obs["state"]]), "family_id": "unified_" + obs["task"],
                "split": case["split"], "metadata": {"task": obs["task"], "record_role": args.role,
                "episode_id": case["id"], "source_group_id": group, "decision_index": index,
                "public_observation_sha256": digest(obs["state"]),
                "executed_action": action, "conditioned_action": action,
                "continuation_policy_id": policy_id, "episode_success": episode["success"],
                "spec": case["spec"], "remaining_steps": obs["remaining_steps"]}}
            if args.role == "policy":
                call = journal.get(answer.get("source_api_call_id"))
                if not call or call["input_sha256"] != answer.get("source_input_sha256"):
                    raise ValueError("Policy labels require the matching successful API journal entry")
                if call["input"].get("state") != request["state"] or call["input"].get("questions") != request["questions"]:
                    raise ValueError("API receipt does not label the recorded physical observation and question")
                if call["native_probs"].get("action") != answer.get("native_probabilities"):
                    raise ValueError("Recorded native probabilities do not match their API receipt")
                row["teacher"] = {"model": call["model"], "native_probs": call["native_probs"],
                                  "rounding": call["rounding"], "source_api_call_id": call["id"]}
            else:
                row["gold"] = {qid: episode["success"] for qid in row["questions"]}
                row["gold_label_kind"] = {qid: "observed_outcome" for qid in row["questions"]}
            rows.append(row)
            counts[(case["split"], obs["task"], args.role)] += 1
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    for split in SPLITS:
        (root / f"{split}.jsonl").write_text("".join(encode(r) + "\n" for r in rows if r["split"] == split))
    manifest = {"schema_version": "nanojev-unified-training-v1", "continuation_policy_id": policy_id,
        "episode_sha256": source_manifest["episode_sha256"], "episode_file": str(args.episodes),
        "collection_policy": source_manifest["policy"], "max_states_per_episode": state_limit,
        "retention": args.retention, "new_records": {"/".join(k): v for k, v in counts.items()},
        "split_sha256": {s: file_digest(root / f"{s}.jsonl") for s in SPLITS},
        "outcome_semantics": "actual eventual success after the executed action under the declared frozen continuation policy"}
    write_json(root / "manifest.json", manifest)
    print(encode(manifest), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("env-server")
    cases = commands.add_parser("cases")
    cases.add_argument("--output", required=True)
    cases.add_argument("--train-episodes", type=int, default=12)
    cases.add_argument("--dev-episodes", type=int, default=3)
    cases.add_argument("--eval-episodes", type=int, default=4)
    cases.add_argument("--seed", type=int, default=1700)
    collect = commands.add_parser("rollout")
    collect.add_argument("--cases", required=True)
    collect.add_argument("--output", required=True)
    collect.add_argument("--engine", choices=["checkpoint", "jev", "random"], required=True)
    collect.add_argument("--checkpoint")
    collect.add_argument("--controller", choices=["greedy", "sample", "q_greedy"], default="greedy")
    collect.add_argument("--epsilon", type=float, default=.15)
    collect.add_argument("--seed", type=int, default=17)
    collect.add_argument("--splits", default=",".join(SPLITS))
    collect.add_argument("--limit-per-variant", type=int, default=0)
    collect.add_argument("--env-batch", type=int, default=16)
    collect.add_argument("--batch-questions", type=int, default=16)
    collect.add_argument("--max-length", type=int, default=8192)
    collect.add_argument("--remote-host")
    collect.add_argument("--remote-command")
    collect.add_argument("--env-file")
    collect.add_argument("--journal-dir")
    collect.add_argument("--budget-usd", type=float, default=2.0)
    dataset = commands.add_parser("dataset")
    dataset.add_argument("--episodes", required=True)
    dataset.add_argument("--output", required=True)
    dataset.add_argument("--role", choices=["policy", "outcome"], required=True)
    dataset.add_argument("--journal-dir")
    dataset.add_argument("--retention")
    dataset.add_argument("--max-states-per-episode", type=int, help="Policy rows default to 24; outcome rows must use 0 (all transitions).")
    args = parser.parse_args()
    {"env-server": lambda _: serve(), "cases": generate_cases, "rollout": rollout,
     "dataset": make_dataset}[args.command](args)


if __name__ == "__main__":
    main()
