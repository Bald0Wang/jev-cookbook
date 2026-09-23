#!/usr/bin/env python3
"""Freeze navigation representation x start-coverage views with matched exposure slots.

No GPU/API calls. Keep all canonical V3 data and V2 results unchanged. Gold views
share the same slot IDs/order; only train coverage and rendered representation vary.
"""
from collections import Counter
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random

from build_navigation_v3 import HEADERS, render_request, make_record, stable_hash
from game_tasks import source_group_id, transform_state, valid_actions
from train_pipeline_decisions import data_schema_summary, read_training_records, validate_training_row

SPLITS = ("train", "dev", "calibration", "test", "ood")
VIEWS = ("ascii_single", "ascii_multi", "coords_single", "coords_multi")
TEACHER_FIELDS = {"native_probs", "rounding", "label_source", "target_kind", "model"}


def render_view_request(state, split="rollout", representation="coords", candidate_order=None):
    public = render_request(state, split=split, candidate_order=candidate_order)
    if representation == "coords":
        return public
    if representation != "ascii":
        raise ValueError("representation must be ascii or coords")
    size = state["size"]
    cells = [["."] * size for _ in range(size)]
    for r, c in state["walls"]:
        cells[r][c] = "#"
    cells[state["goal"][0]][state["goal"][1]] = "G"
    cells[state["position"][0]][state["position"][1]] = "A"
    board = "\n".join(" ".join(row) for row in cells)
    public["state"] = (f"{HEADERS[split]}\nGrid {size}x{size}. North is up; east is right.\n"
                       "Each legal orthogonal move costs 1; no diagonals. A=agent, G=goal, #=wall, .=open.\n" + board)
    public["questions"]["action"]["criteria"] = {
        action: f"Move one cell {action}." for action in public["questions"]["action"]["criteria"]}
    return public


def read_rows(path):
    rows, _ = read_training_records(path)
    return rows


def minimal_record(row, keep_teacher):
    allowed = {"id", "state_id", "family_id", "split", "state", "questions", "gold", "gold_probs",
               "gold_probs_kind", "gold_label_kind", "optimal_actions", "metadata"}
    result = {k: copy.deepcopy(v) for k, v in row.items() if k in allowed}
    metadata_allowed = {"source", "license", "source_group_id", "template_id", "language", "environment_state",
                        "exposure_slot", "physical_state_hash", "canonical_source_id", "coverage", "representation",
                        "d4_symmetry", "pre_transform_start", "single_original_start"}
    result["metadata"] = {k: v for k, v in result.get("metadata", {}).items() if k in metadata_allowed}
    if keep_teacher and row.get("teacher") is not None:
        result["teacher"] = {k: copy.deepcopy(v) for k, v in row["teacher"].items() if k in TEACHER_FIELDS}
    validate_training_row(result)
    return result


