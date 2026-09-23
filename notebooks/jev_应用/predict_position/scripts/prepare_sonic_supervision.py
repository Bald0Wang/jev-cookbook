#!/usr/bin/env python3
"""Replace Predict Position with verified Sonic action targets; retain other rows verbatim.

This offline converter never runs a game or model. Complete raw episodes remain
unchanged. Supervision includes every pre-action state with positive ammo,
regardless of the eventual outcome. Expert targets and executed actions differ.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path

from train_pipeline_decisions import SPLITS, validate_training_row
from train_unified_games import file_sha256, read_unified_dataset, validate_unified_records
from unified_game_pipeline import behavior_distribution, digest, encode, environment_group, policy_request

DEFAULT_PROTOCOL = Path("configs/sonic_predict_supervision_v1.json")
ACTIONS = {"left", "right", "shoot", "noop"}


def read_json(path):
    return json.loads(Path(path).read_text())


def is_pp(row):
    meta = row["metadata"]
    return meta["task"] == "shooting" and meta.get("spec", {}).get("scenario") == "predict_position"


def argmax(probs):
    return min(k for k in probs if probs[k] == max(probs.values()))


def distribution(value, name):
    if (not isinstance(value, dict) or set(value) != ACTIONS or
            any(isinstance(p, bool) or not isinstance(p, (int, float)) or
                not math.isfinite(p) or not 0 <= p <= 1 for p in value.values()) or
            not math.isclose(math.fsum(value.values()), 1., abs_tol=1e-8, rel_tol=0)):
        raise ValueError(name + " must be a complete finite four-action probability simplex")
    return value


def pre_action_ammo(step):
    public = json.loads(step["observation"]["state"])
    history = public.get("observed_history")
    if (public.get("scenario") != "predict_position" or public.get("screen_size") != [320, 240]
            or public.get("terminal") is not False or not isinstance(history, list)
            or not 1 <= len(history) <= 4):
        raise ValueError("Expected the standard live PP observation with up to four history frames")
    ammo = history[-1].get("ammo")
    if isinstance(ammo, bool) or not isinstance(ammo, (int, float)) or not math.isfinite(ammo) or ammo < 0:
        raise ValueError("Pre-action ammo must be a nonnegative observed number")
    if "pre_action_ammo" in step and step["pre_action_ammo"] != ammo:
        raise ValueError("Declared pre-action ammo differs from the visible observation")
    return ammo


def load_protocol(path):
    path = Path(path)
    protocol = read_json(path)
    if protocol.get("schema_version") != "nanojev-sonic-supervision-v1":
        raise ValueError("Wrong Sonic supervision protocol")
    case_path = Path(protocol["case_file"])
    if file_sha256(case_path) != protocol["case_sha256"]:
        raise ValueError("Frozen case file hash mismatch")
    cases = [json.loads(line) for line in case_path.read_text().splitlines() if line.strip()]
    ids, groups = set(), set()
    counts = Counter()
    for case in cases:
        spec = case["spec"]
        group = environment_group(case)
        if (case["id"] in ids or group in groups or case["split"] not in SPLITS or
                spec.get("task") != "shooting" or spec.get("scenario") != "predict_position" or
                spec.get("history_length") != 4):
            raise ValueError("Cases require unique PP seeds/groups, valid splits, and history_length=4")
        ids.add(case["id"])
        groups.add(group)
        counts[case["split"]] += 1
    if set(counts) != set(SPLITS) or dict(counts) != protocol["case_counts"]:
        raise ValueError("Registered cases must cover exactly all five declared splits")
    return protocol, cases, file_sha256(path)


def validate_collection(collection, protocol, cases, protocol_sha):
    if (collection.get("finished") is not True or type(collection.get("limit")) is not int or
            collection["limit"] != 0 or collection.get("config_sha256") != protocol_sha or
            collection.get("cases_sha256") != protocol["case_sha256"]):
        raise ValueError("Only the completed full collection from the frozen protocol is accepted")
    if (collection.get("selected_cases") != [c["id"] for c in cases] or
            collection.get("selected_cases_sha256") != digest(cases) or
            any(collection.get(k) != len(cases) for k in ("episodes", "selected_episodes", "selected_before_limit")) or
            collection.get("split_episodes") != protocol["case_counts"]):
        raise ValueError("Collection is missing registered cases or split coverage")
    policy, primary = collection["policy"], protocol["primary"]
    if (collection.get("continuation_policy_id") != digest(policy) or
            policy.get("engine") != "sonic_doom_pure_vision_pp"):
        raise ValueError("Sonic policy identity does not match its content hash")
    identity = policy["model"]
    for key, source in (("model", "checkpoint_repository"), ("revision", "checkpoint_revision"),
                        ("checkpoint_sha256", "checkpoint_sha256")):
        if identity.get(key) != primary[source]:
            raise ValueError("Expert checkpoint identity differs from the protocol: " + key)
    for key in ("controller", "epsilon", "sampling_seed"):
        if policy.get(key) != primary[key]:
            raise ValueError("Expert controller differs from the protocol: " + key)
    if primary.get("config_sha256") is not None and identity.get("config_sha256") != primary["config_sha256"]:
        raise ValueError("Expert configuration differs from the protocol")
    if protocol.get("assets") is not None and policy.get("assets") != protocol["assets"]:
        raise ValueError("Expert and standard game assets differ from the protocol")


def validate_episode(episode, case, collection):
    """Check complete public observation chains and targets without importing a simulator."""
    if (episode.get("case") != case or episode.get("complete") is not True or
            episode.get("continuation_policy_id") != collection["continuation_policy_id"] or
            type(episode.get("success")) is not bool):
        raise ValueError("Incomplete episode or case/policy identity mismatch")
    final = episode["final_info"]
    if (final.get("terminated") is not True or final.get("truncated") or
            final.get("success") != episode["success"] or episode["final_observation"]["candidates"]):
        raise ValueError("Episode requires a real terminal outcome and empty final candidates")
    replay = episode.get("standard_independent_replay", {})
    if replay.get("passed") is not True:
        raise ValueError("Standard observation replay receipt must pass")
    steps = episode["steps"]
    if not steps:
        raise ValueError("The registered PP cases require at least one decision")
    policy = collection["policy"]
    for index, step in enumerate(steps):
        obs, probs = step["observation"], distribution(step["policy_probs"], "Expert policy")
        if (set(obs["candidates"]) != ACTIONS or step["request"] != policy_request(obs, case["id"]) or
                (index == 0 and obs != episode["initial_observation"])):
            raise ValueError("Request does not match the unchanged standard observation")
        pre_action_ammo(step)
        if step["expert_argmax"] != argmax(probs):
            raise ValueError("Hard label is not the expert argmax")
        behavior = distribution(step["behavior_probs"], "Behavior policy")
        expected = behavior_distribution(probs, policy["controller"], policy["epsilon"])
        if any(not math.isclose(behavior[k], expected[k], rel_tol=0, abs_tol=1e-12) for k in ACTIONS):
            raise ValueError("Behavior probabilities differ from the registered controller")
        if step["action"] not in ACTIONS or behavior[step["action"]] <= 0:
            raise ValueError("Executed action is outside the offered behavior support")
        if step["expert"].get("probs") != probs or step["expert"].get("argmax") != step["expert_argmax"]:
            raise ValueError("Nested expert receipt disagrees with the action target")
        # Pure-stdlib validation, shared with collection; no actor or simulator is constructed.
        from sonic_predict_data import probability_check
        probability_check({"probabilities": probs, "raw_probabilities": step["policy_probs_raw"],
                           "logits": step["expert"]["raw_logits"],
                           "raw_probability_sum": step["raw_probability_sum"]})
        if step["normalization_applied"] != (step["raw_probability_sum"] != 1.):
            raise ValueError("Expert normalization receipt disagrees with the raw probability mass")
        following = steps[index + 1]["observation"] if index + 1 < len(steps) else episode["final_observation"]
        if (step.get("next_observation_sha256") != digest(following) or step.get("truncated") or
                step.get("terminated") != (index == len(steps) - 1)):
            raise ValueError("Broken public observation chain or incomplete terminal sequence")
    if replay.get("decisions") != len(steps):
        raise ValueError("Independent replay decision count differs")


def training_row(episode, step, index, collection, soft):
    case, obs = episode["case"], step["observation"]
    group, probs = environment_group(case), step["policy_probs"]
    identity = digest([episode["continuation_policy_id"], case["id"], index, "policy"])
    row = {**policy_request(obs, identity),
           "state_id": digest([group, case["seed"], index, obs["state"]]),
           "family_id": "unified_shooting", "split": case["split"],
           "gold": {"action": step["expert_argmax"]},
           "gold_label_kind": {"action": "reference_argmax_compatibility"},
           "expert": {**copy.deepcopy(collection["policy"]["model"]),
                      "policy_probs": copy.deepcopy(probs),
                      "policy_probs_raw": copy.deepcopy(step["policy_probs_raw"]),
                      "raw_probability_sum": step["raw_probability_sum"],
                      "normalization_applied": step["normalization_applied"]},
           "metadata": {"task": "shooting", "record_role": "policy",
                        "policy_target_kind": "expert_distribution" if soft else "expert_action",
                        "episode_id": case["id"], "source_group_id": group,
                        "decision_index": index, "spec": copy.deepcopy(case["spec"]),
                        "public_observation_sha256": digest(obs["state"]),
                        "executed_action": step["action"], "conditioned_action": step["action"],
                        "continuation_policy_id": episode["continuation_policy_id"],
                        "episode_success": episode["success"], "remaining_steps": obs["remaining_steps"],
                        "pre_action_ammo": pre_action_ammo(step),
                        "supervision_filter": "pre_action_observed_ammo_positive",
                        "observation_source": "standard_320x240_visible_state_history4",
                        "expert_argmax": step["expert_argmax"],
                        "behavior_probs": copy.deepcopy(step["behavior_probs"]),
                        "sampling_draw": step["sampling_draw"],
                        "expert_pixel_input": copy.deepcopy(step["pixel_input"]),
                        "mirror_tick_checks_sha256": digest(step["mirror_tick_checks"])}}
    if soft:
        row["gold_probs"] = {"action": copy.deepcopy(probs)}
        row["gold_probs_kind"] = {"action": "expert_policy_distribution"}
    validate_training_row(row)
    return row


def preserve_original(original):
    rows, manifest, files, _ = read_unified_dataset(original)
    if any(row["metadata"]["record_role"] != "policy" for row in rows):
        raise ValueError("Original retained data must contain policy rows only")
    chunks, retained, removed = {}, Counter(), Counter()
    for split in SPLITS:
        path = original / (split + ".jsonl")
        if manifest.get("split_sha256", {}).get(split) != file_sha256(path):
            raise ValueError("Original split hash mismatch")
        chunks[split] = []
        for line in path.read_bytes().splitlines(keepends=True):
            if not line.strip():
                continue
            row = json.loads(line)
            if is_pp(row):
                removed[split] += 1
            else:
                # Refuse to alter a retained unterminated line during appending.
                if not line.endswith(b"\n"):
                    raise ValueError("Retained JSONL rows need newline terminators for exact-byte retention")
                chunks[split].append(line)
                retained[(split, row["metadata"]["task"], row["metadata"].get("spec", {}).get("scenario", ""))] += 1
    return rows, manifest, files, chunks, retained, removed


def prepare(original, expert, output, protocol_path=DEFAULT_PROTOCOL):
    original, expert, output = map(Path, (original, expert, output))
    if output.exists():
        raise ValueError("Use a fresh output directory")
    protocol, cases, protocol_sha = load_protocol(protocol_path)
    old_rows, old_manifest, old_files, retained, retained_counts, removed = preserve_original(original)
    old_pp_groups = {r["metadata"].get("source_group_id") for r in old_rows if is_pp(r)}
    historical_overlap = {environment_group(c) for c in cases} & old_pp_groups
    if historical_overlap:
        raise ValueError("New PP cases overlap previous PP environment groups")
    collection = read_json(expert / "episodes.manifest.json")
    validate_collection(collection, protocol, cases, protocol_sha)
    episode_path = expert / "episodes.jsonl"
    if collection.get("episode_sha256") != file_sha256(episode_path):
        raise ValueError("Raw episode file hash mismatch")
    added = {arm: {s: [] for s in SPLITS} for arm in ("hard", "soft")}
    row_sets = {arm: [] for arm in added}
    audit = {s: {"episodes": 0, "successes": 0, "failures": 0, "raw_decisions": 0,
                 "kept_decisions": 0, "filtered_no_ammo": 0, "kept_from_successes": 0,
                 "kept_from_failures": 0, "episodes_without_supervision": 0} for s in SPLITS}
    seen = 0
    with episode_path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            if seen >= len(cases):
                raise ValueError("Unregistered extra episode")
            episode, case = json.loads(line), cases[seen]
            validate_episode(episode, case, collection)
            seen += 1
            cell = audit[case["split"]]
            cell["episodes"] += 1
            cell["successes" if episode["success"] else "failures"] += 1
            kept = 0
            for index, step in enumerate(episode["steps"]):
                cell["raw_decisions"] += 1
                if pre_action_ammo(step) <= 0:
                    cell["filtered_no_ammo"] += 1
                    continue
                kept += 1
                cell["kept_decisions"] += 1
                cell["kept_from_successes" if episode["success"] else "kept_from_failures"] += 1
                for arm in added:
                    row = training_row(episode, step, index, collection, arm == "soft")
                    row_sets[arm].append(row)
                    added[arm][case["split"]].append((encode(row) + "\n").encode())
            cell["episodes_without_supervision"] += int(kept == 0)
    if seen != len(cases) or {s: audit[s]["raw_decisions"] for s in SPLITS} != collection.get("split_records"):
        raise ValueError("Raw episode count or decision count is incomplete")
    for arm, rows in row_sets.items():
        validate_unified_records([r for r in old_rows if not is_pp(r)] + rows, {"continuation_policy_id": None})
    report = {"schema_version": "nanojev-sonic-preparation-audit-v1", "passed": True,
              "protocol_sha256": protocol_sha, "raw_episode_sha256": collection["episode_sha256"],
              "raw_collection_manifest_sha256": file_sha256(expert / "episodes.manifest.json"),
              "original_source_sha256": {p.name: file_sha256(p) for p in old_files},
              "retained_rows": {"/".join(k): v for k, v in sorted(retained_counts.items())},
              "retained_row_bytes_sha256": {s: hashlib.sha256(b"".join(retained[s])).hexdigest() for s in SPLITS},
              "removed_old_pp_rows": dict(removed), "new_pp": audit,
              "historical_pp_group_overlap": len(historical_overlap),
              "unique_new_pp_groups": len({environment_group(c) for c in cases}),
              "new_pp_group_sha256_by_split": {
                  s: digest(sorted(environment_group(c) for c in cases if c["split"] == s)) for s in SPLITS},
              "same_observation_text_across_splits": "Allowed when latent episode/source groups differ",
              "retention_rule": "Maze, Snake and Basic retained as exact original JSONL row bytes in the same split",
              "supervision_rule": "All and only pre-action observed ammo > 0; no outcome filter; complete raw episodes unchanged",
              "hard_soft_inputs_identical": True, "outputs": {}}
    report["preparation_source_sha256"] = {
        name: file_sha256(Path(__file__).with_name(name)) for name in
        ("prepare_sonic_supervision.py", "sonic_predict_data.py", "unified_game_pipeline.py",
         "train_unified_games.py", "train_pipeline_decisions.py")}
    output.mkdir(parents=True)
    for arm in added:
        dest = output / arm
        dest.mkdir()
        for split in SPLITS:
            (dest / (split + ".jsonl")).write_bytes(b"".join(retained[split] + added[arm][split]))
        manifest = {"schema_version": "nanojev-unified-training-v1", "continuation_policy_id": None,
                    "policy_only": True, "policy_target_kind": "mixed_explicit_policy_sources",
                    "replaced_pp_target_kind": "expert_action" if arm == "hard" else "expert_distribution",
                    "protocol_sha256": protocol_sha, "source_manifest_sha256": report["original_source_sha256"]["manifest.json"],
                    "original_split_sha256": old_manifest["split_sha256"],
                    "episode_sha256": collection["episode_sha256"], "collection_policy": collection["policy"],
                    "raw_collection_manifest_sha256": report["raw_collection_manifest_sha256"],
                    "preparation_source_sha256": report["preparation_source_sha256"],
                    "selection_audit": audit, "retention_rule": report["retention_rule"],
                    "supervision_rule": report["supervision_rule"],
                    "split_sha256": {s: file_sha256(dest / (s + ".jsonl")) for s in SPLITS}}
        (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        _, _, _, validation = read_unified_dataset(dest)
        report["outputs"][arm] = {"split_sha256": manifest["split_sha256"], "validation": validation}
    (output / "preparation_audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--expert", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    args = parser.parse_args()
    report = prepare(args.original, args.expert, args.output, args.protocol)
    print(json.dumps({"passed": report["passed"], "new_pp": report["new_pp"]}))


if __name__ == "__main__":
    main()
