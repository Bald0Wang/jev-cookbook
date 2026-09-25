#!/usr/bin/env python3
"""Run fixed Jev game cases in ordered shards with a shared budget ceiling.

The existing pipeline and HTTP worker are unchanged. Each child has four HTTP
slots, 16 environments, greedy epsilon .1 and seed 17. Journals retain separate
namespaces: an API receipt is identified by (shard, call ID). Existing journals
can be reused with a fresh --output and the same --journal-root/case file.
Only --max-active shards run concurrently; a failed shard retries in a fresh
attempt directory after 30 seconds without stopping other running shards.
"""
import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import signal
import subprocess
import sys
import time

from unified_game_pipeline import (
    behavior_distribution, choose, digest, encode, file_digest, policy_request,
    read_rows, source_hashes, summarize, validate_cases,
)

NANO = Decimal("0.000000001")


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


def money(value):
    if isinstance(value, bool):
        raise ValueError("Boolean cost is invalid")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("Cost must be finite and nonnegative")
    return result


def audit_journal(path):
    """Mirror worker accounting, including interrupted starts and unknown failures."""
    path = Path(path)
    raw = path.read_bytes() if path.exists() else b""
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    starts, successes, finished, failed_unknown = {}, {}, set(), set()
    unresolved = set()
    for row in rows:
        identity, status = row["id"], row["status"]
        if not isinstance(identity, str):
            raise ValueError("Invalid journal call ID")
        if status == "started":
            if identity in starts or identity in finished:
                raise ValueError("Duplicate or restarted journal call ID")
            money(row.get("reservation_usd", .002))
            starts[identity] = row
            unresolved.add(identity)
        elif status in ("succeeded", "failed"):
            if identity in finished:
                raise ValueError("Duplicate terminal journal receipt")
            finished.add(identity)
            unresolved.discard(identity)
            if status == "succeeded":
                money(row["cost_usd"])
                successes[identity] = row
            elif row.get("unknown_cost") is True:
                failed_unknown.add(identity)
        else:
            raise ValueError("Unknown journal status")
    unknown = unresolved | failed_unknown
    spent = sum((money(r["cost_usd"]) for r in successes.values()), Decimal(0))
    reserved = sum((money(starts.get(key, {}).get("reservation_usd", .002))
                    for key in unknown), Decimal(0))
    report = {"journal_sha256": hashlib.sha256(raw).hexdigest(), "journal_bytes": len(raw),
        "rows": len(rows), "started_calls": len(starts), "succeeded_calls": len(successes),
        "failed_calls": sum(r["status"] == "failed" for r in rows),
        "reported_cost_usd": str(spent), "unknown_reserved_usd": str(reserved),
        "accounted_usd": str(spent + reserved), "unresolved_started_ids": sorted(unresolved),
        "unknown_cost_ids": sorted(unknown),
        "zero_reported_cost_calls": sum(money(r["cost_usd"]) == 0 for r in successes.values())}
    return report, successes


def allocate_budgets(total, accounts):
    """Ceil old reservations and floor the total in integer nano-dollars."""
    total = money(total)
    if total <= 0 or total > 3:
        raise ValueError("This runner permits a total budget above zero and at most USD 3")
    units = int((total / NANO).to_integral_value(rounding=ROUND_FLOOR))
    used = [int((money(x) / NANO).to_integral_value(rounding=ROUND_CEILING)) for x in accounts]
    remaining = units - sum(used)
    if not used or remaining < len(used) * 2_000_000:
        raise ValueError("Insufficient budget after previous costs and unknown reservations")
    each, extra = divmod(remaining, len(used))
    budgets = [str(Decimal(v + each + int(i < extra)) * NANO) for i, v in enumerate(used)]
    assert sum(map(Decimal, budgets)) <= total
    return budgets


def ordered_shards(cases, workers):
    if workers < 1 or not cases:
        raise ValueError("Use a nonempty cohort and positive worker count")
    width = (len(cases) + workers - 1) // workers
    return [cases[i:i+width] for i in range(0, len(cases), width)]