def build_views(canonical_path, labels_path, replay_path, seed=17):
    canonical = read_rows(canonical_path)
    labelled = read_rows(labels_path)
    label_by_id = {r["id"]: r for r in labelled}
    canonical_ids = {r["id"] for r in canonical}
    if set(label_by_id) - canonical_ids:
        raise ValueError("Teacher labels contain IDs outside frozen canonical V3")
    for row in canonical:
        label = label_by_id.get(row["id"])
        if label is not None:
            for key in ("state", "questions"):
                if json.dumps(label[key], ensure_ascii=False) != json.dumps(row[key], ensure_ascii=False):
                    raise ValueError("Teacher input differs from frozen canonical V3")
            for key in ("gold", "gold_probs", "gold_probs_kind", "split", "state_id"):
                if label.get(key) != row.get(key):
                    raise ValueError("Teacher wrapper changed independent source data")
            if "teacher" in label:
                row["teacher"] = label["teacher"]
    bysplit = {s: [r for r in canonical if r["split"] == s] for s in SPLITS}
    replay = [r for r in read_rows(replay_path) if r["split"] == "train"
              and r.get("metadata", {}).get("environment_state", {}).get("game") != "grid_navigation"]
    if len(replay) != 984:
        raise ValueError(f"Expected exactly984 V2 nongrid train replay records, got{len(replay)}")
    groups = {}
    for row in bysplit["train"]:
        groups.setdefault(row["metadata"]["source_group_id"], []).append(row)
    if len(groups) != 300 or any(len(rows) != 8 for rows in groups.values()):
        raise ValueError("Expected300 training maps with8 canonical exposure slots each")
    slots = []
    single_start_choices = {}
    for group, rows in sorted(groups.items()):
        positions = sorted({tuple(r["metadata"]["pre_transform_start"]) for r in rows})
        choice_rng = random.Random(int(stable_hash([seed, group, "single_start"]), 16))
        one_start = list(choice_rng.choice(positions))
        single_start_choices[group] = one_start
        rows = sorted(rows, key=lambda r: r["metadata"]["d4_symmetry"])
        for row in rows:
            symmetry = row["metadata"]["d4_symmetry"]
            slot = f"navigation_v3_exposure:train:{stable_hash(group)[:24]}:d4_{symmetry}"
            prototype = {"game": "grid_navigation", "size": row["metadata"]["environment_state"]["size"],
                         "walls": row["metadata"]["original_map_walls"], "goal": row["metadata"]["original_map_goal"],
                         "position": one_start}
            single_env = transform_state(prototype, symmetry)
            if source_group_id(single_env) != group:
                raise ValueError("Single-start transform changed source map")
            single = make_record(single_env, "train", rng=random.Random(int(stable_hash([seed, slot, "order"]), 16)))
            slots.append({"id": slot, "multi": row, "single": single, "group": group,
                          "d4": symmetry, "single_original_start": one_start})
    views = {}
    audit = {}
    for view in VIEWS:
        representation, coverage = view.split("_")
        records = []
        for slot in slots:
            row = copy.deepcopy(slot[coverage])
            env = row["metadata"]["environment_state"]
            row.update(render_view_request(env, "train", representation,
                                           list(row["questions"]["action"]["criteria"])))
            canonical_id = row["id"]
            row["id"] = slot["id"]
            # state_id remains the physical-state identity; repeated exposures are not new unique states.
            row["metadata"].update(exposure_slot=slot["id"], physical_state_hash=stable_hash(env),
                                    canonical_source_id=canonical_id, representation=representation, coverage=coverage,
                                    d4_symmetry=slot["d4"], single_original_start=slot["single_original_start"])
            records.append(minimal_record(row, keep_teacher=view == "coords_multi"))
        records.extend(minimal_record(row, keep_teacher=view == "coords_multi") for row in replay)
        # Coverage is a TRAIN factor. Every model evaluates identical unseen physical states.
        for split in SPLITS[1:]:
            for canonical_row in bysplit[split]:
                row = copy.deepcopy(canonical_row)
                env = row["metadata"]["environment_state"]
                row.update(render_view_request(env, split, representation,
                                               list(row["questions"]["action"]["criteria"])))
                row["metadata"].update(physical_state_hash=stable_hash(env), canonical_source_id=row["id"],
                                        representation=representation, coverage="shared_evaluation")
                records.append(minimal_record(row, keep_teacher=view == "coords_multi"))
        if len(records) != 3984 or sum(len(r["questions"]) for r in records) != 11952:
            raise ValueError("Wrong frozen view record/question count")
        ids = [r["id"] for r in records]
        if len(set(ids)) != len(ids):
            raise ValueError("Exposure record IDs must be unique")
        views[view] = records
        nav = records[:2400]
        physical = {r["metadata"]["physical_state_hash"] for r in nav}
        rendered = {stable_hash([r["state"], r["questions"]]) for r in nav}
        audit[view] = {**data_schema_summary(records), "navigation_train_exposure_records": len(nav),
                       "navigation_train_maps": len(groups), "navigation_train_unique_physical_states": len(physical),
                       "navigation_train_repeated_physical_state_exposures": len(nav) - len(physical),
                       "navigation_train_unique_rendered_inputs": len(rendered),
                       "navigation_train_unique_original_starts": 300 if coverage == "single" else 1874,
                       "replay_train_records": len(replay), "replay_train_questions": 3 * len(replay),
                       "evaluation_physical_states_identical_across_coverage": True}
    common_order = [r["id"] for r in views["coords_multi"]]
    assert all([r["id"] for r in rows] == common_order for rows in views.values())
    for coverage in ("single", "multi"):
        a, b = views[f"ascii_{coverage}"], views[f"coords_{coverage}"]
        for ra, rb in zip(a, b):
            assert ra["state_id"] == rb["state_id"] and ra.get("gold_probs") == rb.get("gold_probs") and ra.get("gold") == rb.get("gold")
    for representation in ("ascii", "coords"):
        a = [r for r in views[f"{representation}_single"] if r["split"] != "train"]
        b = [r for r in views[f"{representation}_multi"] if r["split"] != "train"]
        assert [(r["state"], r["questions"], r["state_id"]) for r in a] == [(r["state"], r["questions"], r["state_id"]) for r in b]
    return views, audit, single_start_choices


