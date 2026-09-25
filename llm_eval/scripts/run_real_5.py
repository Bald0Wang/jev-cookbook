"""Real-data runner for the notebook demo.

Runs all confirmed-working providers (those whose key + model name are valid)
end-to-end on tasks/public_all.jsonl. Writes summary.json / results.jsonl /
ledger.jsonl / raw/ under runs/notebook-demo/real/<provider>/ so that
cell 14's cross-model chart can surface real data without any estimation.

Inputs (env vars, never echoed or logged):
  DEEPSEEK_API_KEY  MOONSHOT_API_KEY  ZHIPU_API_KEY  ARK_API_KEY

Notes:
- StepFun key auth is fine but plan quota is exhausted → SKIP.
- Xiaomi/MiMo URL is a documented placeholder → SKIP.
- Cell 12 in the notebook sets key_env='' (broken path that ignores env);
  this script sets key_env explicitly so Runner.effective_key() works.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ))

from llm_eval.multi_config import MultiRunConfig, RunnerConfig  # noqa: E402
from llm_eval.multi_runner import run_multi  # noqa: E402


# (provider_key_env, base_url, adapter, model, in_price, out_price)
PROVIDERS = [
    ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1",            "deepseek", "deepseek-flash",                0.27, 1.10, "deepseek-flash"),
    ("MOONSHOT_API_KEY", "https://api.moonshot.cn/v1",             "moonshot", "kimi-k3",                      0.10, 0.30, "kimi-k3"),
    ("ZHIPU_API_KEY",    "https://open.bigmodel.cn/api/paas/v4",   "glm",      "glm-5.3",                     0.50, 0.50, "glm-5.3-codeplan"),
    ("ARK_API_KEY",      "https://ark.cn-beijing.volces.com/api/v3", "doubao", "doubao-seed-2-1-pro-260915",    0.80, 1.00, "doubao-2.1-pro"),
]


def _check_env(env_name: str) -> str:
    v = os.environ.get(env_name, "").strip()
    if not v:
        raise SystemExit(f"missing env var {env_name!r}; export it before running")
    return v


def run_one(env_name: str, base_url: str, adapter: str, model: str,
            price_in: float, price_out: float, label: str, tasks_path: str,
            out_root: Path, cap_usd: float) -> dict:
    """Run real provider; copy outputs to <out_root>/<label>/. Return summary entry."""
    _check_env(env_name)
    os.environ[env_name] = os.environ[env_name]  # ensure visible to subprocess if any

    run_id = f"real-{label}"
    tmp_out = out_root / "_tmp" / run_id
    tmp_out.mkdir(parents=True, exist_ok=True)

    cfg = MultiRunConfig(
        run_id=run_id,
        tasks_path=tasks_path,
        runners=[RunnerConfig(
            name=label,
            adapter=adapter,
            model=model,
            key_env=env_name,        # <-- THIS is the fix vs cell 12
            price_in_per_m=price_in,
            price_out_per_m=price_out,
            skip_if_done=False,
        )],
        cap_usd=cap_usd,
        delay_s=0.3,
        out_root=str(out_root / "_tmp"),
    )
    manifest = run_multi(cfg)
    summary_path = tmp_out / label / "summary.json"
    if not summary_path.exists():
        return {"name": label, "status": "no_summary", "manifest": manifest}

    # Copy structured output to canonical real/<label>/ for cell 14 to read
    target = out_root / label
    target.mkdir(parents=True, exist_ok=True)
    for fname in ("results.jsonl", "summary.json", "ledger.jsonl"):
        src = tmp_out / label / fname
        if src.exists():
            shutil.copy(src, target / fname)
    src_raw = tmp_out / label / "raw"
    if src_raw.is_dir():
        shutil.copytree(src_raw, target / "raw", dirs_exist_ok=True)
    return {
        "name": label,
        "status": "ok",
        "target": str(target),
        "n_tasks": manifest.get("n_tasks"),
        "elapsed_s": manifest["runners"][0].get("elapsed_s"),
        "n_ok": manifest["runners"][0].get("n_ok"),
        "n_error": manifest["runners"][0].get("n_error"),
        "n_unattempted": manifest["runners"][0].get("n_unattempted"),
    }


def main() -> int:
    proj = Path(__file__).resolve().parents[1]
    os.chdir(proj)
    tasks_path = str(proj / "tasks" / "public_all.jsonl")
    out_root = proj / "runs" / "notebook-demo" / "real"
    out_root.mkdir(parents=True, exist_ok=True)

    cap_usd = float(os.environ.get("LBEVAL_CAP_USD_REAL", "1.50"))

    results = []
    for env_name, base_url, adapter, model, pi, po, label in PROVIDERS:
        print(f"\n=== {label} ({model})  cap=${cap_usd} ===", flush=True)
        try:
            entry = run_one(env_name, base_url, adapter, model, pi, po, label,
                            tasks_path, out_root, cap_usd)
        except Exception as e:
            entry = {"name": label, "status": "exception", "error": repr(e)[:200]}
        results.append(entry)
        print(f"  → {entry.get('status')}  n_ok={entry.get('n_ok')}  err={entry.get('n_error')}  unat={entry.get('n_unattempted')}", flush=True)

    print("\n=== run summary ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
