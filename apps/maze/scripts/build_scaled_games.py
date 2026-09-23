#!/usr/bin/env python3
"""Build reproducible game-policy and observed-outcome datasets without network calls."""
import argparse
from collections import Counter, deque
import copy
import hashlib
import json
from pathlib import Path
import random

from game_outcomes import event_record
from train_pipeline_decisions import validate_training_row, SPLITS


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))


def maze_snapshots(state, count, seed):
    """Sample distinct same-map positions for data, never a learned-model rollout.

    Keep the initial position, then alternate a near-goal point on an actual
    shortest path, a far junction, and a random reachable decision position.
    Missing junctions/path slots have explicit fallbacks. Every added position
    offers at least two legal moves; fewer eligible positions produce fewer
    rows, not duplicated states. All search-derived values stay in metadata.
    """
    from scaled_maze import DIRECTIONS, validate_state, valid_actions
    validate_state(state)
    if type(count) is not int or count < 1 or type(seed) is not int:
        raise ValueError("Maze snapshot count must be positive and seed an integer")
    size = state["size"]
    walls, goal, initial = set(map(tuple, state["walls"])), tuple(state["goal"]), tuple(state["position"])

    def neighbors(cell):
        for dr, dc in DIRECTIONS.values():
            dest = cell[0] + dr, cell[1] + dc
            if 0 <= dest[0] < size and 0 <= dest[1] < size and dest not in walls:
                yield dest

    distances, queue = {goal: 0}, deque([goal])
    while queue:
        cell = queue.popleft()
        for dest in neighbors(cell):
            if dest not in distances:
                distances[dest] = distances[cell] + 1
                queue.append(dest)
    if initial not in distances:
        raise ValueError("Maze sampling requires a goal-reachable initial state")
    path, cell = [initial], initial
    while cell != goal:
        # A deterministic actual path: each move lowers exact distance by one.
        cell = next(dest for dest in neighbors(cell) if distances.get(dest) == distances[cell] - 1)
        path.append(cell)
    path_set = set(path)
    degrees = {cell: sum(1 for _ in neighbors(cell)) for cell in distances if cell != goal}
    eligible = {cell for cell, degree in degrees.items() if degree >= 2 and cell != initial}
    rng = random.Random(f"maze_positions_v1:{seed}")
    chosen = [(initial, "initial", "initial_endpoint", 1)]
    remaining = set(eligible)
    strategies = ("shortest_path_near_goal", "junction_far_goal", "reachable_random")
    while len(chosen) < count and remaining:
        strategy = strategies[(len(chosen) - 1) % len(strategies)]
        if strategy == "shortest_path_near_goal":
            pool = remaining & path_set
            source = strategy
            if not pool:
                pool, source = set(remaining), "reachable_near_goal_fallback"
            ordered = sorted(pool, key=lambda cell: (distances[cell], cell))
            # Pick from the nearest quarter; no assumption of short map paths.
            pool = ordered[:max(1, (len(ordered) + 3) // 4)]
        elif strategy == "junction_far_goal":
            pool = {cell for cell in remaining if degrees[cell] >= 3}
            source = strategy
            if not pool:
                pool, source = set(remaining), "reachable_far_goal_fallback"
            ordered = sorted(pool, key=lambda cell: (-distances[cell], cell))
            pool = ordered[:max(1, (len(ordered) + 3) // 4)]
        else:
            # Off-path examples improve location coverage when the map has any;
            # linear maps explicitly use the remaining path positions instead.
            pool = remaining - path_set
            source = "reachable_random_off_path" if pool else "reachable_random_on_path_fallback"
            pool = sorted(pool if pool else remaining)
        cell = rng.choice(pool)
        remaining.remove(cell)
        chosen.append((cell, strategy, source, len(pool)))
    snapshots = []
    for index, (position, strategy, source, pool_size) in enumerate(chosen):
        snapshot = copy.deepcopy(state)
        snapshot["position"] = list(position)
        metadata = {"protocol": "maze_positions_v1", "sampling_seed": seed, "sample_index": index,
                    "requested_strategy": strategy, "actual_source": source,
                    "source_initial_position": list(initial), "position": list(position),
                    "goal": list(goal), "on_initial_shortest_path": position in path_set,
                    "shortest_path_distance_to_goal": distances[position],
                    "initial_shortest_path_length": distances[initial],
                    "legal_action_count": len(valid_actions(snapshot)), "selection_pool_size": pool_size,
                    "eligible_additional_positions": len(eligible), "requested_states_per_map": count,
                    "actual_states_per_map": len(chosen),
                    "sampling_semantics": "programmatic_training_distribution_not_model_rollout"}
        snapshots.append((snapshot, metadata))
    return snapshots


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--seed", type=int, default=20260920)
    p.add_argument("--train-sizes", default="8,16,32")
    p.add_argument("--ood-sizes", default="50")
    p.add_argument("--train-maps-per-size", type=int, default=12)
    p.add_argument("--eval-maps-per-size", type=int, default=4)
    p.add_argument("--maze-states-per-map", type=int, default=4,
                   help="Distinct same-map positions, including the episode's initial state")
    p.add_argument("--snake-states-per-episode", type=int, default=4)
    p.add_argument("--snake-horizon", type=int, default=96)
    args = p.parse_args()
    if min(args.train_maps_per_size, args.eval_maps_per_size, args.maze_states_per_map,
           args.snake_states_per_episode, args.snake_horizon) < 1:
        p.error("Counts and horizon must be positive")
    train_sizes = [int(x) for x in args.train_sizes.split(",")]
    ood_sizes = [int(x) for x in args.ood_sizes.split(",")]
    if min(train_sizes + ood_sizes) < 8:
        p.error("Maze curriculum sizes must be >= 8")
    out = Path(args.output_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a new empty output directory")
    from scaled_maze import make_maze, make_record as maze_record
    from snake_game import make_snake, make_record as snake_record, valid_actions, step
    out.mkdir(parents=True, exist_ok=True)
    policies, events, episodes = [], [], []
    groups, public_hashes, event_ids = {}, set(), set()
    rng = random.Random(args.seed)

    def add(state, split, record_fn, event_seed, maze_position_source=None):
        row = record_fn(state, split)
        if state["game"] == "scaled_maze":
            from game_question_profiles import add_maze_atomic_questions
            row = add_maze_atomic_questions(row)
        if maze_position_source is not None:
            row["metadata"]["maze_position_source"] = copy.deepcopy(maze_position_source)
        group = row["metadata"]["source_group_id"]
        if group in groups and groups[group] != split:
            return False
        visible_hash = hashlib.sha256(json.dumps({"state": row["state"], "questions": row["questions"]}, sort_keys=True).encode()).hexdigest()
        if visible_hash in public_hashes:
            return False
        groups[group] = split
        public_hashes.add(visible_hash)
        validate_training_row(row)
        policies.append(row)
        actions = list((row["questions"].get("action") or {}).get("criteria", {}))
        if state["game"] == "scaled_maze":
            actions = ["north", "south", "east", "west"]
        elif not actions:
            actions = list(valid_actions(state))
        for index, reliability in enumerate((.1, .3, .7, .9)):
            intended = actions[index % len(actions)]
            event = event_record(state, split, intended, reliability, event_seed + index)
            event["metadata"]["source_group_id"] = group
            if maze_position_source is not None:
                event["metadata"]["maze_position_source"] = copy.deepcopy(maze_position_source)
            validate_training_row(event)
            if event["id"] not in event_ids:
                event_ids.add(event["id"])
                events.append(event)
        return True

    topologies = ("corridor", "tree", "loops", "random_obstacle")
    for split_index, split in enumerate(SPLITS):
        sizes = ood_sizes if split == "ood" else train_sizes
        count = args.train_maps_per_size if split == "train" else args.eval_maps_per_size
        for size in sizes:
            for index in range(count):
                seed = args.seed + split_index * 1000000 + size * 1000 + index
                state = make_maze(size, seed, topologies[index % len(topologies)])
                sampled = maze_snapshots(state, args.maze_states_per_map, seed)
                for snapshot_index, (snapshot, position_source) in enumerate(sampled):
                    accepted = add(snapshot, split, maze_record, seed * 1000000 + snapshot_index * 100,
                                   maze_position_source=position_source)
                    if snapshot_index == 0 and accepted:
                        episodes.append({"id": f"maze:{split}:{size}:{seed}", "split": split,
                                         "game": state["game"], "size": size, "initial_state": state})
                snake = make_snake(size, seed)
                snapshots = []
                for tick in range(args.snake_horizon):
                    if snake.get("done"):
                        break
                    if tick % max(1, args.snake_horizon // args.snake_states_per_episode) == 0:
                        snapshots.append(snake)
                    actions = list(valid_actions(snake))
                    next_states = [(a, step(snake, a)) for a in actions]
                    survivors = [(a, s) for a, s in next_states if not s.get("done") or s.get("outcome") == "win"]
                    if not survivors:
                        break
                    # Roll-in policy only: keeps producing varied body/food states.
                    # It is not used to evaluate a learned model or label optimality.
                    if rng.random() < .25:
                        _, snake = rng.choice(survivors)
                    else:
                        def distance(item):
                            s = item[1]
                            head = s["body"][0]
                            food = s.get("food")
                            return -1 if food is None else abs(head[0]-food[0])+abs(head[1]-food[1])
                        _, snake = min(survivors, key=distance)
                for tick, snapshot in enumerate(snapshots):
                    add(snapshot, split, snake_record, seed * 1000 + tick * 100)
                if snapshots:
                    episodes.append({"id": f"snake:{split}:{size}:{seed}", "split": split,
                                     "game": "snake", "size": size, "initial_state": snapshots[0]})
    for folder, rows in (("policy", policies), ("events", events)):
        target = out / folder
        target.mkdir()
        for split in SPLITS:
            selected = [r for r in rows if r["split"] == split]
            if not selected:
                raise ValueError(f"Empty {folder}/{split} split")
            write_jsonl(target / f"{split}.jsonl", selected)
    write_jsonl(out / "episodes.jsonl", episodes)
    manifest = {"schema": "nanojev-scaled-games-v1", "config": vars(args),
                "policy_states": len(policies), "event_states": len(events),
                "policy_counts": dict(Counter(f"{r['split']}/{r['metadata']['environment_state']['game']}/{r['metadata']['environment_state']['size']}" for r in policies)),
                "event_probability_histogram": dict(Counter(round(r["metadata"]["exact_event_probability"], 6) for r in events)),
                "distinct_source_groups": len(groups), "split_group_overlap": 0,
                "no_model_or_network_calls": True,
                "files": {str(f.relative_to(out)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.rglob("*.jsonl"))}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k not in {"files", "config", "policy_counts"}}))


if __name__ == "__main__":
    main()