def protocol_text(manifest):
    return "\n".join([
        "# V3 导航 2×2 与教师对照：固定协议", "",
        "此协议在V3学生测试结果产生前冻结。V2结果全部保留，V2 test已见，仅作历史参照。主展示预先指定coords/multi/seed17；不按新test选择最佳view。", "",
        "五个run：gold_ascii_single、gold_ascii_multi、gold_coords_single、gold_coords_multi，以及teacher_coords_multi。共同从v2_teacher_seed17最终checkpoint warm start，seed17、head0、1200full steps、batch12、micro4、max6000 padded tokens、maxlen512、BF16；不改网络或loss。各run仅按各自预定目标的新V3 dev CE选择checkpoint，test/ood只在训练与选择完成后评估。", "",
        "四个gold view的300张训练地图、D4曝光槽ID及记录顺序完全一致。multi使用canonical每槽起点；single每地图按固定hash RNG选一个原始起点，同样经过8种D4。重复物理状态保留为明确exposure slot，不称新增独立数据；manifest报告unique physical states和unique original starts。相同seed和步数下，当前均匀question sampler有相同slot采样机会，loss不再乘任何weight。", "",
        "表示因子只改变地图/候选的表示：ASCII没有显式坐标或候选destination，coords明确坐标、索引和合法下一格。任务说明、环境规则与程序gold语义一致。覆盖因子只改变TRAIN；新dev/calibration/test/ood的实际环境在所有view中完全相同，仅按表示因子渲染。", "",
        "每view包含2400条导航train曝光记录及984条相同V2 nongrid train replay（包含TTT/workflow/support，排除所有V2 grid、旧dev/calibration/test/ood）。train共3384记录/10152题；新dev/calibration/test/ood为120/120/240/120状态；总3984记录/11952题。", "",
        "只有coords_multi包保留最小化teacher字段供teacher arm和fidelity记录；gold目标不受teacher缺失/舍入隔离影响。其它gold view不需要teacher。teacher arm只排除无效teacher目标，覆盖数单列；这使teacher对照的eligible曝光与四个gold arm略有差异。", "",
        "固定控制器消融：greedy、学生p采样(T=1)、uniform random，可列oracle上界；同一组新test/ood地图、固定每episode RNG和相同步数上限，保留全部失败与成功。最优动作策略分布不是成功概率，不能称实际事件校准。", "",
        "相同question曝光并不等于相同token/FLOP；分别报告输入长度、训练时间与显存。此2×2可以比较表示和起点覆盖的效应及交互，但只有一个固定训练seed，仍不足以估计一般训练方差。", "",
        f"协议数据seed=17；canonical SHA256={manifest['source_sha256']['canonical']}；V2 replay源SHA256={manifest['source_sha256']['replay']}。原始文件均不修改。", "",
    ])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--canonical", type=Path, default=Path("research/private_navigation_v3/all.jsonl"))
    p.add_argument("--labels", type=Path, default=Path("research/private_navigation_v3/labeled.jsonl"))
    p.add_argument("--replay", type=Path, default=Path("research/private_pipeline_v2/merged.jsonl"))
    p.add_argument("--output-dir", type=Path, default=Path("research/private_navigation_v3/views"))
    p.add_argument("--seed", type=int, default=17)
    args = p.parse_args()
    if (args.output_dir / "manifest.json").exists():
        raise ValueError("Frozen views exist; not overwriting")
    sources = {"canonical": args.canonical, "labels": args.labels, "replay": args.replay}
    snapshots = {k: path.read_bytes() for k, path in sources.items()}
    views, audit, chosen = build_views(args.canonical, args.labels, args.replay, args.seed)
    if any(path.read_bytes() != snapshots[k] for k, path in sources.items()):
        raise ValueError("Source changed during assembly")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "openjev-navigation-v3-five-runs", "seed": args.seed,
                "source_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in snapshots.items()},
                "source_paths": {k: str(v) for k, v in sources.items()}, "views": audit,
                "teacher_fields_retained": sorted(TEACHER_FIELDS), "provider_metadata_or_credentials": False,
                "single_start_choices": chosen, "gold_slot_order_matched": True,
                "steps": 1200, "head_steps": 0, "effective_batch_questions": 12,
                "microbatch_questions": 4, "max_microbatch_tokens": 6000, "max_length": 512,
                "initial_checkpoint": "runs/v2_teacher_seed17", "main_display": "coords_multi_seed17",
                "new_test_used_for_selection": False}
    for view, rows in views.items():
        payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
        path = args.output_dir / f"{view}.jsonl"
        path.write_text(payload, encoding="utf-8")
        manifest["views"][view]["input_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
        # Full split/source-group validation on the actual serialized training package.
        read_training_records(path)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "protocol_zh.md").write_text(protocol_text(manifest), encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "views": audit}, ensure_ascii=False))


if __name__ == "__main__":
    main()
