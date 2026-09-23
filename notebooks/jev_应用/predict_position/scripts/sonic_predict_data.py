#!/usr/bin/env python3
"""Collect a frozen visual PP expert alongside unchanged student observations.

Separate games share seed, scenario, actions, reward and terminal rules. Only
the expert uses the old game materials and 160x120 rendering. Every physical
tick must agree, followed by an independent standard-only episode replay.
All executed states are retained; target filtering belongs to preparation.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import copy
import json
import math
import multiprocessing
import os
from pathlib import Path
import random
import re
import time

from appo_basic_data import (
    TickMirror, expert_argmax, rendering_snapshot, replay_standard, require_equal,
    sample_with_receipt, write_json,
)
from unified_doom_env import UnifiedDoomEnv
from unified_game_pipeline import (
    SPLITS, behavior_distribution, digest, encode, environment_group,
    file_digest, policy_request, read_rows,
)

ACTIONS = ("noop", "left", "right", "shoot")
OLD_WAD_SHA = "729f100448d0b48e12ecc8004e096a9ea6df024467d962f002bb286805be3a8e"
NEW_WAD_SHA = "a8772e088847032510d97ba2312406a6998f21cbab44d4ff10696faa9c0ecd4b"
SCENARIO_WAD_SHA = "a5a1bdbbfdbef2a505b496f6889d06751ba3431a50ec382fb303fcc4066917a6"
SOURCES = ("sonic_predict_data.py", "sonic_predict_policy.py", "appo_basic_data.py",
           "evaluate_appo_doom.py", "unified_doom_env.py", "unified_game_pipeline.py")


def observed_ammo(obs):
    state = json.loads(obs["state"])
    if state["scenario"] != "predict_position" or state["screen_size"] != [320, 240]:
        raise ValueError("Expected the unchanged standard PP observation")
    if not 1 <= len(state["observed_history"]) <= 4:
        raise ValueError("Invalid short visible history")
    ammo = state["observed_history"][-1]["ammo"]
    if not isinstance(ammo, (int, float)) or not math.isfinite(ammo):
        raise ValueError("Missing finite pre-action visible ammunition")
    return ammo


def probability_check(result):
    raw, logits, probs = (result[k] for k in ("raw_probabilities", "logits", "probabilities"))
    if any(set(x) != set(ACTIONS) for x in (raw, logits, probs)):
        raise ValueError("Expert must expose its original four actions")
    if any(not math.isfinite(v) for x in (raw, logits, probs) for v in x.values()):
        raise ValueError("Nonfinite expert output")
    total = math.fsum(raw.values())
    if min(raw.values()) < 0 or total <= 0 or total != result["raw_probability_sum"]:
        raise ValueError("Invalid raw probability mass")
    if any(probs[k] != raw[k] / total for k in ACTIONS):
        raise ValueError("Normalized expert distribution differs from raw output")
    maximum = max(logits.values())
    exp = {k: math.exp(logits[k] - maximum) for k in ACTIONS}
    denominator = math.fsum(exp.values())
    if any(abs(raw[k] - exp[k] / denominator) > 2e-6 for k in ACTIONS):
        raise ValueError("Expert probabilities disagree with its logits")
    return probs


class MirroredPredictEnvironment:
    """No policy access to either game's hidden geometry or physical audit data."""
    def __init__(self, spec, old_game_wad):
        if spec.get("task") != "shooting" or spec.get("scenario") != "predict_position":
            raise ValueError("Only Predict Position is supported")
        if file_digest(old_game_wad) != OLD_WAD_SHA:
            raise ValueError("Expert game materials differ from the frozen SHA256")
        self.standard = UnifiedDoomEnv(copy.deepcopy(spec))
        self.expert = None
        self.mirror = None
        try:
            self.standard._initialize()
            vzd = self.standard._vzd
            if str(vzd.__version__) != "1.3.0":
                raise ValueError("This collection pins the verified ViZDoom 1.3.0 runtime")
            package = Path(vzd.__file__).parent
            scenarios = Path(getattr(vzd, "scenarios_path", package / "scenarios"))
            config_path = scenarios / "predict_position.cfg"
            wad_path = scenarios / "predict_position.wad"
            new_game_wad = package / "freedoom2.wad"
            if file_digest(new_game_wad) != NEW_WAD_SHA or file_digest(wad_path) != SCENARIO_WAD_SHA:
                raise ValueError("Standard game or scenario materials changed")
            config = config_path.read_text()
            self.standard_render = {}
            for field in ("hud", "decals", "particles", "weapon", "crosshair"):
                match = re.search(r"^\s*render_" + field + r"\s*=\s*(true|false)\b", config, re.M | re.I)
                if match:
                    self.standard_render[field] = match.group(1).lower() == "true"
            if self.standard_render.get("hud") is not False:
                raise ValueError("Standard student HUD-off contract changed")
            # Confirm the actual configured base-material path when supported.
            game = self.standard._game
            getter = getattr(game, "get_doom_game_path", None)
            actual_path = getter() if getter else None
            if actual_path:
                actual = Path(actual_path)
                if not actual.is_file():
                    actual = package / actual.name
                if file_digest(actual) != NEW_WAD_SHA:
                    raise ValueError("Standard game did not load the expected default materials")
            self.assets = {
                "standard_game_wad_sha256": NEW_WAD_SHA,
                "expert_game_wad_sha256": OLD_WAD_SHA,
                "scenario_wad_sha256": file_digest(wad_path),
                "scenario_config_sha256": file_digest(config_path),
                "standard_game_path_verification": "runtime_getter" if actual_path else "installed_package_default",
                "shared_scenario_config": True, "shared_reward_settings": True,
                "expert_game_path_setting": "explicit set_doom_game_path before init",
            }
            self.expert = UnifiedDoomEnv(copy.deepcopy(spec))
            self.expert._initialize()
            native = self.expert._game
            native.close()
            native.set_doom_game_path(str(Path(old_game_wad).resolve()))
            native.set_screen_resolution(vzd.ScreenResolution.RES_160X120)
            self.expert_render = {"hud": False, "decals": False, "particles": False,
                                  "weapon": True, "crosshair": False}
            for field, value in self.expert_render.items():
                getattr(native, "set_render_" + field)(value)
            native.init()
        except BaseException:
            self.close()
            raise

    def reset(self, seed):
        if self.mirror is not None:
            raise RuntimeError("A fresh mirrored pair is required for every episode")
        obs, info = self.standard.reset(seed)
        self.expert.reset(seed)  # Its inherited text is discarded, never exported.
        require_equal(self.standard._metadata, self.expert._metadata, "shared standard adapter")
        self.mirror = TickMirror(self.standard._game, self.expert._game, self.standard._vzd)
        initial = self.mirror.check("reset")
        self.standard._game = self.mirror
        rendering = {
            "standard": {"width": self.mirror.standard.get_screen_width(),
                         "height": self.mirror.standard.get_screen_height(),
                         "hud": False, "loaded_config_flags": self.standard_render,
                         "undeclared_flags": "Unmodified ViZDoom engine defaults; no getter claim",
                         "verification": {"width": "runtime_getter", "height": "runtime_getter",
                                          "hud": "loaded_config_declaration"}},
            "expert": rendering_snapshot(self.mirror.expert, self.expert_render),
        }
        if (rendering["standard"]["width"], rendering["standard"]["height"],
                rendering["expert"]["width"], rendering["expert"]["height"]) != (320, 240, 160, 120):
            raise RuntimeError("Unexpected native rendering resolution")
        return obs, info, {"initial_physics": initial, "rendering": rendering,
                           "assets": self.assets,
                           "shared_environment_metadata": copy.deepcopy(self.standard._metadata)}

    def expert_frame(self):
        self.mirror.check("before inference")
        state = self.expert._game.get_state()
        if state is None or state.screen_buffer is None:
            raise RuntimeError("Missing live expert RGB frame")
        return state.screen_buffer.copy()

    def step(self, action):
        self.mirror.checks = []
        result = self.standard.step(action)
        checks = copy.deepcopy(self.mirror.checks)
        if len(checks) != result[-1]["actual_ticks"]:
            raise RuntimeError("Missing per-tick mirrored transition checks")
        return (*result, checks)

    def close(self):
        try:
            self.standard.close()
        finally:
            if self.expert is not None:
                self.expert.close()


