#!/usr/bin/env python3
"""Evaluate candidate-derived calibration/test splits for saved Laya checkpoints."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_records(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("评估数据为空: %s" % path)
    return rows


def main():
    parser = argparse.ArgumentParser(description="在 calibration/test split 上评估多个 Laya checkpoint")
    parser.add_argument("--split-dir", required=True, help="prepare_candidate_splits.py 的输出目录")
    parser.add_argument("--run-root", required=True, help="包含 head-only/lora-sft/rlcd 子目录的实验目录")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--max-seqs", type=int, default=4)
    parser.add_argument("--allow-unreviewed-pseudolabels", action="store_true",
                        help="明确允许使用 DeepSeek 伪标签评估；不会改变 review_status")
    args = parser.parse_args()
    if not args.allow_unreviewed_pseudolabels:
        parser.error("候选数据仍需审核；若本次仅评估伪标签，请显式启用 --allow-unreviewed-pseudolabels")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from laya.finetune_reviewed_jsonl import compile_records
    try:
        import torch
        from safetensors.torch import load_file
        from transformers import AutoTokenizer
    except ImportError as exc:
        parser.error("缺少训练依赖: %s" % exc)
    if not torch.cuda.is_available():
        parser.error("CUDA 不可用")
    from laya.models import rl_common as common

    split_dir, run_root = Path(args.split_dir), Path(args.run_root)
    split_rows = {name: read_records(split_dir / (name + ".jsonl")) for name in ("calibration", "test")}
    for name, rows in split_rows.items():
        if any((r.get("metadata") or {}).get("review_status") != "needs_human_review" for r in rows):
            raise SystemExit("%s split 的 review_status 与候选集不符" % name)
    results = {"split_manifest_sha256": sha256(split_dir / "manifest.json"), "models": {}}
    model_names = ("head-only", "lora-sft", "rlcd")
    for model_name in model_names:
        model_dir = run_root / model_name
        if not (model_dir / "model.safetensors").is_file():
            raise SystemExit("checkpoint 不完整: %s" % model_dir)
        with (model_dir / "rl_agent_config.json").open(encoding="utf-8") as f:
            cfg = json.load(f)
        tok = AutoTokenizer.from_pretrained(str(model_dir / "tokenizer"))
        model = common.build_model(cfg, encoder_dir=str(model_dir / "encoder"))
        model.load_state_dict(load_file(str(model_dir / "model.safetensors"), device="cpu"), strict=True)
        model.to("cuda").eval()
        model_result = {"checkpoint_sha256": sha256(model_dir / "model.safetensors"), "splits": {}}
        for split_name, rows in split_rows.items():
            groups = compile_records(rows, tok, cfg, common, False, 42)
            metric = common
            from laya.finetune_reviewed_jsonl import evaluate
            model_result["splits"][split_name] = evaluate(
                model, groups, tok.pad_token_id, torch.device("cuda"), torch, metric,
                args.max_tokens, args.max_seqs)
            model.eval()
            print(model_name, split_name, json.dumps(model_result["splits"][split_name], ensure_ascii=False), flush=True)
        results["models"][model_name] = model_result
        del model, tok
        torch.cuda.empty_cache()

    results["note"] = "Labels are unreviewed DeepSeek vote proxies; these are pseudo-label metrics, not human-gold test results or calibration claims."
    output = run_root / "holdout_metrics.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved:", output)


if __name__ == "__main__":
    main()
