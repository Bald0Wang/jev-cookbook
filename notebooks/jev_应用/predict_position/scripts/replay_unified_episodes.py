#!/usr/bin/env python3
"""Replay recorded actions through local CPU simulators and verify trajectories.

This tool performs no model inference or API calls. JSON strings (including the
public state text), container keys, Booleans and integers must match exactly.
Finite floating-point values allow absolute error <= 1e-9, with no relative
tolerance. Every mismatch is reported; simulator errors fail their episode.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time

from unified_game_pipeline import factory, file_digest, source_hashes


FLOAT_ABSOLUTE_TOLERANCE = 1e-9


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"Nonfinite JSON number: {value}")


def load_json(text):
    return json.loads(text, object_pairs_hook=strict_object, parse_constant=reject_constant)


def evidence(value):
    """Keep large mismatched observations identifiable without duplicating them."""
    if isinstance(value, str) and len(value) > 400:
        return {"type": "string", "length": len(value), "sha256": hashlib.sha256(value.encode()).hexdigest(),
                "prefix": value[:200], "suffix": value[-100:]}
    return value


def differences(recorded, replayed, path="$", result=None):
    result = [] if result is None else result
    if type(recorded) in (int, float) and type(replayed) in (int, float):
        if type(recorded) is int and type(replayed) is int:
            equal = recorded == replayed
        elif not math.isfinite(recorded) or not math.isfinite(replayed):
            equal = False
        elif any(type(value) is int and abs(value) > 2**53 for value in (recorded, replayed)):
            # Never round a large exact integer through binary64 to compare it.
            equal = recorded == replayed
        else:
            equal = math.isclose(recorded, replayed, rel_tol=0.0, abs_tol=FLOAT_ABSOLUTE_TOLERANCE)
        if not equal:
            result.append({"path": path, "recorded": recorded, "replayed": replayed})
    elif type(recorded) is not type(replayed):
        result.append({"path": path, "reason": "type_mismatch", "recorded": evidence(recorded), "replayed": evidence(replayed)})
    elif isinstance(recorded, dict):
        for key in sorted(recorded.keys() | replayed.keys()):
            subpath = f"{path}.{key}"
            if key not in recorded or key not in replayed:
                result.append({"path": subpath, "reason": "missing_key",
                               "recorded_has_key": key in recorded, "replayed_has_key": key in replayed})
            else:
                differences(recorded[key], replayed[key], subpath, result)
    elif isinstance(recorded, list):
        if len(recorded) != len(replayed):
            result.append({"path": path + ".length", "recorded": len(recorded), "replayed": len(replayed)})
        for index, (left, right) in enumerate(zip(recorded, replayed)):
            differences(left, right, f"{path}[{index}]", result)
    elif recorded != replayed:
        result.append({"path": path, "recorded": evidence(recorded), "replayed": evidence(replayed)})
    return result


def replay_episode(episode, env_factory=factory):
    """Return an audit, continuing comparisons after mismatches when executable."""
    case = episode["case"]
    result = {"id": case["id"], "split": case["split"], "task": case["spec"]["task"],
              "seed": case["seed"], "recorded_decisions": len(episode["steps"]),
              "replayed_decisions": 0, "mismatches": [], "errors": [], "passed": False}
    env = None
    started = time.monotonic()
    try:
        if episode.get("complete") is not True or type(episode.get("success")) is not bool:
            raise ValueError("Replay requires a complete episode with Boolean success")
        env = env_factory(case["spec"])
        observation, info = env.reset(case["seed"])
        terminated, truncated = info["terminated"], info["truncated"]
        for index, recorded in enumerate(episode["steps"]):
            prefix = f"$.steps[{index}]"
            differences(recorded["observation"], observation, prefix + ".observation", result["mismatches"])
            if terminated or truncated:
                raise ValueError(f"Recorded action {index} occurs after replay termination")
            action = recorded["action"]
            if action not in observation["candidates"]:
                raise ValueError(f"Recorded action {index} is not an offered replay candidate")
            observation, reward, terminated, truncated, info = env.step(action)
            result["replayed_decisions"] += 1
            for name, value in (("reward", reward), ("terminated", terminated),
                                ("truncated", truncated), ("info", info)):
                differences(recorded[name], value, prefix + "." + name, result["mismatches"])
        differences(True, terminated, "$.replay_terminal", result["mismatches"])
        differences(False, truncated, "$.replay_truncated", result["mismatches"])
        differences({}, observation["candidates"], "$.terminal_candidates", result["mismatches"])
        differences(episode["success"], info["success"], "$.success", result["mismatches"])
        differences(episode["final_info"], info, "$.final_info", result["mismatches"])
        result["replayed_success"] = info["success"]
        result["replayed_final_metrics"] = info["episode_metrics"]
        result["terminal_observation_sha256"] = hashlib.sha256(
            json.dumps(observation, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    except Exception as exc:
        result["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    finally:
        if env is not None:
            try:
                env.close()
            except Exception as exc:
                result["errors"].append({"type": type(exc).__name__, "message": "close: " + str(exc)})
    result["elapsed_seconds"] = time.monotonic() - started
    result["mismatch_count"] = len(result["mismatches"])
    result["passed"] = not result["errors"] and not result["mismatches"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Use a fresh --output path; existing audit reports are never overwritten")
    source_hash = file_digest(args.episodes)
    manifest_path = args.episodes.with_suffix(".manifest.json")
    manifest = load_json(manifest_path.read_text()) if manifest_path.exists() else None
    report = {
        "schema": "nanojev-unified-replay-v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "episodes_file": str(args.episodes), "episodes_sha256": source_hash,
        "script_sha256": file_digest(__file__), "runtime": {
            "python": sys.version, "platform": platform.platform(), "executable": sys.executable},
        "replay_source_sha256": source_hashes(),
        "collection_manifest_sha256": file_digest(manifest_path) if manifest else None,
        "collection_declared_source_sha256": manifest.get("policy", {}).get("source_sha256") if manifest else None,
        "comparison": {"float_absolute_tolerance": FLOAT_ABSOLUTE_TOLERANCE, "float_relative_tolerance": 0,
                       "public_state_strings": "exact", "all_transition_and_final_info_fields": True,
                       "mismatches_omitted": 0, "model_inference_calls": 0, "api_calls": 0},
        "errors": [], "episodes": [], "passed": False,
    }
    started, identifiers = time.monotonic(), set()
    try:
        if manifest and (manifest.get("finished") is not True or manifest.get("episode_sha256") != source_hash):
            raise ValueError("Collection manifest is incomplete or its episode SHA256 does not match")
        with args.episodes.open() as handle:
            for lineno, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                episode = load_json(line)
                identity = episode["case"]["id"]
                if identity in identifiers:
                    raise ValueError(f"Duplicate episode ID on line {lineno}")
                identifiers.add(identity)
                result = replay_episode(episode)
                result["source_line"] = lineno
                report["episodes"].append(result)
                if len(report["episodes"]) % 16 == 0 or not result["passed"]:
                    print(json.dumps({"replayed_episodes": len(report["episodes"]), "latest_id": identity,
                                      "latest_passed": result["passed"],
                                      "elapsed_seconds": round(time.monotonic() - started, 2)}), flush=True)
        if not report["episodes"]:
            raise ValueError("No episodes were supplied")
        if manifest and "selected_cases" in manifest and set(manifest["selected_cases"]) != identifiers:
            raise ValueError("Replayed case IDs disagree with the collection manifest")
        if file_digest(args.episodes) != source_hash:
            raise ValueError("Source episodes changed during replay")
        if source_hashes() != report["replay_source_sha256"]:
            raise ValueError("Replay implementation files changed during verification")
    except Exception as exc:
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["summary"] = {
        "episodes": len(report["episodes"]), "passed_episodes": sum(r["passed"] for r in report["episodes"]),
        "failed_episodes": sum(not r["passed"] for r in report["episodes"]),
        "replayed_decisions": sum(r["replayed_decisions"] for r in report["episodes"]),
        "mismatches": sum(r["mismatch_count"] for r in report["episodes"]),
        "episodes_by_task": dict(Counter(r["task"] for r in report["episodes"])),
        "elapsed_seconds": time.monotonic() - started,
    }
    report["passed"] = not report["errors"] and all(r["passed"] for r in report["episodes"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"passed": report["passed"], **report["summary"], "report": str(args.output)}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