def collect_episode(case, policy, policy_id, old_game_wad, seed=17,
                    env_factory=MirroredPredictEnvironment):
    env = env_factory(case["spec"], old_game_wad)
    rng = random.Random(int(digest([case["id"], seed])[:16], 16))
    episode = {"case": copy.deepcopy(case), "continuation_policy_id": policy_id,
               "steps": [], "complete": False, "success": None}
    before_forward, before_reset = policy.forward_count, policy.reset_count
    try:
        obs, info, initial = env.reset(case["seed"])
        episode.update(mirror_initial=initial, initial_observation=copy.deepcopy(obs))
        policy.reset()
        while not info["terminated"]:
            if set(obs["candidates"]) != set(ACTIONS):
                raise RuntimeError("The standard environment must offer four actions")
            ammo = observed_ammo(obs)
            result = policy.predict(env.expert_frame())
            probs = probability_check(result)
            behavior = behavior_distribution(probs, "greedy", 0.0)
            action, draw = sample_with_receipt(behavior, rng)
            following, reward, done, truncated, next_info, checks = env.step(action)
            pixel = {key: result[key] for key in (
                "pixel_sha256", "resized_chw_sha256", "normalized_input_sha256",
                "rnn_before_sha256", "rnn_after_sha256")}
            pixel.update(native_frame_shape_hwc=[120, 160, 3], student_text_fed_to_expert=False)
            episode["steps"].append({
                "observation": copy.deepcopy(obs), "request": policy_request(obs, case["id"]),
                "pre_action_ammo": ammo, "action": action, "expert_argmax": expert_argmax(probs),
                "scores": probs, "policy_probs": probs, "policy_probs_raw": result["raw_probabilities"],
                "raw_probability_sum": result["raw_probability_sum"],
                "normalization_applied": result["raw_probability_sum"] != 1.0,
                "expert": {"probs": probs, "argmax": expert_argmax(probs), "raw_logits": result["logits"]},
                "behavior_probs": behavior, "sampling_draw": draw, "pixel_input": pixel,
                "forced": False, "answers": {"action": {"type": "choice", "probabilities": probs,
                    "probability_semantics": "expert categorical action policy"}},
                "decision_source": "sonic_visual_policy_on_old_materials_tick_mirrored_to_standard",
                "reward": reward, "terminated": done, "truncated": truncated,
                "info": copy.deepcopy(next_info), "mirror_tick_checks": checks,
                "next_observation_sha256": digest(following),
            })
            obs, info = following, next_info
        episode.update(complete=True, success=info["success"], final_info=copy.deepcopy(info),
                       final_observation=copy.deepcopy(obs),
                       mirrored_physical_ticks=sum(len(s["mirror_tick_checks"]) for s in episode["steps"]),
                       inference_counts={"actual_expert_forward_calls": policy.forward_count-before_forward,
                                         "actual_recurrent_resets": policy.reset_count-before_reset})
        validate_episode(episode, seed)
        return episode
    finally:
        env.close()


