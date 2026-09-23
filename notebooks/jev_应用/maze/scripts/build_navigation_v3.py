#!/usr/bin/env python3
"""V3 navigation: explicit coordinates, local destinations and multiple starts per map.

Only render_request is needed at inference time. It uses public geometry and legal
one-step transitions; BFS/optimal actions appear only in separate label metadata.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

from game_tasks import (DIRECTIONS, grid_distances, solve, source_group_id, step,
                        transform_state, valid_actions)
from train_pipeline_decisions import validate_training_row

SPLITS = ("train", "dev", "calibration", "test", "ood")
DEFAULT_MAP_COUNTS = dict(zip(SPLITS, (300, 40, 40, 80, 40)))
DEFAULT_SEED = 20260918
SCORE_CRITERIA = ["The goal is reachable in one or two steps.",
                  "The goal is reachable in three to five steps.",
                  "The goal is reachable in six or more steps.",
                  "The goal cannot be reached."]
HEADERS = {"train": "Navigation state:", "dev": "Navigation validation state:",
           "calibration": "Navigation calibration state:", "test": "Held-out navigation state:",
           "ood": "Larger navigation state:", "rollout": "Navigation state:"}


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def render_request(state, split="rollout", candidate_order=None):
    """Return state/questions using geometry only; no oracle, BFS, distance or solution lookup.

