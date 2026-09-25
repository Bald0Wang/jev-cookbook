"""Serial runner. Reserves, calls, records, settles, scores.

Designed to be honest:
  * no retries
  * no fallbacks to another model
  * no repairing of bad answers
  * one request at a time, no concurrency
  * 401/403/429 or 20 consecutive infra errors -> stop, mark remainder unattempted

Live progress (when ``verbose=True`` or env LBEVAL_VERBOSE=1):
  * prints the full task list at start so learners know the scope
  * per-task line with status / latency / cost / verdict mark
  * every N tasks (env LBEVAL_PROGRESS_EVERY, default 10) prints a running tally
  * prints the unfinished list when stopped early
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .ledger import BudgetExceeded, Ledger
from .task import Task
from .scorer import score_distribution
from .adapters.base import AdapterError


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (ValueError, TypeError):
        return default


def _truncate(s: str, n: int) -> str:
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _top_prob(probs: dict) -> tuple[str, float]:
    """Return (label, prob) for the highest-prob label.

    Coerces values to float defensively — some providers return
    probabilities as strings ("0.99"), which would otherwise crash
    max()'s comparison.
    """
    if not probs:
        return ("—", 0.0)
    # Coerce each value to float; treat unparseable as 0.0 so they
    # never accidentally win the max.
    coerced: list[tuple[str, float]] = []
    for k, v in probs.items():
        try:
            coerced.append((str(k), float(v)))
        except (TypeError, ValueError):
            continue
    if not coerced:
        return ("—", 0.0)
    label, p = max(coerced, key=lambda kv: kv[1])
    return (label, p)


def _maybe_print_tally(tag: str, done: int, total: int, tally: dict, every: int) -> None:
    """Every N tasks, print a running tally + bar so learners can see progress."""
    if every <= 0:
        return
    if done % every != 0 and done != total:
        return
    total_done = sum(tally.values())
    print(
        f"{tag}── tally @ {done}/{total} ── "
        f"ok={tally['ok']}  invalid={tally['invalid']}  "
        f"error={tally['error']}  unattempted={tally['unattempted']}  "
        f"({total_done} records written)  {_bar(done, total)}",
        flush=True,
    )


def _bar(done: int, total: int, width: int = 30) -> str:
    if total == 0:
        return "[" + " " * width + "]"
    filled = int(round(width * done / total))
    return "[" + "█" * filled + "·" * (width - filled) + f"] {done}/{total}"


def run(
    tasks: list[Task],
    adapter,
    ledger_path: str,
    cap_usd: float,
    out_path: str,
    raw_dir: str | None,
    price_in_per_m: float | None,
    price_out_per_m: float | None,
    delay_s: float = 0.0,
    max_input_tokens: int = 2000,
    max_output_tokens: int = 200,
    runner_name: str = "",
    verbose: bool = False,
) -> list[dict]:
    """Drive the adapter over `tasks`. Returns scored results (one per task).

    status values per record:
      "ok"      : adapter returned a parseable distribution
      "invalid" : adapter returned but distribution is malformed
      "error"   : adapter raised or returned non-2xx
      "unattempted": stopped before reaching this task (rate-limit etc.)
    """
    ledger = Ledger(ledger_path, cap_usd=cap_usd)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if raw_dir:
        Path(raw_dir).mkdir(parents=True, exist_ok=True)

    # Resume support: append to existing file if present.
    existing_records: list[dict] = []
    try:
        with open(out_path, "r", encoding="utf-8") as f_in:
            for ln in f_in:
                ln = ln.strip()
                if ln:
                    existing_records.append(json.loads(ln))
    except FileNotFoundError:
        pass
    done_ids = {r.get("task_id") for r in existing_records}

    out_f = open(out_path, "a", encoding="utf-8")
    results: list[dict] = list(existing_records)
    consecutive_err = 0
    stopped = False
    stop_reason: str | None = None

    n_total = len(tasks)
    n_done_skip = len(done_ids)
    tag = f"[{runner_name}] " if runner_name else ""
    progress_every = _env_int("LBEVAL_PROGRESS_EVERY", 10)
    show_prompt = os.environ.get("LBEVAL_VERBOSE_PROMPT", "").strip() == "1"
    show_output = os.environ.get("LBEVAL_VERBOSE_OUTPUT", "").strip() == "1"

    # === Live progress: print the full scope up front so learners know what's queued ===
    if verbose:
        all_ids = [t.id for t in tasks]
        pending_ids = [tid for tid in all_ids if tid not in done_ids]
        print(
            f"{tag}── scope ── {n_total} tasks total · "
            f"{n_done_skip} already on disk · {len(pending_ids)} to run",
            flush=True,
        )
        if len(pending_ids) <= 50:
            print(
                f"{tag}task list ({len(pending_ids)}): "
                + ", ".join(pending_ids),
                flush=True,
            )
        else:
            print(
                f"{tag}task list (first 20 of {len(pending_ids)}): "
                + ", ".join(pending_ids[:20])
                + f"  … (+{len(pending_ids) - 20} more)",
                flush=True,
            )
        print(
            f"{tag}progress bar: {_bar(n_done_skip, n_total)}  "
            f"(updates every {progress_every} tasks)",
            flush=True,
        )

    # running counters for periodic tally
    tally = {"ok": 0, "invalid": 0, "error": 0, "unattempted": 0}
    n_attempted_this_run = 0  # excludes already-on-disk

    for i, task in enumerate(tasks):
        if task.id in done_ids:
            # Already completed in a prior run; skip (don't count in this-run tally).
            if verbose:
                print(
                    f"{tag}task {i+1}/{n_total}  {task.id}  "
                    f"status=resumed  (already on disk)",
                    flush=True,
                )
            continue
        if stopped:
            record = {
                "task_id": task.id,
                "family": task.family,
                "question_type": task.question_type,
                "status": "unattempted",
                "stop_reason": stop_reason,
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            results.append(record)
            tally["unattempted"] += 1
            if verbose:
                print(
                    f"{tag}task {i+1}/{n_total}  {task.id}  "
                    f"status=unattempted  reason={stop_reason}",
                    flush=True,
                )
            continue

        # Worst-case reserve
        if price_in_per_m is not None and price_out_per_m is not None:
            worst = (
                max_input_tokens * price_in_per_m / 1e6
                + max_output_tokens * price_out_per_m / 1e6
            )
        else:
            worst = 0.0  # free / unmetered route; settlement will be 0 too
        try:
            rid = ledger.reserve(worst, meta={"task": task.id})
        except BudgetExceeded as e:
            stopped = True
            stop_reason = f"budget:{e}"
            record = {
                "task_id": task.id,
                "family": task.family,
                "question_type": task.question_type,
                "status": "unattempted",
                "stop_reason": stop_reason,
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            results.append(record)
            tally["unattempted"] += 1
            if verbose:
                print(
                    f"{tag}task {i+1}/{n_total}  {task.id}  "
                    f"status=unattempted  reason=budget_exceeded  ({e})",
                    flush=True,
                )
            continue

        # === Live progress: announce which task is starting ===
        n_attempted_this_run += 1
        if verbose:
            print(
                f"{tag}▶ task {i+1}/{n_total}  {task.id}  "
                f"[{task.family}/{task.question_type}]  starting…",
                flush=True,
            )
            if show_prompt:
                print(
                    f"{tag}  prompt: instructions={_truncate(task.instructions, 120)!r}  "
                    f"state_keys={list(task.state.keys())}  "
                    f"labels={task.labels}",
                    flush=True,
                )

        # Call adapter
        t0 = time.perf_counter()
        try:
            resp = adapter.call(task)
            latency = time.perf_counter() - t0
        except AdapterError as e:
            latency = time.perf_counter() - t0
            try:
                ledger.settle(rid, 0.0, meta={"error": str(e)[:200]})
            except BudgetExceeded:
                pass
            if e.fatal:
                stopped = True
                stop_reason = f"adapter_fatal:{e.code}"
                record = {
                    "task_id": task.id,
                    "family": task.family,
                    "question_type": task.question_type,
                    "status": "error",
                    "error": str(e),
                    "latency_s": latency,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()
                results.append(record)
                tally["error"] += 1
                if verbose:
                    print(
                        f"{tag}✗ task {i+1}/{n_total}  {task.id}  "
                        f"status=error  fatal={e.code}  ({latency:.1f}s)  {str(e)[:120]}",
                        flush=True,
                    )
                    _maybe_print_tally(tag, i + 1, n_total, tally, progress_every)
                continue
            # Non-fatal: parse/infra hiccups. Up to 20 consecutive, then stop.
            consecutive_err += 1
            if consecutive_err >= 20:
                stopped = True
                stop_reason = "20_consecutive_infra_errors"
                record = {
                    "task_id": task.id,
                    "family": task.family,
                    "question_type": task.question_type,
                    "status": "error",
                    "error": str(e),
                    "latency_s": latency,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()
                results.append(record)
                tally["error"] += 1
                if verbose:
                    print(
                        f"{tag}✗ task {i+1}/{n_total}  {task.id}  "
                        f"status=error  20_consecutive_stop  ({latency:.1f}s)  "
                        f"{str(e)[:80]}",
                        flush=True,
                    )
                    _maybe_print_tally(tag, i + 1, n_total, tally, progress_every)
                continue
            record = {
                "task_id": task.id,
                "family": task.family,
                "question_type": task.question_type,
                "status": "error",
                "error": str(e),
                "latency_s": latency,
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            results.append(record)
            tally["error"] += 1
            if verbose:
                print(
                    f"{tag}✗ task {i+1}/{n_total}  {task.id}  "
                    f"status=error  consecutive={consecutive_err}/20  "
                    f"({latency:.1f}s)  {str(e)[:80]}",
                    flush=True,
                )
                _maybe_print_tally(tag, i + 1, n_total, tally, progress_every)
            continue

        # Success path
        consecutive_err = 0
        usage = resp.get("usage") or {}
        # Coerce to int defensively (some providers return string or float).
        try:
            in_tok = int(usage.get("prompt_tokens") or 0)
        except (TypeError, ValueError):
            in_tok = 0
        try:
            out_tok = int(usage.get("completion_tokens") or 0)
        except (TypeError, ValueError):
            out_tok = 0
        if price_in_per_m is not None and price_out_per_m is not None:
            # Also coerce prices to float, just in case a PROVIDER_TABLE entry
            # accidentally shipped a string price.
            try:
                pin = float(price_in_per_m)
                pout = float(price_out_per_m)
                cost = in_tok * pin / 1e6 + out_tok * pout / 1e6
            except (TypeError, ValueError):
                cost = 0.0
        else:
            cost = 0.0
        try:
            ledger.settle(rid, cost, meta={"task": task.id})
        except BudgetExceeded:
            # settlement larger than reserved — bad assumption, stop
            stopped = True
            stop_reason = "settlement_exceeded_reservation"

        scored = score_distribution(
            resp.get("probs") or {}, task, source=resp.get("source", "unknown")
        )
        record = {
            "task_id": task.id,
            "family": task.family,
            "question_type": task.question_type,
            "status": "ok" if scored["valid"] else "invalid",
            "probs": resp.get("probs"),
            "source": resp.get("source", "unknown"),
            "model": resp.get("model", ""),
            "latency_s": latency,
            "usage": usage,
            "cost_usd": cost,
            **scored,
        }
        out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
        out_f.flush()
        results.append(record)
        tally[record["status"]] += 1

        if raw_dir:
            raw_path = Path(raw_dir) / f"{task.id}.json"
            try:
                raw_path.write_text(
                    json.dumps(
                        {
                            "task_id": task.id,
                            "request": resp.get("request_body"),
                            "response": resp.get("raw"),
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass

        if verbose:
            valid_mark = "✓" if scored["valid"] else "✗"
            correct_mark = ""
            expected_str = (
                f"expected={task.expected!r}" if task.expected is not None else "expected=—"
            )
            top_label, top_p = _top_prob(record.get("probs") or {})
            if scored.get("correct_value") is True:
                correct_mark = " 🎯 correct"
            elif scored.get("correct_value") is False:
                correct_mark = " ✗ wrong"
            print(
                f"{tag}● task {i+1}/{n_total}  {task.id}  "
                f"status={record['status']}{valid_mark}  "
                f"top={top_label}({top_p:.2f})  {expected_str}  "
                f"({latency:.1f}s, ${cost:.4f}, {in_tok}↓{out_tok}↑){correct_mark}",
                flush=True,
            )
            if show_output:
                print(
                    f"{tag}  output: {_truncate(json.dumps(record.get('probs'), ensure_ascii=False), 200)}",
                    flush=True,
                )
            _maybe_print_tally(tag, i + 1, n_total, tally, progress_every)

        if delay_s > 0:
            time.sleep(delay_s)

    # === End-of-run summary: list what's still missing, even if nothing crashed ===
    if verbose:
        finished_ids = {r.get("task_id") for r in results}
        unfinished = [t.id for t in tasks if t.id not in finished_ids]
        print(
            f"{tag}── final ── ok={tally['ok']}  invalid={tally['invalid']}  "
            f"error={tally['error']}  unattempted={tally['unattempted']}  "
            f"records_on_disk={len(results)}/{n_total}  "
            f"{_bar(len(results), n_total)}",
            flush=True,
        )
        if stopped:
            print(f"{tag}stop reason: {stop_reason}", flush=True)
        if unfinished:
            sample = unfinished[:20]
            extra = len(unfinished) - len(sample)
            print(
                f"{tag}unfinished tasks ({len(unfinished)}/{n_total}): "
                + ", ".join(sample)
                + (f"  … (+{extra} more)" if extra > 0 else ""),
                flush=True,
            )

    out_f.close()
    return results