def validate_episode(episode, seed=17):
    case, steps = episode["case"], episode["steps"]
    if not episode["complete"] or type(episode["success"]) is not bool or not steps:
        raise ValueError("Only complete nonempty episodes are valid")
    final = episode["final_info"]
    if not final["terminated"] or final["truncated"] or final["success"] != episode["success"]:
        raise ValueError("Invalid terminal outcome")
    if episode["final_observation"]["candidates"]:
        raise ValueError("Terminal actions must be empty")
    if episode["success"] != (final["episode_metrics"]["kills"] > 0):
        raise ValueError("Success must reflect observed kill count")
    rng = random.Random(int(digest([case["id"], seed])[:16], 16))
    previous, ticks = episode["mirror_initial"]["initial_physics"], 0
    for i, step in enumerate(steps):
        obs = step["observation"]
        if step["pre_action_ammo"] != observed_ammo(obs) or step["request"] != policy_request(obs, case["id"]):
            raise ValueError("Public request or pre-action ammunition changed")
        if i == 0 and obs != episode["initial_observation"]:
            raise ValueError("Initial observation changed")
        if set(obs["candidates"]) != set(ACTIONS):
            raise ValueError("Incorrect action candidates")
        probs = probability_check({"probabilities": step["policy_probs"],
            "raw_probabilities": step["policy_probs_raw"], "logits": step["expert"]["raw_logits"],
            "raw_probability_sum": step["raw_probability_sum"]})
        if step["expert"] != {"probs": probs, "argmax": expert_argmax(probs), "raw_logits": step["expert"]["raw_logits"]}:
            raise ValueError("Expert receipt changed")
        if step["expert_argmax"] != expert_argmax(probs):
            raise ValueError("Expert target differs from logits")
        behavior = behavior_distribution(probs, "greedy", 0.0)
        action, draw = sample_with_receipt(behavior, rng)
        if (step["action"], step["sampling_draw"], step["behavior_probs"]) != (action, draw, behavior):
            raise ValueError("Actual action differs from frozen behavior")
        checks = step["mirror_tick_checks"]
        if not 1 <= len(checks) <= case["spec"]["frame_skip"] or len(checks) != step["info"]["actual_ticks"]:
            raise ValueError("Incorrect action duration")
        for check in checks:
            ticks += 1
            if check["tick_index"] != ticks or check["before_sha256"] != digest(previous):
                raise ValueError("Broken physical audit chain")
            previous = check["after"]
        if not math.isclose(math.fsum(c["reward"] for c in checks), step["reward"], abs_tol=1e-10):
            raise ValueError("Inconsistent per-tick reward")
        following = steps[i+1]["observation"] if i+1 < len(steps) else episode["final_observation"]
        if digest(following) != step["next_observation_sha256"] or step["truncated"] or step["terminated"] != (i == len(steps)-1):
            raise ValueError("Incomplete or broken observed trajectory")
        if i and step["pixel_input"]["rnn_before_sha256"] != steps[i-1]["pixel_input"]["rnn_after_sha256"]:
            raise ValueError("Broken recurrent-state chain")
    if ticks != episode["mirrored_physical_ticks"] or ticks != final["episode_metrics"]["physical_ticks"]:
        raise ValueError("Physical tick totals disagree")
    if episode["inference_counts"] != {"actual_expert_forward_calls": len(steps), "actual_recurrent_resets": 1}:
        raise ValueError("Real inference counters disagree")


