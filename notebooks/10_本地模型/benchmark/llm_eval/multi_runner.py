"""Multi-runner orchestrator.

For each runner in the config, drive the existing single-model runner against
the same task set. Each runner gets its own output dir, its own ledger, its own
budget. Skips runners whose key_env is unset (with a warning). Resumes a runner
whose results.jsonl already contains all tasks (skip_if_done=True, default).

Output layout under <out_root>/<run_id>/:
    _manifest.json                  # run metadata + per-runner status
    <runner.name>/                  # per-runner dir
            results.jsonl
            summary.json
            ledger.jsonl
            raw/<task_id>.json     # raw request/response bodies
    compare.json                    # cross-runner comparison table

Nothing else is special — the actual model call goes through runner.run().
"""
from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

from .adapters import get_adapter
from .multi_config import MultiRunConfig, RunnerConfig
from .runner import run
from .summarize import public_export
from .task import dataset_hash, load_tasks


def _slug(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)


def _already_done(out_dir: str, task_ids: set[str]) -> bool:
    p = Path(out_dir) / "results.jsonl"
    if not p.exists():
        return False
    done = set()
    with p.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                done.add(json.loads(ln).get("task_id"))
    return task_ids.issubset(done)


def run_multi(cfg: MultiRunConfig) -> dict:
    """Execute the multi-runner plan. Returns a manifest dict."""
    tasks = load_tasks(cfg.tasks_path)
    task_ids = {t.id for t in tasks}
    base = Path(cfg.out_root) / cfg.run_id
    base.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "run_id": cfg.run_id,
        "started_at": time.time(),
        "tasks_path": cfg.tasks_path,
        "dataset_hash": dataset_hash(tasks),
        "n_tasks": len(tasks),
        "runners": [],
    }

    # === Print full plan up front so learners know what's queued ===
    print(
        f"[plan] run_id={cfg.run_id}  tasks={cfg.tasks_path}  n={len(tasks)}  "
        f"cap=${cfg.cap_usd}/runner  parallel={cfg.delay_s}",
        flush=True,
    )
    print(
        f"[plan] runners queued: {len(cfg.runners)} → "
        + ", ".join(r.name for r in cfg.runners),
        flush=True,
    )
    print(
        f"[plan] task ids ({len(tasks)}): "
        + ", ".join(t.id for t in tasks[:20])
        + (f"  … (+{len(tasks) - 20} more)" if len(tasks) > 20 else ""),
        flush=True,
    )

    for runner in cfg.runners:
        slug = _slug(runner.name)
        out_dir = str(base / slug)
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        entry: dict = {"name": runner.name, "dir": out_dir, "status": "pending"}

        if not runner.is_available():
            entry["status"] = "skipped_no_key"
            entry["reason"] = (
                f"env var {runner.key_env!r} not set" if runner.key_env else "no key_env"
            )
            manifest["runners"].append(entry)
            print(f"[skip] {runner.name}: {entry['reason']}", flush=True)
            continue

        if runner.skip_if_done and _already_done(out_dir, task_ids):
            entry["status"] = "skipped_already_done"
            manifest["runners"].append(entry)
            print(f"[skip] {runner.name}: already complete in {out_dir}", flush=True)
            continue

        try:
            adapter = get_adapter(
                name=runner.adapter,
                model=runner.model,
                endpoint=runner.endpoint,
                key=runner.effective_key(),
                request_options=(runner.request_options or cfg.request_options),
                price_in_per_m=runner.price_in_per_m,
                price_out_per_m=runner.price_out_per_m,
                max_input_tokens=cfg.max_input_tokens,
                max_output_tokens=cfg.max_output_tokens,
            )
        except Exception as e:
            entry["status"] = "config_error"
            entry["error"] = str(e)
            manifest["runners"].append(entry)
            print(f"[error] {runner.name}: adapter init failed: {e}", flush=True)
            continue

        n_tasks_total = len(tasks)
        # List which tasks are still pending for this runner, so learners can watch.
        existing_path = Path(out_dir) / "results.jsonl"
        already_done_ids: set[str] = set()
        if existing_path.exists():
            try:
                with existing_path.open("r", encoding="utf-8") as f:
                    for ln in f:
                        ln = ln.strip()
                        if ln:
                            already_done_ids.add(json.loads(ln).get("task_id"))
            except Exception:
                pass
        pending_ids = [t.id for t in tasks if t.id not in already_done_ids]
        print(
            f"[run]  {runner.name} ({runner.model})  "
            f"→ {n_tasks_total} tasks on {cfg.tasks_path}",
            flush=True,
        )
        print(
            f"[run]  {runner.name}: {len(already_done_ids)} already on disk, "
            f"{len(pending_ids)} to run now",
            flush=True,
        )
        if pending_ids:
            head = ", ".join(pending_ids[:15])
            tail = f"  … (+{len(pending_ids) - 15} more)" if len(pending_ids) > 15 else ""
            print(f"[run]  {runner.name} pending: {head}{tail}", flush=True)
        t0 = time.time()
        try:
            results = run(
                tasks=tasks,
                adapter=adapter,
                ledger_path=str(Path(out_dir) / "ledger.jsonl"),
                cap_usd=cfg.cap_usd,
                out_path=str(Path(out_dir) / "results.jsonl"),
                raw_dir=str(Path(out_dir) / "raw"),
                price_in_per_m=runner.price_in_per_m,
                price_out_per_m=runner.price_out_per_m,
                delay_s=cfg.delay_s,
                max_input_tokens=cfg.max_input_tokens,
                max_output_tokens=cfg.max_output_tokens,
                runner_name=runner.name,
                verbose=True,
            )
        except Exception as e:
            entry["status"] = "runner_crashed"
            entry["error"] = repr(e)
            entry["traceback"] = traceback.format_exc()
            entry["elapsed_s"] = time.time() - t0
            manifest["runners"].append(entry)
            print(f"[error] {runner.name}: runner crashed: {e}", flush=True)
            # Print the last 6 lines of the traceback so the operator can see
            # the failing line without opening the manifest.
            tb_tail = entry["traceback"].strip().splitlines()[-6:]
            for ln in tb_tail:
                print(f"    {ln}", flush=True)
            continue

        # Summarize
        summary = public_export(
            results,
            tasks,
            run_meta={
                "run_id": cfg.run_id,
                "runner": runner.name,
                "adapter": runner.adapter,
                "model": runner.model,
            },
        )
        with open(Path(out_dir) / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        entry["status"] = "ok"
        entry["elapsed_s"] = time.time() - t0
        entry["n_ok"] = sum(1 for r in results if r.get("status") == "ok")
        entry["n_invalid"] = sum(1 for r in results if r.get("status") == "invalid")
        entry["n_error"] = sum(1 for r in results if r.get("status") == "error")
        entry["n_unattempted"] = sum(
            1 for r in results if r.get("status") == "unattempted"
        )
        manifest["runners"].append(entry)
        print(
            f"[done] {runner.name}: "
            f"{entry['n_ok']} ok / {entry['n_error']} err / {entry['n_unattempted']} unat "
            f"in {entry['elapsed_s']:.0f}s",
            flush=True,
        )

    manifest["finished_at"] = time.time()
    with open(base / "_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest