#!/usr/bin/env python3
"""Keep selected recorded NanoJev wins, preserving complete benchmark scores.

This operation verifies and backs up the original media receipt before replacing
its index. Kept case objects and frame pixels remain unchanged. Only unused,
receipt-owned Predict Position atlases are removed from the development folder.
There is no simulator, model inference, training or API request in this tool.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

from build_predict_position_demo import NANOJEV_SHA, ORDER, OUTPUT_NAME
from build_shooting_demo import require
from replay_unified_episodes import load_json
from unified_game_pipeline import digest, file_digest


def select_wins(data, config):
    require(data.get("schema") == "nanojev-shooting-demo-v1" and data.get("task") == "predict_position",
            "Expected a completed Predict Position recording")
    require(data.get("protocol", {}).get("selected_checkpoint_sha256") == NANOJEV_SHA,
            "The recording must use the current unified step-400 checkpoint")
    original = {case["id"]: case for case in data["cases"]}
    require(len(original) == len(data["cases"]), "Duplicate source cases")
    rows = config["cases"]
    selected_ids = [row["id"] for row in rows]
    require(rows and len(set(selected_ids)) == len(rows) and config["default_case_id"] in selected_ids,
            "Selection needs unique cases and an included default")
    for row in rows:
        require(row["id"] in original, "Selected case is absent from the source recording")
        case = original[row["id"]]
        require(case["split"] == "test" and len(case["systems"]) == 3 and
                {s["id"]: s["success"] for s in case["systems"]} == {"jev": False, "nanojev": True, "base": False},
                "Every retained illustration must be a recorded NanoJev-only test success")
        require(row["expected_success"] == {"jev": False, "nanojev": True, "base": False}, "Incorrect configured outcome")
        require(case["title"] == row["title"] and case["description"] == row["description"],
                "Filtering cannot rewrite a retained case")
    for model_id in ORDER:
        for split in ("test", "ood"):
            row = data["summary"][model_id][split]
            require(row["episodes"] == 128 and type(row["successes"]) is int and 0 <= row["successes"] <= 128,
                    "The full 128-case benchmark must accompany selected illustrations")
    result = copy.deepcopy(data)
    result["default_case_id"] = config["default_case_id"]
    result["cases"] = [copy.deepcopy(original[cid]) for cid in selected_ids]
    result["illustration_summary"] = {k: {"test": {"episodes": len(rows), "successes": len(rows) if k == "nanojev" else 0}}
                                      for k in ORDER}
    result["protocol"]["selection"].update({"rule": config["selection_rule"],
        "selected_case_id": config["default_case_id"], "selected_case_ids": selected_ids,
        "outcome_selected": True, "selection_changes_training_or_evaluation": False})
    require(result["summary"] == data["summary"], "Full-cohort metrics changed")
    for case in result["cases"]:
        require(case == original[case["id"]], "A retained case or frame changed")
    return result


def owned_path(root, item):
    rel = Path(item["path"])
    require(not rel.is_absolute() and ".." not in rel.parts and
            (rel.as_posix() == OUTPUT_NAME or
             (rel.parent.as_posix() == "media" and rel.name.startswith("predict_position_") and rel.suffix == ".webp")),
            "Receipt includes a path outside Predict Position media")
    path = root / rel
    require(path.is_file() and not path.is_symlink() and file_digest(path) == item["sha256"] and
            path.stat().st_size == item["bytes"], "Receipt-owned file is missing or modified: " + str(rel))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("web/dev"))
    parser.add_argument("--source-receipt", type=Path, default=Path("results/predict_position_demo_v1/build_manifest.json"))
    parser.add_argument("--selection", type=Path, default=Path("configs/predict_position_demo_v1.json"))
    parser.add_argument("--backup", type=Path, default=Path("runs/predict_position_wins_v2/original_demo"))
    parser.add_argument("--receipt", type=Path, default=Path("results/predict_position_wins_v2/filter_manifest.json"))
    args = parser.parse_args(argv)
    require(not args.site.is_symlink() and not (args.site / "media").is_symlink(), "Site cannot use symlinked directories")
    require(not args.backup.exists() and not args.receipt.exists(), "Use a fresh backup and filter receipt")
    source_receipt_sha = file_digest(args.source_receipt)
    old_receipt = load_json(args.source_receipt.read_text())
    require(old_receipt.get("schema") == "nanojev-predict-position-media-receipt-v1" and old_receipt.get("passed") is True,
            "Expected the successful original replay/render receipt")
    generated = old_receipt["generated_files"]
    paths = {item["path"] for item in generated}
    require(len(paths) == len(generated) and OUTPUT_NAME in paths, "Invalid original generated-file inventory")
    for item in generated:
        owned_path(args.site, item)
    original_index = args.site / OUTPUT_NAME
    old_index_sha = file_digest(original_index)
    data = load_json(original_index.read_text())
    selection_sha = file_digest(args.selection)
    config = load_json(args.selection.read_text())
    filtered = select_wins(data, config)
    keep_media = {frame["sprite"]["src"] for case in filtered["cases"] for system in case["systems"] for frame in system["frames"]}
    require(keep_media <= paths - {OUTPUT_NAME}, "Selected frame references unowned media")
    removed = [item for item in generated if item["path"] != OUTPUT_NAME and item["path"] not in keep_media]
    preserved = [item for item in generated if item["path"] in keep_media]
    # Back up all original files, not only the removed cases, so the complete
    # previous five-case demo and its receipt remain reproducible locally.
    args.backup.mkdir(parents=True)
    for item in generated:
        src = owned_path(args.site, item)
        dst = args.backup / item["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        require(file_digest(dst) == item["sha256"], "Backup SHA mismatch")
    shutil.copyfile(args.source_receipt, args.backup / "original_build_manifest.json")
    require(file_digest(args.backup / "original_build_manifest.json") == source_receipt_sha, "Receipt backup changed")
    encoded = (json.dumps(filtered, separators=(",", ":"), allow_nan=False) + "\n").encode()
    new_index_sha = hashlib.sha256(encoded).hexdigest()
    original_cases = {case["id"]: case for case in data["cases"]}
    case_audits = []
    for case in filtered["cases"]:
        previous = original_cases[case["id"]]
        case_audits.append({"case_id": case["id"], "unchanged": True,
            "source_case_sha256": digest(previous), "retained_case_sha256": digest(case),
            "systems": [{"model_id": system["id"], "frames": len(system["frames"]),
                         "frames_sha256": digest(system["frames"]), "all_frames_unchanged":
                         system["frames"] == next(s for s in previous["systems"] if s["id"] == system["id"])["frames"]}
                        for system in case["systems"]]})
    index_row = {"path": OUTPUT_NAME, "sha256": new_index_sha, "bytes": len(encoded)}
    receipt = {"schema": "nanojev-predict-position-filter-v2", "passed": True,
        "created_at": datetime.now(timezone.utc).isoformat(), "script_sha256": file_digest(__file__),
        "source_receipt": str(args.source_receipt), "source_receipt_sha256": source_receipt_sha,
        "source_index_sha256": old_index_sha, "new_index_sha256": new_index_sha,
        "selection_config": str(args.selection), "selection_config_sha256": selection_sha,
        "original_backup": str(args.backup), "original_cases": len(data["cases"]), "retained_cases": len(filtered["cases"]),
        "retained_case_ids": [case["id"] for case in filtered["cases"]],
        "removed_case_ids": [case["id"] for case in data["cases"] if case["id"] not in {c["id"] for c in filtered["cases"]}],
        "case_validation": case_audits, "full_cohort_summary_unchanged": True,
        "full_cohort_summary_sha256": digest(data["summary"]), "full_cohort_summary": data["summary"],
        "illustration_summary": filtered["illustration_summary"], "generated_files": [index_row, *preserved],
        "removed_media_after_verified_backup": removed, "source_media_sha256_verified": True,
        "retained_media_sha256_unchanged": True, "new_api_calls": 0, "new_model_calls": 0,
        "new_simulation_ticks": 0}
    require(file_digest(args.source_receipt) == source_receipt_sha and file_digest(args.selection) == selection_sha,
            "Input receipt or selection changed while filtering")
    for item in generated:
        owned_path(args.site, item)
    pending = args.site / (OUTPUT_NAME + ".filtered")
    require(not pending.exists(), "Index staging path already exists")
    with pending.open("xb") as handle:
        handle.write(encoded)
    os.replace(pending, original_index)
    for item in removed:
        path = owned_path(args.site, item)
        require(file_digest(args.backup / item["path"]) == item["sha256"], "Removal backup changed")
        path.unlink()
    for item in receipt["generated_files"]:
        owned_path(args.site, item)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as handle:
        json.dump(receipt, handle, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps({"passed": True, "cases": len(filtered["cases"]), "retained_media": len(preserved),
        "removed_media": len(removed), "bytes": sum(item["bytes"] for item in receipt["generated_files"]),
        "receipt": str(args.receipt), "default_case_id": filtered["default_case_id"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