def validate_cases(cases, config, case_sha256):
    if config["case_sha256"] != case_sha256:
        raise ValueError("Case file differs from the frozen protocol")
    if dict(Counter(c["split"] for c in cases)) != config["case_counts"]:
        raise ValueError("Incomplete registered split counts")
    if len({c["id"] for c in cases}) != len(cases) or len({environment_group(c) for c in cases}) != len(cases):
        raise ValueError("Duplicate latent group or case identity")
    for case in cases:
        skip = 8 if case["split"] == "ood" else 4
        expected = {"task": "shooting", "scenario": "predict_position", "history_length": 4,
                    "frame_skip": skip, "max_steps": 38 if skip == 8 else 75}
        if case["spec"] != expected:
            raise ValueError("Case differs from registered decision-cadence protocol")


def load_policy(checkpoint, expert_config, protocol, device):
    from sonic_predict_policy import SonicVisionPolicy, CHECKPOINT_SHA256, SOURCE_COMMIT
    primary = protocol["primary"]
    expected = {"checkpoint_repository": "thainv0212/sonic_doom", "checkpoint_revision": SOURCE_COMMIT,
                "checkpoint_sha256": CHECKPOINT_SHA256, "controller": "greedy", "epsilon": 0.0}
    if any(primary.get(k) != v for k, v in expected.items()):
        raise ValueError("Protocol differs from the frozen visual expert")
    if file_digest(expert_config) != primary["config_sha256"]:
        raise ValueError("Expert config differs from its frozen SHA256")
    actor = SonicVisionPolicy(checkpoint, expert_config, device)
    identity = copy.deepcopy(actor.identity)
    identity.update(model=primary["checkpoint_repository"], revision=SOURCE_COMMIT,
                    cfg_sha256=identity["config_sha256"])
    return actor, identity


_WORKER = None


def worker_init(checkpoint, expert_config, protocol, old_wad, identity, policy_id, sources, device):
    global _WORKER
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[name] = "1"
    for name, sha in sources.items():
        if file_digest(Path(__file__).with_name(name)) != sha:
            raise RuntimeError("Worker implementation changed")
    actor, observed_identity = load_policy(checkpoint, expert_config, protocol, device)
    if observed_identity != identity:
        raise RuntimeError("Worker expert identity differs from the parent")
    _WORKER = (actor, old_wad, policy_id, protocol["primary"]["sampling_seed"], digest(identity))