def prepare_journals(root, prior, case_sha, shards):
    """Copy a stable old journal only to shard zero, or reuse all existing shards."""
    root = Path(root)
    declaration = {"schema": "nanojev-parallel-journals-v1", "cases_sha256": case_sha,
                   "shard_cases": [[c["id"] for c in group] for group in shards]}
    marker = root / "parallel_journals.json"
    if root.exists():
        if prior:
            raise ValueError("For journal reuse omit --prior-journal-dir; prior bytes are already present")
        saved = json.loads(marker.read_text())
        if any(saved.get(k) != v for k, v in declaration.items()):
            raise ValueError("Existing journal root belongs to different cases or shards")
        for i in range(len(shards)):
            if not (root / f"shard_{i:02d}").is_dir():
                raise ValueError("Existing journal root is missing a registered shard")
        return saved
    root.mkdir(parents=True)
    for i in range(len(shards)):
        (root / f"shard_{i:02d}").mkdir()
    if prior:
        source = Path(prior) / "calls.jsonl"
        before, _ = audit_journal(source)
        if not source.is_file():
            raise ValueError("Prior journal file is missing")
        destination = root / "shard_00/calls.jsonl"
        shutil.copy2(source, destination)
        if file_digest(source) != before["journal_sha256"] or file_digest(destination) != before["journal_sha256"]:
            raise RuntimeError("Prior journal changed during copying; stop its writer before restarting")
        declaration["prior_copy"] = {"destination_shard": 0, "source": str(source.resolve()), **before}
    else:
        declaration["prior_copy"] = None
    write_json(marker, declaration)
    return declaration


def child_command(args, cases, episodes, journal, budget):
    command = [sys.executable, str(Path(__file__).with_name("unified_game_pipeline.py")), "rollout",
        "--cases", str(cases), "--output", str(episodes), "--engine", "jev",
        "--controller", "greedy", "--epsilon", "0.1", "--seed", "17",
        "--env-batch", "16", "--batch-questions", "16", "--max-length", "8192",
        "--env-file", str(args.env_file.resolve()), "--journal-dir", str(journal),
        "--budget-usd", budget]
    if args.remote_host:
        command += ["--remote-host", args.remote_host, "--remote-command", args.remote_cmd]
    return command


def validate_episode(episode, case, policy_id, calls):
    if (episode["case"] != case or episode.get("complete") is not True or
            episode.get("continuation_policy_id") != policy_id or type(episode.get("success")) is not bool):
        raise ValueError("Incomplete episode, changed case or policy identity")
    final = episode["final_info"]
    if (final.get("terminated") is not True or final.get("truncated") or
            final["success"] != episode["success"]):
        raise ValueError("Episode does not have a real terminal outcome")
    if case["spec"]["task"] == "shooting" and episode["success"] != (final["episode_metrics"]["kills"] > 0):
        raise ValueError("Shooting success differs from its real kill count")
    steps = episode["steps"]
    rng = random.Random(int(digest([case["id"], 17])[:16], 16))
    for i, step in enumerate(steps):
        if step["truncated"] or step["terminated"] != (i == len(steps)-1):
            raise ValueError("Early terminal, truncation or unfinished trajectory")
        expected_behavior = behavior_distribution(step["scores"], "greedy", .1)
        if step["behavior_probs"] != expected_behavior or step["action"] != choose(expected_behavior, rng):
            raise ValueError("Recorded actions do not replay from the fixed controller")
        if set(step["scores"]) != set(step["observation"]["candidates"]):
            raise ValueError("Invalid action support")
        if len(step["scores"]) == 1:
            if not step.get("forced") or step["answers"]:
                raise ValueError("A single-action transition must be recorded as forced")
            continue
        answer = step["answers"]["action"]
        receipt = calls.get(answer["source_api_call_id"])
        expected_input = {"model": "typesafe-ai/jev", "state": step["observation"]["state"],
                          "questions": policy_request(step["observation"], case["id"])["questions"]}
        if (receipt is None or receipt["input"] != expected_input or
                receipt["input_sha256"] != answer["source_input_sha256"] or
                receipt["native_probs"]["action"] != answer["native_probabilities"]):
            raise ValueError("Missing or mismatched per-shard successful API receipt")
        native = answer["native_probabilities"]
        if set(native) != set(step["scores"]) or any(not math.isfinite(p) or not 0 <= p <= 1 for p in native.values()):
            raise ValueError("Invalid native distribution")
        total = sum(native.values())
        if total <= 0 or any(abs(step["scores"][k] - native[k] / total) > 1e-12 for k in native):
            raise ValueError("Controller scores do not equal normalized native probabilities")


