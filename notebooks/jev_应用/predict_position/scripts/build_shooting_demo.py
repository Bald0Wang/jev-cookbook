#!/usr/bin/env python3
"""Replay frozen Basic episodes and export real per-tick RGB WebP sprite atlases.

Requires ViZDoom and Pillow at execution time, never a model, GPU or API.
Only shooting_results.json and this builder's media/shooting_* files are written
inside --output. A separate receipt binds recordings, implementation and media.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import tempfile
from datetime import datetime, timezone

from replay_unified_episodes import differences, load_json
from unified_doom_env import UnifiedDoomEnv
from unified_game_pipeline import digest, file_digest

WIDTH, HEIGHT, COLS, ROWS = 320, 240, 8, 8
ORDER = ("jev", "nanojev", "base")
NANOJEV_SHA = "38116340795de1c82369b7fe15819d92d79600a7b4dc7a3cd0d4390cb6782639"
BASE_SHA = "f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b"
BASE_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
MODEL_TEXT = {
    "jev": ("Jev", "Recorded Jev API decisions"),
    "nanojev": ("NanoJev", "0.6B · latest trained action model"),
    "base": ("Untuned Qwen", "Original Qwen3-0.6B language-model head · no task fine-tuning"),
}
RECEIPT_SCHEMA = "nanojev-shooting-media-receipt-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def match(recorded, replayed, where):
    mismatch = differences(recorded, replayed, where)
    if mismatch:
        raise ValueError(json.dumps({"where": where, "mismatch_count": len(mismatch),
                                     "first_mismatch": mismatch[0]}, allow_nan=False))


def read_rows(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [load_json(line) for line in handle if line.strip()]


def load_source(path, model_id, cases):
    path = Path(path)
    manifest_path = path.with_suffix(".manifest.json")
    manifest = load_json(manifest_path.read_text())
    episode_sha = file_digest(path)
    require(manifest.get("schema_version") == "nanojev-unified-episodes-v1" and manifest.get("finished") is True,
            f"{model_id}: source manifest is incomplete or has the wrong schema")
    require(manifest.get("episode_sha256") == episode_sha, f"{model_id}: episode file SHA mismatch")
    policy = manifest["policy"]
    require(digest(policy) == manifest["continuation_policy_id"], f"{model_id}: policy identity mismatch")
    if model_id == "jev":
        require(policy.get("engine") == "jev" and policy.get("model") == "typesafe-ai/jev", "Expected the recorded Jev API policy")
    elif model_id == "nanojev":
        require(policy.get("engine") == "checkpoint" and
                policy.get("checkpoint_sha256", {}).get("best.safetensors") == NANOJEV_SHA,
                "NanoJev must use the frozen hard-target seed-17 checkpoint")
    else:
        require(policy.get("engine") == "native_qwen_original_lm" and policy.get("model") == "Qwen/Qwen3-0.6B" and
                policy.get("revision") == BASE_REVISION and policy.get("project_training_steps") == 0 and
                policy.get("backend") == "untrained_qwen_lm_option_logits" and
                policy.get("checkpoint_sha256") == {"model.safetensors": BASE_SHA} and
                policy.get("original_weight_files_sha256") == {"model.safetensors": BASE_SHA},
                "Baseline must use the pinned original Qwen weights and unchanged language-model head")
    require(policy.get("controller") == "greedy" and policy.get("epsilon") == .1 and
            policy.get("sampling_seed") == 17, f"{model_id}: different action controller")
    selected_ids = manifest["selected_cases"]
    require(len(selected_ids) == len(set(selected_ids)), f"{model_id}: duplicate manifest case IDs")
    episodes = {}
    for episode in read_rows(path):
        cid = episode["case"]["id"]
        require(cid not in episodes and episode.get("complete") is True and type(episode.get("success")) is bool,
                f"{model_id}: duplicate or incomplete episode")
        require(episode.get("continuation_policy_id") == manifest["continuation_policy_id"], f"{model_id}: mixed policies")
        episodes[cid] = episode
    require(set(episodes) == set(selected_ids), f"{model_id}: source rows disagree with manifest case IDs")
    require(set(cases) <= set(episodes), f"{model_id}: missing selected display cases")
    if model_id != "jev":
        require(set(episodes) == set(cases), f"{model_id}: expected exactly the 12 selected cases")
    for cid, case in cases.items():
        match(case, episodes[cid]["case"], f"{model_id}/{cid}/case")
    require(file_digest(path) == episode_sha, f"{model_id}: input changed while loading")
    provenance = {"path": str(path), "manifest_path": str(manifest_path), "episodes_sha256": episode_sha,
                  "manifest_sha256": file_digest(manifest_path), "policy": policy,
                  "source_episode_count": len(episodes), "included_episode_count": len(cases)}
    return {cid: episodes[cid] for cid in cases}, provenance


class AtlasWriter:
    """One bounded-memory, lossless 8-by-8 atlas at a time."""
    def __init__(self, root, prefix):
        from PIL import Image
        self.Image, self.root, self.prefix = Image, Path(root), prefix
        self.root.mkdir(parents=True, exist_ok=True)
        self.count, self.atlas, self.assets = 0, None, []

    def add(self, rgb):
        require(len(rgb) == WIDTH * HEIGHT * 3, "Expected a 320x240 RGB24 image")
        page, cell = divmod(self.count, COLS * ROWS)
        if cell == 0:
            self.atlas = self.Image.new("RGB", (WIDTH * COLS, HEIGHT * ROWS), (0, 0, 0))
        x, y = (cell % COLS) * WIDTH, (cell // COLS) * HEIGHT
        self.atlas.paste(self.Image.frombytes("RGB", (WIDTH, HEIGHT), rgb), (x, y))
        sprite = {"src": f"media/{self.prefix}_{page:03d}.webp", "x": x, "y": y,
                  "width": WIDTH, "height": HEIGHT}
        self.count += 1
        if self.count % (COLS * ROWS) == 0:
            self._flush(page, COLS * ROWS)
        return sprite

    def _flush(self, page, used):
        path = self.root / f"{self.prefix}_{page:03d}.webp"
        require(not path.exists(), "Atlas destination already exists")
        self.atlas.save(path, format="WEBP", lossless=True, method=4)
        with self.Image.open(path) as decoded:
            decoded.load()
            require(decoded.mode == "RGB" and decoded.size == self.atlas.size and
                    decoded.tobytes() == self.atlas.tobytes(), "Lossless atlas decode differs from actual RGB")
        self.assets.append({"path": f"media/{path.name}", "sha256": file_digest(path), "bytes": path.stat().st_size,
                            "width": WIDTH * COLS, "height": HEIGHT * ROWS, "used_cells": used})
        self.atlas = None

    def finish(self):
        if self.atlas is not None:
            self._flush((self.count - 1) // (COLS * ROWS), self.count % (COLS * ROWS))
        return self.assets


class CaptureGame:
    """Observe exactly the single ticks already executed by UnifiedDoomEnv.step."""
    def __init__(self, game, game_variables, initial_kills, atlas):
        self.game, self.variables, self.initial_kills, self.atlas = game, game_variables, initial_kills, atlas
        self.tick, self.decision, self.action, self.probabilities = 0, 0, None, None
        self.frames, self.last_sprite, self.image_tick = [], None, None
        self.rgb_chain = hashlib.sha256()
        self.fallback_count = 0

    def __getattr__(self, name):
        return getattr(self.game, name)

    def capture(self):
        state = self.game.get_state()
        if state is not None and getattr(state, "screen_buffer", None) is not None:
            frame = state.screen_buffer
            require(tuple(frame.shape) == (HEIGHT, WIDTH, 3) and str(frame.dtype) == "uint8",
                    "Standard renderer must return 320x240 RGB uint8")
            rgb = frame.tobytes()
            self.last_sprite, self.image_tick = self.atlas.add(rgb), self.tick
            self.rgb_chain.update(self.tick.to_bytes(8, "big") + hashlib.sha256(rgb).digest())
        else:
            require(self.last_sprite is not None, "No real initial image is available")
            self.fallback_count += 1
        ammo = float(self.game.get_game_variable(self.variables.SELECTED_WEAPON_AMMO))
        kills = float(self.game.get_game_variable(self.variables.KILLCOUNT)) - self.initial_kills
        require(math.isfinite(ammo) and math.isfinite(kills), "Nonfinite per-tick game variables")
        self.frames.append({"tick": self.tick, "decision": self.decision, "action": self.action,
                            "probabilities": copy.deepcopy(self.probabilities), "ammo": ammo, "kills": kills,
                            "terminal": False, "success": kills > 0,
                            "sprite": dict(self.last_sprite), "image_tick": self.image_tick})

    def make_action(self, buttons, ticks=1):
        require(ticks == 1 and self.action in UnifiedDoomEnv._ACTIONS, "Capture requires one recorded physical tick")
        require(list(buttons) == list(UnifiedDoomEnv._ACTIONS[self.action]), "Recorded action/button mapping differs")
        reward = self.game.make_action(buttons, ticks)
        self.tick += 1
        self.capture()
        return reward


def render_episode(episode, model_id, atlas, env_factory=UnifiedDoomEnv, capture_factory=CaptureGame):
    case, env = episode["case"], None
    try:
        require(episode["complete"] is True and episode["steps"], "Need a complete, nonempty Basic episode")
        env = env_factory(copy.deepcopy(case["spec"]))
        obs, info = env.reset(case["seed"])
        capture = capture_factory(env._game, env._vzd.GameVariable, float(env._initial["KILLCOUNT"]), atlas)
        env._game = capture
        capture.capture()
        max_ticks = min(env.max_ticks, env.max_steps * env.frame_skip)
        if info["native_timeout_tick"] > 0:
            max_ticks = min(max_ticks, info["native_timeout_tick"] - info["episode_start_tick"])
        for index, recorded in enumerate(episode["steps"]):
            where = f"{model_id}/{case['id']}/step{index}"
            match(recorded["observation"], obs, where + "/observation")
            require(not info["terminated"] and not info["truncated"], where + ": action after termination")
            require(recorded["action"] in obs["candidates"], where + ": unoffered action")
            scores = recorded["scores"]
            require(set(scores) == set(obs["candidates"]) and all(type(v) in (int, float) and
                    math.isfinite(v) and 0 <= v <= 1 for v in scores.values()), where + ": invalid action probabilities")
            capture.decision, capture.action = index + 1, recorded["action"]
            # Preserve the model distribution, including provider rounding.
            # Exploration affects the recorded action, never these bars.
            capture.probabilities = dict(scores)
            before = capture.tick
            obs, reward, terminated, truncated, info = env.step(recorded["action"])
            for key, value in (("reward", reward), ("terminated", terminated), ("truncated", truncated), ("info", info)):
                match(recorded[key], value, where + "/" + key)
            require(capture.tick - before == info["actual_ticks"], where + ": missing or extra physical capture")
            require(capture.tick == info["episode_metrics"]["physical_ticks"], where + ": cumulative tick mismatch")
            match(info["episode_metrics"]["ammo"], capture.frames[-1]["ammo"], where + "/ammo")
            match(info["episode_metrics"]["kills"], capture.frames[-1]["kills"], where + "/kills")
            if terminated:
                require(index == len(episode["steps"]) - 1, where + ": premature recorded terminal")
                capture.frames[-1]["terminal"] = True
            require(not truncated, "External truncation is not a terminal showcase result")
        match(episode["final_info"], info, case["id"] + "/final_info")
        match(episode["success"], info["success"], case["id"] + "/success")
        require(info["terminated"] is True and obs["candidates"] == {} and capture.frames[-1]["terminal"],
                "Episode must end at its actual terminal transition")
        if "final_observation" in episode:
            match(episode["final_observation"], obs, case["id"] + "/final_observation")
        require(len(capture.frames) == capture.tick + 1 and capture.tick <= max_ticks, "Invalid complete physical timeline")
        match(episode["success"], capture.frames[-1]["success"], case["id"] + "/last_frame_success")
        assets = atlas.finish()
        metrics = info["episode_metrics"]
        system = {"id": model_id, "name": MODEL_TEXT[model_id][0], "success": episode["success"],
                  "total_ticks": capture.tick, "total_decisions": len(episode["steps"]),
                  "ammo_consumed": metrics["ammo_consumed"], "native_reward": metrics["native_reward"],
                  "outcome": metrics["outcome"], "frames": capture.frames,
                  "probability_semantics": "Recorded model action probabilities before epsilon exploration; not winning probabilities"}
        audit = {"case_id": case["id"], "model_id": model_id, "passed": True,
                 "physical_ticks": capture.tick, "decisions": len(episode["steps"]), "frames": len(capture.frames),
                 "fallback_image_frames": capture.fallback_count, "actual_rgb_images": atlas.count,
                 "rgb_capture_chain_sha256": capture.rgb_chain.hexdigest(), "max_available_ticks": max_ticks,
                 "final_metrics": metrics, "assets": assets}
        return system, audit, max_ticks
    finally:
        if env is not None:
            env.close()


def choose_default(cases, requested=None):
    eligible = [case for case in cases if all(next(s for s in case["systems"] if s["id"] == k)["success"]
                                             for k in ("nanojev", "jev")) and
                not next(s for s in case["systems"] if s["id"] == "base")["success"]]
    if requested is not None:
        chosen = next((c for c in cases if c["id"] == requested), None)
        require(chosen is not None, "--default-case must identify one of the 12 recorded cases")
        rule = "Explicit --default-case selection; outcomes are preserved and all registered cases remain available"
    elif eligible:
        pool = [c for c in eligible if c["split"] == "test"] or eligible
        duration = lambda c: statistics.mean(s["total_ticks"] for s in c["systems"] if s["id"] in ("nanojev", "jev"))
        median = statistics.median(duration(c) for c in pool)
        chosen = min(pool, key=lambda c: (abs(duration(c) - median), c["id"]))
        rule = "Outcome-selected illustration: Jev and NanoJev succeed while Untuned Qwen fails; prefer test, then closest to median successful-system mean duration, ties by case ID"
    else:
        alternative = [c for c in cases if next(s for s in c["systems"] if s["id"] == "nanojev")["success"] and
                       not any(s["success"] for s in c["systems"] if s["id"] in ("jev", "base"))]
        if alternative:
            chosen = min(alternative, key=lambda c: (-abs(c.get("initial_target_horizontal_offset") or 0), c["id"]))
            rule = "No Jev/NanoJev-success and baseline-failure intersection exists; select a NanoJev-only success with greatest initial visible target horizontal offset, ties by case ID"
        else:
            chosen = cases[0]
            rule = "No requested success/failure intersection exists; keep the first registered case with its real outcomes"
    return chosen["id"], {"rule": rule, "eligible_case_ids": [c["id"] for c in eligible],
                          "selected_case_id": chosen["id"], "all_registered_cases_retained": True}


def check_owned_receipt(output, receipt_path, overwrite):
    result_path = output / "shooting_results.json"
    existing_media = list((output / "media").glob("shooting_*.webp")) if (output / "media").exists() else []
    old = None
    if result_path.exists() or existing_media or receipt_path.exists():
        require(overwrite and receipt_path.is_file(), "Existing generated output needs --overwrite and its original receipt")
        old = load_json(receipt_path.read_text())
        require(old.get("schema") == RECEIPT_SCHEMA and old.get("passed") is True and
                Path(old["output_directory"]).resolve() == output.resolve(), "Receipt does not own this output directory")
        for item in old["generated_files"]:
            rel = Path(item["path"])
            require(not rel.is_absolute() and ".." not in rel.parts and
                    (rel.as_posix() == "shooting_results.json" or
                     (rel.parent.as_posix() == "media" and rel.name.startswith("shooting_") and rel.suffix == ".webp")),
                    "Receipt includes a file outside this builder's scope")
            target = output / rel
            require(target.is_file() and not target.is_symlink() and file_digest(target) == item["sha256"],
                    "Previously generated file changed or is missing; refuse to overwrite it")
        owned = {f["path"] for f in old["generated_files"]}
        require(all(p.relative_to(output).as_posix() in owned for p in existing_media), "Unowned shooting media already exists")
    return old


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jev", type=Path, default=Path("data/unified_v2/jev_complete.jsonl"))
    parser.add_argument("--nanojev", type=Path, default=Path("runs/shooting_demo_v1/nanojev.jsonl"))
    parser.add_argument("--base", type=Path, default=Path("runs/shooting_demo_v1/base.jsonl"))
    parser.add_argument("--cases", type=Path, default=Path("configs/shooting_demo_v1_cases.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("web/dev"))
    parser.add_argument("--receipt", type=Path, default=Path("runs/shooting_demo_v1/build_manifest.json"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--default-case", help="Optional explicit recorded case ID; selection is recorded in the receipt")
    args = parser.parse_args(argv)
    require(not args.output.is_symlink() and not (args.output / "media").is_symlink(), "Output directories cannot be symlinks")
    old = check_owned_receipt(args.output, args.receipt, args.overwrite)
    case_sha = file_digest(args.cases)
    case_list = read_rows(args.cases)
    registry = {c["id"]: c for c in case_list}
    require(len(registry) == len(case_list) == 12, "Exactly 12 distinct frozen display cases are required")
    require(all(c["spec"].get("task") == "shooting" and c["spec"].get("scenario") == "basic" for c in case_list), "Basic only")
    require(sum(c["split"] == "test" for c in case_list) == 6 and sum(c["split"] == "ood" for c in case_list) == 6,
            "Expected six test and six OOD cases")
    sources, provenance = {}, {}
    for model_id in ORDER:
        sources[model_id], provenance[model_id] = load_source(getattr(args, model_id), model_id, registry)
    source_files = {name: file_digest(Path(__file__).with_name(name)) for name in (
        Path(__file__).name, "unified_doom_env.py", "unified_game_pipeline.py", "replay_unified_episodes.py")}
    namespace = digest({"sources": provenance, "cases": case_sha, "implementation": source_files})[:12]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Keep a failed replay from replacing a previously validated demo.
    with tempfile.TemporaryDirectory(prefix="shooting-build-", dir=args.output.parent) as temporary:
        staging = Path(temporary)
        demos, audits, assets = [], [], []
        for case_index, case in enumerate(case_list):
            systems, budgets = [], []
            for model_id in ORDER:
                prefix = f"shooting_{namespace}_{model_id}_{digest(case['id'])[:12]}"
                writer = AtlasWriter(staging / "media", prefix)
                system, audit, budget = render_episode(sources[model_id][case["id"]], model_id, writer)
                systems.append(system); audits.append(audit); assets.extend(audit["assets"]); budgets.append(budget)
                print(json.dumps({"case": case["id"], "model": model_id, "physical_ticks": system["total_ticks"],
                                  "decisions": system["total_decisions"], "success": system["success"], "replay_passed": True}), flush=True)
            require(len(set(budgets)) == 1, "Compared systems have different physical task deadlines")
            initial_public = load_json(sources["jev"][case["id"]]["steps"][0]["observation"]["state"])
            labels = initial_public["observed_history"][-1]["visible_labels"]
            target = next((label for label in labels if label.get("name") == "Cacodemon"), None)
            offset = target["bbox"][0] + target["bbox"][2] / 2 - WIDTH / 2 if target else None
            ordinal = sum(c["split"] == case["split"] for c in case_list[:case_index + 1])
            demos.append({"id": case["id"], "split": case["split"], "seed": case["seed"],
                          "frame_skip": case["spec"].get("frame_skip", 4), "max_ticks": budgets[0],
                          "title": f"Line up the shot · {case['split'].title()} {ordinal}",
                          "initial_target_horizontal_offset": offset, "systems": systems})
        default, selection = choose_default(demos, args.default_case)
        summary = {model_id: {split: {"episodes": 6, "successes": sum(s["success"] for c in demos if c["split"] == split
                    for s in c["systems"] if s["id"] == model_id)} for split in ("test", "ood")} for model_id in ORDER}
        data = {"schema": "nanojev-shooting-demo-v1", "default_case_id": default,
                "models": [{"id": k, "name": MODEL_TEXT[k][0], "description": MODEL_TEXT[k][1]} for k in ORDER],
                "cases": demos, "summary": summary,
                "protocol": {"synchronization": "physical_tick", "frame_zero": "actual reset state",
                    "decision_index": "zero at reset; one-based recorded decision producing each subsequent tick",
                    "probabilities": "original model scores before epsilon exploration, preserved without renormalizing",
                    "controller": "greedy", "epsilon": .1, "sampling_seed": 17,
                    "image_fallback": "When native state is unavailable, hold the last real RGB image; image_tick identifies it",
                    "success": "positive observed kill-count delta before the task deadline",
                    "selection": selection, "case_file_sha256": case_sha,
                    "source_episodes_sha256": {k: v["episodes_sha256"] for k, v in provenance.items()},
                    "new_model_calls": 0, "new_api_calls": 0}}
        data_path = staging / "shooting_results.json"
        data_path.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n")
        generated = [{"path": "shooting_results.json", "sha256": file_digest(data_path), "bytes": data_path.stat().st_size}, *assets]
        for model_id, source in provenance.items():
            require(file_digest(source["path"]) == source["episodes_sha256"] and
                    file_digest(source["manifest_path"]) == source["manifest_sha256"], f"{model_id}: source changed during replay")
        require(all(file_digest(Path(__file__).with_name(n)) == h for n, h in source_files.items()), "Replay code changed during build")
        require(file_digest(args.cases) == case_sha, "Frozen display cases changed during replay")
        import PIL
        receipt = {"schema": RECEIPT_SCHEMA, "passed": True, "created_at": datetime.now(timezone.utc).isoformat(),
                   "output_directory": str(args.output.resolve()), "source_cases": str(args.cases),
                   "cases_sha256": case_sha, "sources": provenance, "implementation_sha256": source_files,
                   "runtime": {"python": platform.python_version(), "pillow": PIL.__version__},
                   "rendering": {"width": WIDTH, "height": HEIGHT, "atlas_columns": COLS, "atlas_rows": ROWS,
                       "encoding": "lossless WebP; decoded pixels checked against original RGB", "extra_simulation_ticks": 0},
                   "validation": {"episodes": len(audits), "all_passed": True,
                       "decisions": sum(a["decisions"] for a in audits), "physical_ticks": sum(a["physical_ticks"] for a in audits),
                       "float_absolute_tolerance": 1e-9, "state_text": "exact", "all_transition_info_fields": True},
                   "selection": selection, "episodes": audits, "generated_files": generated}
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "media").mkdir(exist_ok=True)
        for item in assets:
            destination = args.output / item["path"]
            require(not destination.exists() or old is not None, "Generated atlas unexpectedly already exists")
            os.replace(staging / item["path"], destination)
        os.replace(data_path, args.output / "shooting_results.json")
        if old:
            keep = {f["path"] for f in generated}
            for item in old["generated_files"]:
                if item["path"] not in keep:
                    (args.output / item["path"]).unlink()
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "output": str(args.output), "receipt": str(args.receipt),
                      "default_case_id": default, "cases": len(demos), "summary": summary}), flush=True)


if __name__ == "__main__":
    main()