def collect_worker(case):
    actor, old_wad, policy_id, seed, identity_hash = _WORKER
    episode = collect_episode(case, actor, policy_id, old_wad, seed)
    episode["standard_independent_replay"] = replay_standard(episode)
    episode["worker_execution"] = {"pid": os.getpid(), "expert_identity_sha256": identity_hash}
    return episode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cases", "config", "checkpoint", "expert-config", "old-game-wad", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--splits", default=",".join(SPLITS))
    parser.add_argument("--limit", type=int, default=0, help="First selected cases for an explicit smoke test; zero retains all")
    args = parser.parse_args()
    if args.workers < 1 or args.limit < 0 or (args.workers > 1 and args.device != "cpu"):
        parser.error("Use positive workers, nonnegative limit, and CPU for multiple workers")
    if args.output.exists():
        parser.error("Use a fresh output directory; existing raw records are never overwritten")
    protocol = json.loads(args.config.read_text())
    all_cases = read_rows(args.cases)
    validate_cases(all_cases, protocol, file_digest(args.cases))
    splits = args.splits.split(",")
    if not splits or len(set(splits)) != len(splits) or set(splits) - set(SPLITS):
        parser.error("Invalid requested splits")
    cases = [c for c in all_cases if c["split"] in splits]
    before_limit = len(cases)
    cases = cases[:args.limit] if args.limit else cases
    if file_digest(args.old_game_wad) != OLD_WAD_SHA:
        raise ValueError("Expert game material SHA256 mismatch")
    actor, identity = load_policy(args.checkpoint, args.expert_config, protocol, args.device)
    del actor  # Parent identity loading does not perform inference.
    sources = {name: file_digest(Path(__file__).with_name(name)) for name in SOURCES}
    policy = {"engine": "sonic_doom_pure_vision_pp", "render_adapter": "old_materials_tick_mirror",
              "controller": "greedy", "epsilon": 0.0, "temperature": 1.0,
              "sampling_seed": protocol["primary"]["sampling_seed"], "tie_break": "lexicographic_first",
              "model": identity, "checkpoint_sha256": {"model": identity["checkpoint_sha256"], "cfg": identity["config_sha256"]},
              "source_sha256": sources, "environment_contract": "finite_task_deadline_v1",
              "observation": protocol["student_observation"], "assets": protocol["assets"]}
    policy_id = digest(policy)
    args.output.mkdir(parents=True)
    path = args.output / "episodes.jsonl"
    manifest_path = args.output / "episodes.manifest.json"
    manifest = {"schema_version": "nanojev-unified-episodes-v1", "collector_schema": "nanojev-sonic-pp-mirrored-v1",
        "finished": False, "cases_sha256": file_digest(args.cases), "config_sha256": file_digest(args.config),
        "selected_cases_sha256": digest(cases), "selected_cases": [c["id"] for c in cases],
        "selected_episodes": len(cases), "selected_before_limit": before_limit, "limit": args.limit,
        "policy": policy, "continuation_policy_id": policy_id, "retention": protocol["retention"],
        "standard_independent_replay": True, "api_calls": 0, "model_downloads": 0,
        "parallel_execution": {"workers_requested": args.workers, "start_method": "spawn",
            "result_order": "registered case order", "independent_actors": True, "parent_forward_calls": 0}}
    write_json(manifest_path, manifest)
    arguments = (str(args.checkpoint.resolve()), str(args.expert_config.resolve()), protocol,
                 str(args.old_game_wad.resolve()), identity, policy_id, sources, args.device)
    pool = None
    counts, episodes, successes = Counter(), Counter(), Counter()
    completed, ticks = 0, 0
    started = time.monotonic()
    try:
        if args.workers == 1:
            worker_init(*arguments)
            results = map(collect_worker, cases)
        else:
            pool = ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("spawn"),
                                       initializer=worker_init, initargs=arguments)
            results = pool.map(collect_worker, cases, chunksize=1)
        with path.open("x") as output:
            for case, episode in zip(cases, results):
                if episode["case"] != case or episode["continuation_policy_id"] != policy_id:
                    raise ValueError("Worker changed case order or policy identity")
                validate_episode(episode, policy["sampling_seed"])
                if episode["standard_independent_replay"].get("passed") is not True:
                    raise ValueError("Missing successful independent replay")
                output.write(encode(episode) + "\n")
                output.flush()
                counts[case["split"]] += len(episode["steps"])
                episodes[case["split"]] += 1
                successes[case["split"]] += episode["success"]
                completed += 1
                ticks += episode["mirrored_physical_ticks"]
                print(encode({"case": case["id"], "success": episode["success"], "decisions": len(episode["steps"]),
                              "physical_ticks": episode["mirrored_physical_ticks"], "mirror_and_replay": True}), flush=True)
        if completed != len(cases):
            raise RuntimeError("Collection ended before all registered cases completed")
        manifest.update(finished=True, episode_sha256=file_digest(path), episodes=completed,
            decisions=sum(counts.values()), split_episodes=dict(episodes), split_records=dict(counts),
            split_successes=dict(successes), mirrored_physical_ticks=ticks,
            actual_expert_forward_calls=sum(counts.values()), actual_recurrent_resets=completed,
            elapsed_seconds=time.monotonic()-started)
    except BaseException as exc:
        manifest.update(finished=False, completed_episodes=completed, error_type=type(exc).__name__)
        raise
    finally:
        write_json(manifest_path, manifest)
        if pool:
            pool.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    main()