def merge_results(cases, case_path, jobs, output, expected_sources):
    """Only complete verified children may produce a complete merged artifact."""
    output = Path(output)
    expected_ids = [c["id"] for c in cases]
    expected_cases = {c["id"]: c for c in cases}
    rows, raw_by_id, source_map, child_receipts = {}, {}, {}, []
    policy = None
    for job in jobs:
        if job.get("returncode") != 0:
            raise ValueError("Every registered child must finish with exit code zero")
        path = Path(job["episodes"])
        manifest_path = path.with_suffix(".manifest.json")
        manifest = json.loads(manifest_path.read_text())
        group = read_rows(job["cases"])
        if any(expected_cases.get(case["id"]) != case for case in group):
            raise ValueError("Child case definitions differ from the original frozen file")
        if (manifest.get("finished") is not True or manifest["episode_sha256"] != file_digest(path) or
                manifest["cases_sha256"] != file_digest(job["cases"]) or
                manifest["selected_cases"] != [c["id"] for c in group]):
            raise ValueError("Child completion, case selection or source hash differs")
        current = manifest["policy"]
        if (current.get("engine") != "jev" or current.get("controller") != "greedy" or
                current.get("epsilon") != .1 or current.get("sampling_seed") != 17 or
                current.get("model") != "typesafe-ai/jev" or current.get("temperature") != 1.0 or
                current.get("tie_break") != "lexicographic_first" or
                current.get("environment_contract") != "finite_task_deadline_v1" or
                current.get("source_sha256") != expected_sources or
                manifest["continuation_policy_id"] != digest(current)):
            raise ValueError("Child policy or implementation differs from the frozen contract")
        if policy is not None and current != policy:
            raise ValueError("Mixed child policies")
        policy = current
        snapshot = manifest_path.parent / manifest["source_snapshot"]
        for name, sha in expected_sources.items():
            if file_digest(snapshot / name) != sha:
                raise ValueError("Child source snapshot differs")
        accounting, calls = audit_journal(Path(job["journal"]) / "calls.jsonl")
        if money(accounting["accounted_usd"]) > money(job["budget_usd"]) + NANO:
            raise ValueError("Child reported costs and reservations exceed its allocation")
        raw_lines = [line for line in path.read_bytes().splitlines(keepends=True) if line.strip()]
        if len(raw_lines) != len(group):
            raise ValueError("Missing or extra child episode")
        child_rows = []
        for case, raw in zip(group, raw_lines):
            row = json.loads(raw)
            validate_episode(row, case, manifest["continuation_policy_id"], calls)
            if case["id"] in rows:
                raise ValueError("Duplicate episode across shards")
            rows[case["id"]], raw_by_id[case["id"]] = row, raw
            source_map[case["id"]] = job["shard"]
            child_rows.append(row)
        if manifest["summary"] != summarize(child_rows):
            raise ValueError("Child aggregate metrics differ from raw episodes")
        child_receipts.append({"shard": job["shard"], "manifest_sha256": file_digest(manifest_path),
            "episode_sha256": file_digest(path), "cases_sha256": file_digest(job["cases"]),
            "manifest": str(manifest_path), "journal": job["journal"],
            "budget_usd": job["budget_usd"], "accounting": accounting,
            "attempts": job.get("attempts", [])})
    if set(rows) != set(expected_ids) or len(rows) != len(cases):
        raise ValueError("Merged collection must contain every original case exactly once")
    destination = output / "episodes.jsonl"
    if destination.exists():
        raise ValueError("Merged output already exists")
    ordered = [rows[key] for key in expected_ids]
    temporary = destination.with_suffix(".jsonl.tmp")
    with temporary.open("xb") as handle:
        for key in expected_ids:
            raw = raw_by_id[key]
            handle.write(raw if raw.endswith(b"\n") else raw + b"\n")
    os.replace(temporary, destination)
    snapshot = output / "episodes.sources"
    snapshot.mkdir()
    for name, sha in expected_sources.items():
        source = Path(__file__).with_name(name)
        if file_digest(source) != sha:
            raise ValueError("Local source changed during collection")
        shutil.copy2(source, snapshot / name)
    manifest = {"schema_version": "nanojev-unified-episodes-v1", "finished": True,
        "policy": policy, "continuation_policy_id": digest(policy), "cases_sha256": file_digest(case_path),
        "selected_cases": expected_ids, "episode_sha256": file_digest(destination),
        "source_snapshot": snapshot.name, "summary": summarize(ordered),
        "parallel_children": child_receipts, "episode_journal_shards": source_map,
        "api_receipt_identity": "(journal shard, source_api_call_id); IDs are not globally unique",
        "reported_cost_usd": str(sum(money(c["accounting"]["reported_cost_usd"]) for c in child_receipts)),
        "unknown_reserved_usd": str(sum(money(c["accounting"]["unknown_reserved_usd"]) for c in child_receipts)),
        "unknown_reservation_count": sum(len(c["accounting"]["unknown_cost_ids"]) for c in child_receipts),
        "accounting_scope": "Includes prior journal exactly once in shard zero; zero reported cost is not independent billing verification."}
    write_json(output / "episodes.manifest.json", manifest)
    return manifest


