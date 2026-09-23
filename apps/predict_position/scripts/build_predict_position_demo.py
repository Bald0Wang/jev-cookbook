#!/usr/bin/env python3
"""Export selected Predict Position recordings with full held-out aggregates.

Replay uses only frozen actions and CPU ViZDoom. Each transition is checked
against its source before lossless RGB media is installed in a fresh namespace.
No model inference, API requests, training, or reconstructed decisions occur.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import tempfile

from build_shooting_demo import (AtlasWriter, BASE_REVISION, BASE_SHA, COLS,
                                 CaptureGame, HEIGHT, ORDER, ROWS, WIDTH,
                                 match, read_rows, render_episode, require)
from replay_unified_episodes import load_json
from unified_game_pipeline import digest, file_digest

NANOJEV_SHA = "f68c47d66998231b86b7e91b4ed5e82ae23acf104c8b7cd6d165c3ac7b7ffe1b"
CASES_SHA = "d00f5b6aeaa9f2aac3e4b5010b31df4e86f77674cb588e17bc3f7d853e4a1f36"
OUTPUT_NAME = "predict_position_results.json"
MODEL_TEXT = {
    "jev": ("Jev", "Recorded Jev API action probabilities"),
    "nanojev": ("NanoJev", "0.6B · mixed-task expert SFT · step 400"),
    "base": ("Untuned Qwen", "Original Qwen3-0.6B language-model head · no task fine-tuning"),
}
IMPLEMENTATION = (Path(__file__).name, "build_shooting_demo.py", "unified_doom_env.py",
                  "unified_game_pipeline.py", "replay_unified_episodes.py")


class PredictCapture(CaptureGame):
    """All physical counters and real RGB at every available physical tick.

    An attack decision is not necessarily a projectile launch: the weapon has
    an animation delay and native firing rules. A shot is an observed ammo drop.
    """
    def capture(self):
        state = self.game.get_state()
        ammo = float(self.game.get_game_variable(self.variables.SELECTED_WEAPON_AMMO))
        kills = float(self.game.get_game_variable(self.variables.KILLCOUNT)) - self.initial_kills
        require(math.isfinite(ammo) and math.isfinite(kills), "Nonfinite physical counters")
        shot = bool(self.frames and ammo < self.frames[-1]["ammo"])
        available = state is not None and getattr(state, "screen_buffer", None) is not None
        if available:
            frame = state.screen_buffer
            require(tuple(frame.shape) == (HEIGHT, WIDTH, 3) and str(frame.dtype) == "uint8",
                    "Standard renderer must return 320x240 RGB uint8")
            rgb = frame.tobytes()
            self.last_sprite, self.image_tick = self.atlas.add(rgb), self.tick
            self.rgb_chain.update(self.tick.to_bytes(8, "big") + hashlib.sha256(rgb).digest())
        if not available:
            self.fallback_count += 1
        require(self.last_sprite is not None, "No real reset image exists")
        target_boxes = []
        if available:
            for label in getattr(state, "labels", ()):
                if (str(label.object_name) == "Cacodemon" and int(label.value) != 0 and
                        bool((state.labels_buffer == int(label.value)).any())):
                    box = [int(label.x), int(label.y), int(label.width), int(label.height)]
                    if box[2] > 0 and box[3] > 0:
                        target_boxes.append(box)
        self.frames.append({"tick": self.tick, "decision": self.decision, "action": self.action,
            "probabilities": copy.deepcopy(self.probabilities), "ammo": ammo, "kills": kills,
            "terminal": False, "success": kills > 0, "shot": shot,
            "sprite": dict(self.last_sprite), "image_tick": self.image_tick,
            "visual_state_available": available, "target_boxes": target_boxes})


def load_recordings(path, model_id, registry, registry_sha):
    """Bind complete 548-case source files, exact case specs, model and runtime."""
    path = Path(path)
    manifest_path = path.with_suffix(".manifest.json")
    manifest = load_json(manifest_path.read_text())
    sha = file_digest(path)
    require(manifest.get("schema_version") == "nanojev-unified-episodes-v1" and
            manifest.get("finished") is True and manifest.get("episode_sha256") == sha,
            f"{model_id}: incomplete or modified episode file")
    require(manifest.get("cases_sha256") == registry_sha, f"{model_id}: different frozen registry")
    policy = manifest["policy"]
    require(digest(policy) == manifest["continuation_policy_id"], f"{model_id}: policy identity mismatch")
    require(policy.get("controller") == "greedy" and policy.get("epsilon") == .1 and
            policy.get("sampling_seed") == 17 and policy.get("tie_break") == "lexicographic_first",
            f"{model_id}: different action controller")
    if model_id == "nanojev":
        require(policy.get("engine") == "checkpoint" and
                policy.get("checkpoint_sha256", {}).get("best.safetensors") == NANOJEV_SHA,
                "Expected the dev-selected mixed SFT step-400 checkpoint")
    elif model_id == "jev":
        require(policy.get("engine") == "jev" and policy.get("model") == "typesafe-ai/jev",
                "Expected the recorded Jev API policy")
    else:
        require(policy.get("engine") == "native_qwen_original_lm" and
                policy.get("model") == "Qwen/Qwen3-0.6B" and policy.get("revision") == BASE_REVISION and
                policy.get("project_training_steps") == 0 and
                policy.get("backend") == "untrained_qwen_lm_option_logits" and
                policy.get("checkpoint_sha256") == {"model.safetensors": BASE_SHA} and
                policy.get("original_weight_files_sha256") == {"model.safetensors": BASE_SHA},
                "Expected the unchanged original Qwen weights and vocabulary head")
    env_sha = file_digest(Path(__file__).with_name("unified_doom_env.py"))
    require(policy.get("source_sha256", {}).get("unified_doom_env.py") == env_sha,
            f"{model_id}: local environment implementation differs from the recorded source")
    snapshots = path.parent / manifest["source_snapshot"]
    require(file_digest(snapshots / "unified_doom_env.py") == env_sha,
            f"{model_id}: archived environment implementation differs")
    episodes = {}
    for episode in read_rows(path):
        cid = episode["case"]["id"]
        require(cid not in episodes and cid in registry and episode.get("complete") is True and
                type(episode.get("success")) is bool and
                episode.get("continuation_policy_id") == manifest["continuation_policy_id"],
                f"{model_id}: duplicate, unexpected, incomplete, or mixed-policy episode")
        match(registry[cid], episode["case"], f"{model_id}/{cid}/case")
        metrics = episode["final_info"]["episode_metrics"]
        require(episode["final_info"]["terminated"] is True and episode["final_info"]["truncated"] is False,
                f"{model_id}/{cid}: final state is not terminal")
        if episode["case"]["spec"].get("task") == "shooting":
            require(episode["success"] == (metrics["kills"] > 0) == metrics["success"],
                    f"{model_id}/{cid}: success disagrees with actual kill counters")
        episodes[cid] = episode
    selected = manifest["selected_cases"]
    require(len(selected) == len(set(selected)) and set(selected) == set(episodes) == set(registry),
            f"{model_id}: full case coverage differs")
    require(file_digest(path) == sha, f"{model_id}: source changed during read")
    provenance = {"path": str(path), "manifest_path": str(manifest_path), "episodes_sha256": sha,
                  "manifest_sha256": file_digest(manifest_path), "policy": policy,
                  "source_episode_count": len(episodes)}
    return episodes, provenance


def aggregate(sources, registry):
    result = {}
    for model_id in ORDER:
        result[model_id] = {}
        for split in ("test", "ood"):
            ids = [cid for cid, c in registry.items() if c["split"] == split and
                   c["spec"].get("scenario") == "predict_position"]
            require(len(ids) == 128, "Full Predict Position test and OOD each need 128 cases")
            successes = sum(sources[model_id][cid]["success"] for cid in ids)
            result[model_id][split] = {"episodes": len(ids), "successes": successes,
                                       "success_rate": successes / len(ids)}
    return result


def choose_illustrations(config, sources, registry):
    rows = config["cases"]
    require(rows and len({row["id"] for row in rows}) == len(rows), "Duplicate display cases")
    require(config["default_case_id"] in {row["id"] for row in rows}, "Default case is absent")
    for row in rows:
        require(row["id"] in registry, "Display case is absent from the frozen registry")
        case = registry[row["id"]]
        require(case["split"] == "test" and case["spec"].get("scenario") == "predict_position",
                "Display selection must use Predict Position test cases")
        actual = {k: sources[k][row["id"]]["success"] for k in ORDER}
        match(row["expected_success"], actual, row["id"] + "/selection_outcomes")
    return rows, {"rule": config["selection_rule"], "selected_case_id": config["default_case_id"],
                  "selected_case_ids": [r["id"] for r in rows], "outcome_selected": True,
                  "aggregate_scope": "All 128 frozen test cases; OOD separately uses all 128 frozen OOD cases",
                  "selection_changes_training_or_evaluation": False}


def add_events(system):
    frames = system["frames"]
    shot_ticks = []
    events = []
    previous_ammo = frames[0]["ammo"]
    for frame in frames:
        expected = frame["ammo"] < previous_ammo
        require(frame["shot"] == expected, "Shot marker must equal a real ammo decrease")
        if expected:
            shot_ticks.append(frame["tick"])
            events.append({"type": "shot", "tick": frame["tick"], "decision": frame["decision"],
                           "ammo_before": previous_ammo, "ammo_after": frame["ammo"]})
        previous_ammo = frame["ammo"]
    require(sum(e["ammo_before"] - e["ammo_after"] for e in events) == system["ammo_consumed"],
            "Shot timeline and episode ammo total disagree")
    events.append({"type": "hit" if system["success"] else "episode_end", "tick": system["total_ticks"],
                   "outcome": system["outcome"]})
    system["shot_ticks"], system["events"] = shot_ticks, events
    system["first_shot_tick"] = shot_ticks[0] if shot_ticks else None
    system["initial_ammo"] = frames[0]["ammo"]
    return system


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jev", type=Path, default=Path("runs/sonic_unified_sft_v1/jev_parallel_recovery_v2/episodes.jsonl"))
    parser.add_argument("--nanojev", type=Path, default=Path("runs/sonic_unified_sft_v1/experiment/selected_test.jsonl"))
    parser.add_argument("--base", type=Path, default=Path("runs/sonic_unified_sft_v1/native_test.jsonl"))
    parser.add_argument("--cases", type=Path, default=Path("runs/sonic_unified_sft_v1/test_cases.jsonl"))
    parser.add_argument("--selection", type=Path, default=Path("configs/predict_position_demo_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("web/dev"))
    parser.add_argument("--receipt", type=Path, default=Path("runs/predict_position_demo_v1/build_manifest.json"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    registry_sha = file_digest(args.cases)
    require(registry_sha == CASES_SHA, "Expected the original frozen 548-case registry")
    cases = read_rows(args.cases)
    registry = {c["id"]: c for c in cases}
    require(len(cases) == len(registry) == 548, "Expected 548 distinct frozen cases")
    sources, provenance = {}, {}
    for model_id in ORDER:
        sources[model_id], provenance[model_id] = load_recordings(getattr(args, model_id), model_id, registry, registry_sha)
    selection_sha = file_digest(args.selection)
    config = load_json(args.selection.read_text())
    illustrations, selection = choose_illustrations(config, sources, registry)
    summary = aggregate(sources, registry)
    if args.validate_only:
        print(json.dumps({"passed": True, "selection": selection, "summary": summary}), flush=True)
        return 0
    require(not args.output.is_symlink() and not (args.output / "media").is_symlink(), "Output directories cannot be symlinks")
    require(not (args.output / OUTPUT_NAME).exists() and not args.receipt.exists(),
            "Use a fresh Predict Position output and receipt; existing recordings are preserved")
    implementation = {name: file_digest(Path(__file__).with_name(name)) for name in IMPLEMENTATION}
    namespace = digest({"sources": provenance, "cases": registry_sha, "selection": selection_sha,
                        "implementation": implementation})[:12]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="predict-position-build-", dir=args.output.parent) as temporary:
        staging = Path(temporary)
        demos, audits, assets = [], [], []
        for row in illustrations:
            case = registry[row["id"]]
            systems, budgets = [], []
            for model_id in ORDER:
                prefix = f"predict_position_{namespace}_{model_id}_{digest(case['id'])[:12]}"
                writer = AtlasWriter(staging / "media", prefix)
                system, audit, budget = render_episode(sources[model_id][case["id"]], model_id, writer,
                                                       capture_factory=PredictCapture)
                add_events(system)
                systems.append(system); audits.append(audit); assets.extend(audit["assets"]); budgets.append(budget)
                print(json.dumps({"case": case["id"], "model": model_id, "physical_ticks": system["total_ticks"],
                                  "shot_ticks": system["shot_ticks"], "success": system["success"], "replay_passed": True}), flush=True)
            require(len(set(budgets)) == 1, "Compared systems have different physical task deadlines")
            demos.append({"id": case["id"], "title": row["title"], "description": row["description"],
                          "split": case["split"], "seed": case["seed"], "frame_skip": case["spec"]["frame_skip"],
                          "max_ticks": budgets[0], "systems": systems})
        illustration_summary = {model_id: {"test": {"episodes": len(demos),
            "successes": sum(next(s for s in c["systems"] if s["id"] == model_id)["success"] for c in demos)}}
            for model_id in ORDER}
        data = {"schema": "nanojev-shooting-demo-v1", "task": "predict_position", "ticks_per_second": 35,
                "default_case_id": config["default_case_id"],
                "models": [{"id": k, "name": MODEL_TEXT[k][0], "description": MODEL_TEXT[k][1]} for k in ORDER],
                "cases": demos, "summary": summary, "illustration_summary": illustration_summary,
                "protocol": {"synchronization": "physical_tick", "ticks_per_second": 35,
                    "frame_zero": "actual reset state; source scenario begins at native episode tick 16",
                    "decision_index": "zero at reset; one-based recorded decision producing each subsequent tick",
                    "probabilities": "original model action probabilities before epsilon exploration, not hit probabilities",
                    "controller": "greedy", "epsilon": .1, "sampling_seed": 17,
                    "image_sampling": "Real RGB at every available physical tick; every physical state retained",
                    "image_fallback": "When native state is unavailable, hold the preceding real image; image_tick identifies it",
                    "terminal_playback": "Freeze each system at its real terminal transition while the shared clock continues",
                    "shot": "Observed decrease in SELECTED_WEAPON_AMMO; an attack decision alone is not a shot",
                    "success": "Positive observed kill-count delta before the task deadline",
                    "selection": selection, "case_file_sha256": registry_sha,
                    "source_episodes_sha256": {k: v["episodes_sha256"] for k, v in provenance.items()},
                    "selected_checkpoint_sha256": NANOJEV_SHA, "new_model_calls": 0, "new_api_calls": 0}}
        data_path = staging / OUTPUT_NAME
        data_path.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n")
        generated = [{"path": OUTPUT_NAME, "sha256": file_digest(data_path), "bytes": data_path.stat().st_size}, *assets]
        for k, p in provenance.items():
            require(file_digest(p["path"]) == p["episodes_sha256"] and file_digest(p["manifest_path"]) == p["manifest_sha256"],
                    f"{k}: input changed during replay")
        require(all(file_digest(Path(__file__).with_name(n)) == h for n, h in implementation.items()),
                "Replay source changed during rendering")
        require(file_digest(args.cases) == registry_sha and file_digest(args.selection) == selection_sha,
                "Case or selection file changed during rendering")
        import PIL
        receipt = {"schema": "nanojev-predict-position-media-receipt-v1", "passed": True,
            "created_at": datetime.now(timezone.utc).isoformat(), "output_directory": str(args.output.resolve()),
            "source_cases": str(args.cases), "cases_sha256": registry_sha, "sources": provenance,
            "selection_sha256": selection_sha, "selection": selection, "implementation_sha256": implementation,
            "runtime": {"python": platform.python_version(), "pillow": PIL.__version__},
            "rendering": {"width": WIDTH, "height": HEIGHT, "atlas_columns": COLS, "atlas_rows": ROWS,
                "encoding": "lossless WebP; decoded RGB checked byte-for-byte", "extra_simulation_ticks": 0,
                "image_stride_ticks": 1, "state_stride_ticks": 1},
            "validation": {"episodes": len(audits), "all_passed": True,
                "decisions": sum(a["decisions"] for a in audits), "physical_ticks": sum(a["physical_ticks"] for a in audits),
                "float_absolute_tolerance": 1e-9, "state_text": "exact", "all_transition_info_fields": True},
            "full_cohort_summary": summary, "episodes": audits, "generated_files": generated}
        # Only the new namespace and its new index may be installed. Existing
        # Basic assets, unrelated files and previous receipts are not modified.
        require(not (args.output / OUTPUT_NAME).exists() and not args.receipt.exists(), "Output appeared during replay")
        for item in assets:
            require(not (args.output / item["path"]).exists(), "Generated asset destination already exists")
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "media").mkdir(exist_ok=True)
        for item in assets:
            os.replace(staging / item["path"], args.output / item["path"])
        os.replace(data_path, args.output / OUTPUT_NAME)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open("x") as handle:
            json.dump(receipt, handle, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps({"passed": True, "output": str(args.output), "receipt": str(args.receipt),
                      "cases": len(demos), "summary": summary, "generated_bytes": sum(i["bytes"] for i in generated)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
