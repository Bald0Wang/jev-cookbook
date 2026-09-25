"""CLI: run + summarize.

Usage:
  python -m llm_eval.cli run --tasks tasks/public.jsonl --adapter deepseek \
      --model deepseek-chat --key-env DEEPSEEK_API_KEY \
      --price-in-per-m 0.14 --price-out-per-m 2.8 \
      --results runs/ds/results.jsonl --raw-dir runs/ds/raw \
      --ledger runs/ds/ledger.jsonl --cap-usd 5

  python -m llm_eval.cli summarize --tasks tasks/public.jsonl \
      --results runs/ds/results.jsonl --public-export runs/ds/summary.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .runner import run
from .summarize import load_results, public_export
from .task import load_tasks, dataset_hash


# Adapter registry — populated by adapters/__init__.py
def _adapters():
    from .adapters import get_adapter
    return get_adapter


def cmd_run(a):
    tasks = load_tasks(a.tasks)
    price_in = float(a.price_in_per_m) if a.price_in_per_m is not None else None
    price_out = float(a.price_out_per_m) if a.price_out_per_m is not None else None
    key = os.environ.get(a.key_env, "") if a.key_env else ""

    adapter_factory = _adapters()
    adapter = adapter_factory(
        name=a.adapter,
        model=a.model,
        endpoint=a.endpoint,
        key=key,
        request_options=json.loads(a.request_options) if a.request_options else None,
        price_in_per_m=price_in,
        price_out_per_m=price_out,
        max_input_tokens=a.max_input_tokens,
        max_output_tokens=a.max_output_tokens,
    )

    results = run(
        tasks=tasks,
        adapter=adapter,
        ledger_path=a.limit_ledger,
        cap_usd=a.cap_usd,
        out_path=a.results,
        raw_dir=a.raw_dir,
        price_in_per_m=price_in,
        price_out_per_m=price_out,
        delay_s=a.delay_s,
        max_input_tokens=a.max_input_tokens,
        max_output_tokens=a.max_output_tokens,
    )
    print(
        f"completed: {sum(1 for r in results if r.get('status') == 'ok')} ok / "
        f"{sum(1 for r in results if r.get('status') == 'invalid')} invalid / "
        f"{sum(1 for r in results if r.get('status') == 'error')} error / "
        f"{sum(1 for r in results if r.get('status') == 'unattempted')} unattempted",
        file=sys.stderr,
    )


def cmd_multi_run(a):
    from .multi_config import load_config
    from .multi_runner import run_multi

    cfg = load_config(a.config)
    manifest = run_multi(cfg)
    n_done = sum(1 for r in manifest["runners"] if r["status"] == "ok")
    n_skip = sum(
        1 for r in manifest["runners"] if r["status"].startswith("skipped")
    )
    n_err = sum(
        1
        for r in manifest["runners"]
        if r["status"] in ("config_error", "runner_crashed")
    )
    print(
        f"\nmulti-run done: {n_done} ran / {n_skip} skipped / {n_err} errors",
        file=sys.stderr,
    )
    print(
        f"manifest: {a.out_root.rstrip('/')}/{cfg.run_id}/_manifest.json",
        file=sys.stderr,
    )


def cmd_compare(a):
    from .compare import compare_run, write_markdown_table

    cmp = compare_run(a.run_dir)
    if a.markdown:
        write_markdown_table(cmp, a.markdown)
        print(f"wrote {a.markdown}", file=sys.stderr)
    if a.public_export:
        with open(a.public_export, "w", encoding="utf-8") as f:
            json.dump(cmp, f, ensure_ascii=False, indent=2)
        print(f"wrote {a.public_export}", file=sys.stderr)
    else:
        print(json.dumps(cmp, ensure_ascii=False, indent=2))


def cmd_summarize(a):
    tasks = load_tasks(a.tasks)
    results = load_results(a.results)
    meta = {
        "tasks": a.tasks,
        "results": a.results,
        "dataset_hash": dataset_hash(tasks),
    }
    summary = public_export(results, tasks, run_meta=meta)
    if a.public_export:
        import pathlib
        pathlib.Path(a.public_export).parent.mkdir(parents=True, exist_ok=True)
        with open(a.public_export, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"wrote {a.public_export}", file=sys.stderr)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run the harness over a task set")
    p_run.add_argument("--tasks", required=True, help="path to JSONL tasks")
    p_run.add_argument(
        "--adapter",
        required=True,
        choices=[
            "mock",
            "openai_compat",
            "deepseek",
            "qwen",
            "glm",
            "moonshot",
            "doubao",
            "stepfun",
            "xiaomi",
        ],
    )
    p_run.add_argument("--model", default="", help="model name (provider-specific)")
    p_run.add_argument(
        "--endpoint", default="", help="override base URL (OpenAI-compatible adapters)"
    )
    p_run.add_argument(
        "--key-env",
        default="",
        help="env var name holding the API key; '' sends no Authorization header",
    )
    p_run.add_argument("--price-in-per-m", default=None)
    p_run.add_argument("--price-out-per-m", default=None)
    p_run.add_argument("--request-options", default="", help="JSON dict to merge into request")
    p_run.add_argument("--results", required=True, help="output results.jsonl")
    p_run.add_argument("--raw-dir", default="", help="directory for raw response bodies")
    p_run.add_argument("--limit-ledger", required=True, help="ledger jsonl path")
    p_run.add_argument("--cap-usd", type=float, default=15.0)
    p_run.add_argument("--delay-s", type=float, default=0.0)
    p_run.add_argument("--max-input-tokens", type=int, default=2000)
    p_run.add_argument("--max-output-tokens", type=int, default=200)
    p_run.set_defaults(func=cmd_run)

    p_sum = sub.add_parser("summarize", help="Aggregate results.jsonl")
    p_sum.add_argument("--tasks", required=True)
    p_sum.add_argument("--results", required=True)
    p_sum.add_argument("--public-export", default="")
    p_sum.set_defaults(func=cmd_summarize)

    p_multi = sub.add_parser(
        "multi-run", help="Run multiple (adapter, model) runners from one config"
    )
    p_multi.add_argument("--config", required=True, help="path to multi-run JSON config")
    p_multi.add_argument(
        "--out-root",
        default="runs",
        help="root dir for per-runner outputs (default: runs)",
    )
    p_multi.set_defaults(func=cmd_multi_run)

    p_cmp = sub.add_parser(
        "compare",
        help="Cross-runner comparison: read all summary.json under a run_id dir",
    )
    p_cmp.add_argument("--run-dir", required=True, help="runs/<run_id>/ path")
    p_cmp.add_argument("--public-export", default="")
    p_cmp.add_argument("--markdown", default="")
    p_cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())