def stop_children(processes):
    alive = [p for p in processes if p.poll() is None]
    for process in alive:
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while any(p.poll() is None for p in alive) and time.monotonic() < deadline:
        time.sleep(.1)
    for process in alive:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()


def execute_jobs(jobs, max_active, max_attempts, update=lambda: None,
                 popen=subprocess.Popen, clock=time.monotonic, sleep=time.sleep):
    """Independent bounded retries; only external interruption stops other shards."""
    if max_active < 1 or max_attempts < 1:
        raise ValueError("Positive active and attempt limits are required")
    running, eligible_after = {}, {}
    origin = clock()
    for job in jobs:
        job.update(state="ready", attempts=[], returncode=None)
        eligible_after[job["shard"]] = origin
    try:
        while True:
            now = clock()
            for shard, (job, process, log, attempt) in list(running.items()):
                code = process.poll()
                if code is None:
                    continue
                log.close()
                attempt.update(returncode=code, finished_elapsed_seconds=now-origin)
                job["returncode"] = code
                del running[shard]
                if code == 0:
                    job["state"] = "succeeded"
                elif len(job["attempts"]) >= max_attempts:
                    job["state"] = "exhausted"
                else:
                    job["state"] = "cooldown"
                    eligible_after[shard] = now + 30.0
                    attempt["retry_delay_seconds"] = 30
            if all(j["state"] in ("succeeded", "exhausted") for j in jobs):
                update()
                return all(j["state"] == "succeeded" for j in jobs)
            available = [j for j in jobs if j["state"] in ("ready", "cooldown")
                         and eligible_after[j["shard"]] <= now]
            # Fresh shards are not starved by a repeatedly failing early shard.
            available.sort(key=lambda j: (len(j["attempts"]), j["shard"]))
            for job in available[:max(0, max_active-len(running))]:
                number = len(job["attempts"]) + 1
                directory = Path(job["cases"]).parent / f"attempt_{number:02d}"
                directory.mkdir(exist_ok=False)
                episodes = directory / "episodes.jsonl"
                command = list(job["command"])
                command[command.index("--output") + 1] = str(episodes)
                # Journal and USD allocation are identical for every attempt.
                if (command[command.index("--journal-dir") + 1] != job["journal"] or
                        command[command.index("--budget-usd") + 1] != job["budget_usd"]):
                    raise ValueError("Attempt changed its journal or fixed budget")
                log = (directory / "pipeline.log").open("x")
                attempt = {"attempt": number, "episodes": str(episodes), "command": command,
                    "started_elapsed_seconds": clock()-origin, "returncode": None}
                job["attempts"].append(attempt)
                try:
                    process = popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                except BaseException:
                    log.close()
                    raise
                attempt["pid"] = process.pid
                job.update(episodes=str(episodes), command=command, pid=process.pid,
                           returncode=None, state="running")
                running[job["shard"]] = (job, process, log, attempt)
            update()
            sleep(1)
    except BaseException:
        # Explicit interruption or local runner failure is distinct from an API
        # child returning nonzero. The latter never signals unrelated children.
        stop_children([entry[1] for entry in running.values()])
        for job, process, log, attempt in running.values():
            log.close()
            code = process.poll()
            attempt.update(returncode=code, finished_elapsed_seconds=clock()-origin)
            job.update(returncode=code, state="interrupted")
        update()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cases", "output", "journal-root", "env-file"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--prior-journal-dir", type=Path)
    parser.add_argument("--remote-host")
    parser.add_argument("--remote-cmd", "--remote-command", dest="remote_cmd")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-active", type=int, default=2,
                        help="Concurrent shards; each uses four HTTP slots")
    parser.add_argument("--max-attempts", type=int, default=4,
                        help="Maximum attempts per shard, sharing its original journal and budget")
    parser.add_argument("--total-budget-usd", default="3")
    args = parser.parse_args()
    if bool(args.remote_host) != bool(args.remote_cmd):
        parser.error("Provide both remote host and command, or neither")
    cases = read_rows(args.cases)
    validate_cases(cases)
    if not cases:
        parser.error("The fixed case file cannot be empty")
    if args.workers < 1 or args.workers > 8:
        parser.error("Use one through eight independent pipeline children")
    if not 1 <= args.max_active <= args.workers or not 1 <= args.max_attempts <= 4:
        parser.error("Use max-active from one to workers and max-attempts from one to four")
    if args.output.exists():
        parser.error("Use a fresh --output directory")
    args.output, args.journal_root = args.output.resolve(), args.journal_root.resolve()
    groups = ordered_shards(cases, args.workers)
    journals = prepare_journals(args.journal_root, args.prior_journal_dir, file_digest(args.cases), groups)
    prior = [audit_journal(args.journal_root / f"shard_{i:02d}/calls.jsonl")[0] for i in range(len(groups))]
    budgets = allocate_budgets(args.total_budget_usd, [r["accounted_usd"] for r in prior])
    args.output.mkdir(parents=True)
    sources = source_hashes()
    jobs = []
    for i, group in enumerate(groups):
        directory = args.output / f"shard_{i:02d}"
        directory.mkdir()
        subset = directory / "cases.jsonl"
        subset.write_text("".join(encode(c) + "\n" for c in group))
        episodes, journal = directory / "episodes.jsonl", args.journal_root / f"shard_{i:02d}"
        jobs.append({"shard": i, "cases": str(subset), "episodes": str(episodes), "journal": str(journal),
            "budget_usd": budgets[i], "returncode": None,
            "command": child_command(args, subset, episodes, journal, budgets[i])})
    report = {"schema": "nanojev-parallel-jev-run-v1", "finished": False,
        "runner_sha256": file_digest(__file__), "cases_sha256": file_digest(args.cases),
        "total_budget_usd": str(money(args.total_budget_usd)), "allocated_budget_usd": str(sum(map(Decimal, budgets))),
        "prior_accounting": prior, "journal_declaration": journals, "jobs": jobs,
        "source_sha256": sources, "http_concurrency_per_child": 4, "env_batch_per_child": 16,
        "max_active": args.max_active, "max_attempts_per_shard": args.max_attempts,
        "retry_delay_seconds": 30, "failed_shard_does_not_interrupt_others": True,
        "controller": {"mode": "greedy", "epsilon": .1, "seed": 17}}
    report_path = args.output / "parallel_run.json"
    write_json(report_path, report)
    try:
        completed = execute_jobs(jobs, args.max_active, args.max_attempts,
                                 update=lambda: write_json(report_path, report))
        if not completed:
            raise RuntimeError("One or more shards exhausted their attempts; all other shards have finished")
        merged = merge_results(cases, args.cases, jobs, args.output, sources)
        report.update(finished=True, merged_episode_sha256=merged["episode_sha256"],
                      reported_cost_usd=merged["reported_cost_usd"], unknown_reserved_usd=merged["unknown_reserved_usd"])
    except BaseException as exc:
        report.update(finished=False, error_type=type(exc).__name__)
        raise
    finally:
        # Parse after stopping writers; interrupted requests remain reserved.
        try:
            report["final_accounting"] = [audit_journal(Path(j["journal"]) / "calls.jsonl")[0] for j in jobs]
            report["final_reported_cost_usd"] = str(sum(money(r["reported_cost_usd"]) for r in report["final_accounting"]))
            report["final_unknown_reserved_usd"] = str(sum(money(r["unknown_reserved_usd"]) for r in report["final_accounting"]))
        except Exception as exc:
            report["accounting_error"] = type(exc).__name__
            report["finished"] = False
        write_json(report_path, report)


if __name__ == "__main__":
    main()