One-legal-action states can be rendered, but the controller must execute that
forced move directly because the model's Choice API requires at least two options.
"""
    if state.get("game") != "grid_navigation" or split not in HEADERS:
        raise ValueError("Expected a grid_navigation state and a supported split")
    actions = valid_actions(state)
    if not actions:
        raise ValueError("Terminal or immobile state has no action question")
    order = list(actions) if candidate_order is None else list(candidate_order)
    if len(order) != len(actions) or set(order) != set(actions):
        raise ValueError("candidate_order must contain each legal action exactly once")
    size = state["size"]
    walls = {tuple(x) for x in state["walls"]}
    board = [["#" if (r, c) in walls else "." for c in range(size)] for r in range(size)]
    board[state["goal"][0]][state["goal"][1]] = "G"
    board[state["position"][0]][state["position"][1]] = "A"
    coords = lambda cell: f"({cell[0]},{cell[1]})"
    wall_text = ",".join(coords(cell) for cell in sorted(walls)) or "none"
    grid = "columns: " + " ".join(map(str, range(size))) + "\n" + "\n".join(
        f"row {r}: " + " ".join(values) for r, values in enumerate(board))
    public_state = (
        f"{HEADERS[split]}\n"
        f"Grid {size}x{size}. Coordinates are zero-based (row,column). Rows increase south; columns increase east.\n"
        f"Agent={coords(state['position'])}; goal={coords(state['goal'])}; walls={wall_text}.\n"
        "Each legal orthogonal move costs 1; no diagonals. A=agent, G=goal, #=wall, .=open.\n" + grid)
    criteria = {}
    for action in order:
        destination = step(state, action)["position"]  # Local legal transition only, never an oracle score.
        criteria[action] = f"Move {action} to (row {destination[0]}, column {destination[1]})."
    return {"state": public_state, "questions": {
        "action": {"type": "choice",
                   "instructions": "Choose a legal next step on a shortest route to the goal. If the goal is unreachable, all legal moves tie. Walls cannot be crossed.",
                   "criteria": criteria},
        "solvable": {"type": "boolean", "instructions": "Can the agent reach the goal by legal orthogonal moves?"},
        "value": {"type": "score",
                  "instructions": "Classify the minimum number of legal steps from the current agent cell to the goal; use the unreachable category if no route exists.",
                  "criteria": list(SCORE_CRITERIA)},
    }}


def make_record(state, split, index=0, seed=DEFAULT_SEED, rng=None):
    rng = random.Random(seed + index) if rng is None else rng
    actions = valid_actions(state)
    rng.shuffle(actions)
    public = render_request(state, split=split, candidate_order=actions)
    oracle = solve(state)
    optimal = sorted(oracle["optimal_actions"])
    reachable = oracle["reachable"]
    distance = oracle["distance"]
    level = 3 if distance is None else 0 if distance <= 2 else 1 if distance <= 5 else 2
    state_id = "navigation_v3:" + stable_hash(state)[:24]
    return {"id": state_id, "state_id": state_id, "family_id": "grid_navigation_coordinates_v3",
            "split": split, **public,
            "gold": {"action": optimal[0], "solvable": reachable, "value": level},
            "gold_probs": {"action": {a: 1 / len(optimal) if a in optimal else 0.0 for a in actions},
                           "solvable": {"false": float(not reachable), "true": float(reachable)},
                           "value": {str(i): float(i == level) for i in range(4)}},
            "gold_probs_kind": {"action": "optimal_action_policy", "solvable": "deterministic_truth", "value": "deterministic_truth"},
            "gold_label_kind": {"action": "reference_argmax_compatibility", "solvable": "deterministic_truth", "value": "deterministic_truth"},
            "optimal_actions": {"action": optimal},
            "metadata": {"source": "self_authored_programmatic", "license": "CC0-1.0",
                         "source_group_id": source_group_id(state), "template_id": f"navigation_v3:{split}",
                         "language": "en", "environment_state": state, "oracle": oracle,
                         "action_distribution_meaning": "uniform optimal-action policy, not calibrated success probability",
                         "model_input_oracle_fields": [], "distribution_shift": "6x6_grid" if state["size"] == 6 else "4x4_grid"}}


def excluded_v2_groups(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    groups = set()
    for row in rows:
        state = row.get("metadata", {}).get("environment_state", {})
        if state.get("game") == "grid_navigation":
            groups.add(source_group_id(state))
    if not groups:
        raise ValueError("V2 source contains no grid maps; cannot establish exclusion")
    return groups


def sample_map(size, unreachable, rng, excluded):
    for attempt in range(100000):
        # Preserve V2's wall-density distribution; do not filter for eight starts.
        density = rng.uniform(.18, .38)
        walls = [[r, c] for r in range(size) for c in range(size) if rng.random() < density]
        wall_set = set(map(tuple, walls))
        free = [(r, c) for r in range(size) for c in range(size) if (r, c) not in wall_set]
        if len(free) < 4:
            continue
        goal = list(rng.choice(free))
        prototype = {"game": "grid_navigation", "size": size, "walls": walls, "position": goal, "goal": goal}
        group = source_group_id(prototype)
        if group in excluded:
            continue
        distances = grid_distances(prototype)
        starts = [list(cell) for cell in free if list(cell) != goal and ((cell not in distances) == unreachable)
                  and len(valid_actions({**prototype, "position": list(cell)})) >= 2]
        if len(starts) < 2:
            continue
        rng.shuffle(starts)
        return prototype, starts, attempt + 1
    raise RuntimeError("Map sampling exhausted; counts were not silently reduced")


def render_map_records(prototype, starts, split, count, rng):
    # Eight train records cover every D4 transform. Independent starts are used
    # without replacement first; repeated starts can only add a distinct transformed state.
    symmetry_order = list(range(8))
    rng.shuffle(symmetry_order)
    if count > 8:
        raise ValueError("This version supports at most eight records per map")
    selected = starts[:min(count, len(starts))]
    used_starts, used_states, records = set(), set(), []
    for symmetry in symmetry_order[:count]:
        candidates = [s for s in selected if tuple(s) not in used_starts]
        if not candidates:
            candidates = list(selected)
        rng.shuffle(candidates)
        chosen = None
        for start in candidates:
            state = transform_state({**prototype, "position": start}, symmetry)
            key = stable_hash(state)
            if key not in used_states:
                chosen = start, state, key
                break
        if chosen is None:
            return None  # Reject this sampled map instead of duplicating a state.
        start, state, key = chosen
        used_starts.add(tuple(start)); used_states.add(key)
        record = make_record(state, split, rng=rng)
        record["metadata"].update(pre_transform_start=start, d4_symmetry=symmetry,
                                  original_map_goal=prototype["goal"], original_map_walls=prototype["walls"])
        records.append(record)
    if len(used_starts) != min(count, len(starts)):
        raise AssertionError("Available distinct raw starts were not maximally used")
    for row in records:
        row["metadata"].update(map_unique_raw_starts=len(used_starts), map_unique_transformed_states=len(used_states),
                                map_eligible_raw_starts=len(starts))
    return records


def validate_records(records, excluded):
    seen_ids, seen_states, group_split, by_group = set(), set(), {}, {}
    for split, rows in records.items():
        for row in rows:
            validate_training_row(row)
            if row["split"] != split or row["id"] in seen_ids:
                raise ValueError("Duplicate record ID or wrong split")
            seen_ids.add(row["id"])
            state = row["metadata"]["environment_state"]
            key = stable_hash(state)
            if key in seen_states:
                raise ValueError("An identical transformed environment state was counted twice")
            seen_states.add(key)
            group = source_group_id(state)
            if group != row["metadata"]["source_group_id"] or group in excluded:
                raise ValueError("Source group mismatches or overlaps V2")
            if group in group_split and group_split[group] != split:
                raise ValueError("A map/D4 orbit crosses V3 splits")
            group_split[group] = split
            by_group.setdefault(group, []).append(row)
            oracle = solve(state)
            if len(valid_actions(state)) < 2 or set(row["questions"]["action"]["criteria"]) != set(valid_actions(state)):
                raise ValueError("Training Choice must contain exactly all legal actions, K>=2")
            if row["gold"]["solvable"] != oracle["reachable"]:
                raise ValueError("Boolean oracle mismatch")
            expected_level = 3 if oracle["distance"] is None else 0 if oracle["distance"] <= 2 else 1 if oracle["distance"] <= 5 else 2
            if row["gold"]["value"] != expected_level:
                raise ValueError("Score oracle mismatch")
            optimal = set(oracle["optimal_actions"])
            if set(row["optimal_actions"]["action"]) != optimal:
                raise ValueError("Optimal action set mismatch")
            for action, probability in row["gold_probs"]["action"].items():
                if probability != (1 / len(optimal) if action in optimal else 0.0):
                    raise ValueError("Policy mass is not uniform over all optimal actions")
            public = render_request(state, split, list(row["questions"]["action"]["criteria"]))
            if public["state"] != row["state"] or public["questions"] != row["questions"]:
                raise ValueError("Public input differs from geometry-only renderer")
    for group, rows in by_group.items():
        raw_count = len({tuple(row["metadata"]["pre_transform_start"]) for row in rows})
        if raw_count < 2:
            raise ValueError("A map has fewer than two distinct original starts")
        if any(row["metadata"]["map_unique_raw_starts"] != raw_count for row in rows):
            raise ValueError("Incorrect independent-start count")
        if any(row["metadata"]["map_unique_transformed_states"] != len(rows) for row in rows):
            raise ValueError("Incorrect transformed-state count")
        if group_split[group] == "train" and {row["metadata"]["d4_symmetry"] for row in rows} != set(range(8)):
            raise ValueError("Train map did not cover all D4 transforms")
    return {"states": len(seen_ids), "unique_transformed_states": len(seen_states),
            "unique_source_maps": len(by_group), "excluded_v2_maps": len(excluded),
            "v2_map_overlap": 0, "cross_split_map_overlap": 0, "duplicate_transformed_states": 0,
            "geometry_only_renderer_matches_all_inputs": True}


def build_records(v2_input, seed=DEFAULT_SEED, map_counts=None):
    counts = dict(DEFAULT_MAP_COUNTS if map_counts is None else map_counts)
    if set(counts) != set(SPLITS) or any(type(n) is not int or n < 0 or n % 4 for n in counts.values()):
        raise ValueError("Map counts must be nonnegative multiples of four for the fixed 75/25 reachability split")
    excluded = excluded_v2_groups(v2_input)
    seen = set(excluded)
    records, sampling = {s: [] for s in SPLITS}, {}
    for split_index, split in enumerate(SPLITS):
        rng = random.Random(seed + split_index * 100003)
        attempts, symmetry_rejections = 0, 0
        maps = 0
        while maps < counts[split]:
            unreachable = maps % 4 == 0
            prototype, starts, tries = sample_map(6 if split == "ood" else 4, unreachable, rng, seen)
            attempts += tries
            group = source_group_id(prototype)
            items = render_map_records(prototype, starts, split, 8 if split == "train" else 3, rng)
            if items is None:
                seen.add(group); symmetry_rejections += 1
                continue
            seen.add(group); maps += 1
            records[split].extend(items)
        rng.shuffle(records[split])
        sampling[split] = {"map_sampling_attempts": attempts, "symmetry_collision_map_rejections": symmetry_rejections}
    return records, excluded, sampling


def protocol_text(manifest):
    return "\n".join([
        "# V3 导航数据与验收预注册", "",
        "V2 的六个训练及测试结果保留。V2 导航闭环失败触发本次后续假设；V2 test 已被观察，只能作为历史/开发参照。V3 的新 test/ood 在训练及 dev checkpoint 选择完成后才用于模型评估。", "",
        "本版同时检验表示与数据覆盖：输入明确给出零基 agent/goal/wall 坐标、带行列索引的完整地图，以及每个合法候选动作的 destination 坐标；同一训练地图覆盖多个原始起点和 D4 变换。没有单因素消融时，改善不能归因于某一个因素。游戏规则、墙密度抽样范围、ID 4×4/OOD 6×6 和 75% 可达/25% 不可达边界沿用 V2。", "",
        "训练300图×8条=2400状态；dev40图×3=120，calibration40×3=120，test80×3=240，OOD40×3=120。总3000状态/9000题。八条训练记录不伪称八个独立原始起点：每图至少2个、尽量多的不同原始起点，用不同D4补齐；原始起点数和变换后唯一状态数逐图审计。", "",
        "按 walls+goal 的 D4 canonical source_group 分区，忽略 agent 起点。V3 排除 V2 全部地图（包括已见test），新train/dev/calibration/test/ood地图互斥。D4等价地图或同图其它起点不得跨split。每个状态的候选覆盖全部合法动作；单合法动作状态由闭环控制器透明地执行 forced move，不能伪装模型决策。", "",
        "render_request 只读取公开地图并调用合法一步变换；不会调用 solve/grid_distances。BFS 距离、最优动作、可达性与所有 gold 只存在独立标签/metadata，不进入 state/questions。Choice gold 为全部等价最优动作上的均匀策略，不是成功概率或现实事件校准；Boolean/Score为程序确定真值。", "",
        "如需防遗忘replay，只允许原有数据的train；旧dev可作回归开发，不得把旧test/calibration/ood混入训练。数据builder不混合replay，后续assembler须按split审计。新训练步数、目标两臂、checkpoint选择规则由root在启动前冻结，本脚本不启动GPU或调用teacher。", "",
        "闭环验收预先固定控制器greedy、按学生T=1概率采样、uniform random；可另列oracle上界。使用相同新test/ood、固定每episode RNG、相同步长上限，保留所有成功和失败，不只展示成功轨迹。模型与控制器效果分开报告，避免把循环都归因数据或表示。", "",
        f"数据seed={manifest['seed']}；V2来源SHA256={manifest['v2_input_sha256']}。完整地图重合与标签检查见manifest；真实tokenizer预检另记录，超长只报错，不截断输入或候选。", "",
    ])


def write_dataset(output_dir, v2_input, seed=DEFAULT_SEED, map_counts=None):
    output_dir = Path(output_dir)
    if (output_dir / "manifest.json").exists():
        raise ValueError("Existing V3 dataset is preserved; choose a new directory to regenerate")
    records, excluded, sampling = build_records(v2_input, seed, map_counts)
    audit = validate_records(records, excluded)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "openjev-navigation-v3", "seed": seed,
                "source": "self_authored_programmatic", "license": "CC0-1.0", "teacher": None,
                "v2_input_path": str(v2_input), "v2_input_sha256": hashlib.sha256(Path(v2_input).read_bytes()).hexdigest(),
                "audit": audit, "sampling": sampling, "splits": {},
                "input_fields": ["agent coordinates", "goal coordinates", "wall coordinates", "indexed full map", "legal one-step destination coordinates"],
                "oracle_fields_in_model_input": [], "wall_density_sampling": [.18, .38],
                "unreachable_fraction_by_split": .25, "game_rule_changes": [],
                "source_code_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                       for name in ("build_navigation_v3.py", "game_tasks.py")}}
    all_payload = []
    for split, rows in records.items():
        payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
        (output_dir / f"{split}.jsonl").write_text(payload, encoding="utf-8")
        all_payload.append(payload)
        groups = {}
        for row in rows:
            groups.setdefault(row["metadata"]["source_group_id"], []).append(row)
        manifest["splits"][split] = {
            "maps": len(groups), "states": len(rows), "questions": 3 * len(rows),
            "unique_raw_starts_sum": sum(items[0]["metadata"]["map_unique_raw_starts"] for items in groups.values()),
            "unique_raw_starts_per_map": dict(Counter(items[0]["metadata"]["map_unique_raw_starts"] for items in groups.values())),
            "unique_transformed_states": len({stable_hash(row["metadata"]["environment_state"]) for row in rows}),
            "boolean_labels": dict(Counter(str(row["gold"]["solvable"]).lower() for row in rows)),
            "score_labels": dict(Counter(str(row["gold"]["value"]) for row in rows)),
            "choice_k": dict(Counter(len(row["questions"]["action"]["criteria"]) for row in rows)),
            "optimal_action_count": dict(Counter(len(row["optimal_actions"]["action"]) for row in rows)),
            "oracle_distance_histogram": dict(Counter(str(row["metadata"]["oracle"]["distance"]) for row in rows)),
            "wall_count_histogram": dict(Counter(len(row["metadata"]["environment_state"]["walls"]) for row in rows)),
            "sha256": hashlib.sha256(payload.encode()).hexdigest()}
    combined = "".join(all_payload)
    (output_dir / "all.jsonl").write_text(combined, encoding="utf-8")
    manifest["all_sha256"] = hashlib.sha256(combined.encode()).hexdigest()
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "protocol_zh.md").write_text(protocol_text(manifest), encoding="utf-8")
    return manifest


def self_check(v2_input):
    state = {"game": "grid_navigation", "size": 4, "walls": [[0, 1], [1, 1]], "position": [0, 0], "goal": [0, 3]}
    global solve, grid_distances
    original_solve, original_distances = solve, grid_distances
    def forbidden(*args, **kwargs):
        raise AssertionError("Oracle was called by geometry renderer")
    solve, grid_distances = forbidden, forbidden
    try:
        rendered = render_request(state)
    finally:
        solve, grid_distances = original_solve, original_distances
    for action, text in rendered["questions"]["action"]["criteria"].items():
        destination = step(state, action)["position"]
        assert f"row {destination[0]}, column {destination[1]}" in text
    counts = {split: 4 for split in SPLITS}
    first, excluded, _ = build_records(v2_input, 31, counts)
    second, _, _ = build_records(v2_input, 31, counts)
    assert first == second
    audit = validate_records(first, excluded)
    assert audit["states"] == 80 and audit["unique_source_maps"] == 20
    assert len(first["train"]) == 32
    bad = {s: list(rows) for s, rows in first.items()}
    bad["test"].append(first["train"][0])
    try:
        validate_records(bad, excluded)
        raise AssertionError("Cross-split or duplicate state accepted")
    except ValueError:
        pass
    return {"geometry_renderer_without_oracle": True, "destination_transition_check": True,
            "deterministic_generation": True, "map_split_and_oracle_checks": True,
            "duplicate_or_cross_split_rejected": True, "small_fixture_states": audit["states"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=Path("research/private_navigation_v3"))
    p.add_argument("--v2-input", type=Path, default=Path("research/private_games_v2/all.jsonl"))
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()
    if args.self_check:
        print(json.dumps(self_check(args.v2_input), ensure_ascii=False))
    else:
        m = write_dataset(args.output_dir, args.v2_input, args.seed)
        print(json.dumps({"output_dir": str(args.output_dir), "audit": m["audit"],
                          "splits": {s: {k: r[k] for k in ("maps", "states", "unique_raw_starts_per_map", "boolean_labels")} for s, r in m["splits"].items()},
                          "all_sha256": m["all_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
