"""Single-provider real runner (parallel-friendly)."""
from __future__ import annotations
import json, os, shutil, sys, time
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ))

from llm_eval.multi_config import MultiRunConfig, RunnerConfig
from llm_eval.multi_runner import run_multi


# args: 1=env_name  2=base_url  3=adapter  4=model  5=price_in  6=price_out  7=label
def main():
    args = sys.argv[1:]
    env_name, base_url, adapter, model, pi_s, po_s, label = args
    pi, po = float(pi_s), float(po_s)
    tasks_path = str(PROJ / "tasks" / "public_all.jsonl")
    out_root = PROJ / "runs" / "notebook-demo" / "real"
    cap_usd = float(os.environ.get("LBEVAL_CAP_USD_REAL", "1.50"))

    os.environ[env_name] = os.environ[env_name]  # propagate

    # Provider-specific request_options overrides
    request_options = None
    if label == "kimi-k3":
        # kimi-k3 only accepts temperature=1
        request_options = {"temperature": 1}

    run_id = f"cell12-{label}"
    tmp_out = out_root / "_tmp" / run_id
    tmp_out.mkdir(parents=True, exist_ok=True)

    cfg = MultiRunConfig(
        run_id=run_id,
        tasks_path=tasks_path,
        runners=[RunnerConfig(
            name=label, adapter=adapter, model=model,
            key_env=env_name,
            price_in_per_m=pi, price_out_per_m=po,
            skip_if_done=False,
        )],
        cap_usd=cap_usd,
        delay_s=0.3,
        out_root=str(out_root / "_tmp"),
        request_options=request_options,
    )
    print(f"[{label}] starting at {time.strftime('%H:%M:%S')}", flush=True)
    manifest = run_multi(cfg)
    print(f"[{label}] manifest: {manifest.get('runners')[0]}", flush=True)

    # multi_runner slugifies runner.name (dots → underscores); use the manifest dir directly
    runner_dir = Path(manifest["runners"][0]["dir"])
    summary_path = runner_dir / "summary.json"
    if not summary_path.exists():
        print(f"[{label}] no summary at {summary_path}", flush=True)
        return 1

    target = out_root / label
    target.mkdir(parents=True, exist_ok=True)
    for fname in ("results.jsonl", "summary.json", "ledger.jsonl"):
        src = runner_dir / fname
        if src.exists():
            shutil.copy(src, target / fname)
    src_raw = runner_dir / "raw"
    if src_raw.is_dir():
        shutil.copytree(src_raw, target / "raw", dirs_exist_ok=True)
    print(f"[{label}] done at {time.strftime('%H:%M:%S')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
