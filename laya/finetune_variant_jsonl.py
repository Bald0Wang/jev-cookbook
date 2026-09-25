#!/usr/bin/env python3
"""LoRA-SFT and RLCD-style training for Laya decision JSONL.

The RLCD mode is an explicit small-scale research implementation: it samples
Gaussian perturbations of decision logits, scores probability reports with
Laya's proper scoring rewards, uses a leave-one-out group baseline, and adds a
soft-CE auxiliary objective. It is not claimed to reproduce every upstream
Laya RLCD training detail.
"""

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Laya encoder-LoRA SFT or RLCD-style fine-tuning")
    parser.add_argument("--method", required=True, choices=("lora_sft", "rlcd"))
    parser.add_argument("--data", required=True, help="JSONL with approved train/dev or explicit pilot data")
    parser.add_argument("--model-dir", required=True, help="Laya checkpoint directory, e.g. multilingual")
    parser.add_argument("--output-dir", required=True, help="New persistent experiment directory")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--max-seqs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--rl-samples", type=int, default=4)
    parser.add_argument("--exploration-std", type=float, default=0.5)
    parser.add_argument("--aux-weight", type=float, default=0.1)
    parser.add_argument("--allow-assistant-reviewed-pilot", action="store_true",
                        help="仅允许仓库标记为 assistant_reviewed_pilot 的 112 条流程试验")
    parser.add_argument("--allow-unreviewed-pseudolabels", action="store_true",
                        help="仅供明确的伪标签实验：保留 needs_human_review 状态，不代表人工审核通过")
    args = parser.parse_args()

    if args.epochs < 1 or args.patience < 1 or args.max_tokens < 1 or args.max_seqs < 1:
        parser.error("epochs、patience、max-tokens、max-seqs 都必须为正数")
    if args.method == "rlcd" and args.rl_samples < 2:
        parser.error("RLCD 至少需要 2 个扰动样本以计算组基线")
    if args.exploration_std <= 0 or args.aux_weight < 0:
        parser.error("exploration-std 必须大于 0，aux-weight 不能小于 0")

    # Reuse the same schema checks, data split, and evaluation code as head-only.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from laya.finetune_reviewed_jsonl import compile_records, evaluate, load_reviewed_jsonl

    try:
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        from safetensors.torch import load_file, save_file
        from transformers import AutoTokenizer
    except ImportError as exc:
        parser.error("缺少依赖；安装 transformers、safetensors、peft: %s" % exc)
    if not torch.cuda.is_available():
        parser.error("CUDA 不可用；此脚本拒绝静默回退到 CPU")

    from laya.models import rl_common as common

    try:
        train_records, dev_records = load_reviewed_jsonl(
            args.data,
            allow_assistant_pilot=args.allow_assistant_reviewed_pilot,
            allow_unreviewed_pseudolabels=args.allow_unreviewed_pseudolabels,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    model_dir = Path(args.model_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    if not (model_dir / "model.safetensors").is_file():
        parser.error("模型目录缺少 model.safetensors: %s" % model_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        parser.error("输出目录非空；请使用新的实验目录: %s" % out_dir)

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    device = torch.device("cuda:0")
    amp_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    started = datetime.now(timezone.utc).isoformat()
    start_time = time.time()
    print("Method:", args.method, flush=True)
    print("GPU:", torch.cuda.get_device_name(0), "VRAM GiB:",
          round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2), flush=True)
    print("PyTorch:", torch.__version__, "CUDA:", torch.version.cuda,
          "Transformers:", __import__("transformers").__version__,
          "AMP:", str(amp_dtype), flush=True)

    with (model_dir / "rl_agent_config.json").open(encoding="utf-8") as f:
        cfg = json.load(f)
    tok = AutoTokenizer.from_pretrained(str(model_dir / "tokenizer"))
    train_groups = compile_records(train_records, tok, cfg, common, True, args.seed)
    dev_groups = compile_records(dev_records, tok, cfg, common, False, args.seed)
    print("Records: train=%d / dev=%d; decisions: train=%d / dev=%d" % (
        len(train_groups), len(dev_groups), sum(map(len, train_groups)), sum(map(len, dev_groups))), flush=True)

    model = common.build_model(cfg, encoder_dir=str(model_dir / "encoder"))
    weights = load_file(str(model_dir / "model.safetensors"), device="cpu")
    model.load_state_dict(weights, strict=True)
    del weights

    if args.method == "lora_sft":
        lora = LoraConfig(
            task_type=TaskType.FEATURE_EXTRACTION,
            r=args.lora_rank,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            target_modules=["Wqkv", "attn.Wo"],
            bias="none",
        )
        model.encoder = get_peft_model(model.encoder, lora)
        for name, parameter in model.named_parameters():
            if not name.startswith("encoder."):
                parameter.requires_grad_(not name.startswith("act_head."))
        lr = args.lr if args.lr is not None else 5e-5
        train_scope = "ModernBERT LoRA (Wqkv and attention Wo) + decision head; act_head frozen"
    else:
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(not name.startswith("act_head."))
        if hasattr(model.encoder, "gradient_checkpointing_enable"):
            try:
                model.encoder.gradient_checkpointing_enable(
                    gradient_checkpointing_kwargs={"use_reentrant": False})
            except TypeError:
                model.encoder.gradient_checkpointing_enable()
        lr = args.lr if args.lr is not None else 2e-5
        train_scope = "full encoder + decision head; act_head frozen"

    model.to(device)
    model.head_checkpointing = True
    model.train()
    model.act_head.eval()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    if not trainable:
        raise RuntimeError("没有可训练参数")
    print("Trainable parameters:", trainable, "/", total, flush=True)

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01, foreach=False)
    dev_before = evaluate(model, dev_groups, tok.pad_token_id, device, torch, common,
                          args.max_tokens, args.max_seqs)
    print("Dev before:", json.dumps(dev_before, ensure_ascii=False), flush=True)
    torch.cuda.reset_peak_memory_stats()

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "training_log.csv"
    jsonl_path = out_dir / "training_log.jsonl"
    fields = ["epoch", "train_loss", "train_ce", "train_reward", "dev_soft_cross_entropy",
              "dev_accuracy", "best_epoch", "elapsed_seconds"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"epoch": 0, "dev_soft_cross_entropy": dev_before["soft_cross_entropy"],
                         "dev_accuracy": dev_before["argmax_accuracy"], "best_epoch": 0,
                         "elapsed_seconds": 0})
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"event": "baseline", "dev": dev_before}, ensure_ascii=False) + "\n")

    best_loss = float("inf")
    best_state = None
    best_epoch = 0
    stale_epochs = 0
    history = []
    for epoch in range(args.epochs):
        epoch_groups = compile_records(train_records, tok, cfg, common, True, args.seed + epoch + 1)
        random.Random(args.seed + epoch).shuffle(epoch_groups)
        batches = common.pack_groups(epoch_groups, max_tokens=args.max_tokens, max_seqs=args.max_seqs)
        model.train()
        if model.act_head is not None:
            model.act_head.eval()
        loss_sum = ce_sum = reward_sum = 0.0
        n_questions = n_reward_batches = 0
        for group_batch in batches:
            batch = common.collate_items(group_batch, tok.pad_token_id)
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            marker_pos = batch["marker_pos"].to(device)
            marker_mask = batch["marker_mask"].to(device)
            targets = batch["target"].to(device)
            qtype = batch["qtype"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=amp_dtype):
                logits, _ = model(input_ids, attention_mask, marker_pos, marker_mask, qtype)
            logits = logits.float().masked_fill(~marker_mask, -1e4)
            ce = -(targets * torch.log_softmax(logits, -1)).sum(-1).mean()
            if args.method == "lora_sft":
                loss = ce
            else:
                sigma = args.exploration_std
                valid = marker_mask.unsqueeze(0)
                noise = torch.randn((args.rl_samples, *logits.shape), device=device) * sigma
                noise = noise.masked_fill(~valid, 0.0)
                mean_logits = logits.unsqueeze(0)
                sampled_logits = mean_logits.detach() + noise
                sampled_probs = torch.softmax(sampled_logits.masked_fill(~valid, -1e4), dim=-1)
                rewards = common.proper_reward(
                    sampled_probs, targets, qtype, marker_mask,
                    w_sph=0.5, w_rps=1.0)
                baseline = (rewards.sum(0, keepdim=True) - rewards) / (args.rl_samples - 1)
                advantage = (rewards - baseline).detach()
                scale = rewards.std(0, unbiased=False, keepdim=True).clamp_min(1e-3)
                advantage = (advantage / scale).clamp(-5.0, 5.0)
                log_prob = -0.5 * (((sampled_logits - mean_logits) / sigma).square())
                log_prob = log_prob.masked_fill(~valid, 0.0).sum(-1)
                policy_loss = -(advantage * log_prob).mean()
                loss = policy_loss + args.aux_weight * ce
                reward_sum += float(rewards.mean().item()) * len(batch["label"])
                n_reward_batches += len(batch["label"])
            if not torch.isfinite(loss):
                raise RuntimeError("训练 loss 出现 NaN/Inf")
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            optimizer.step()
            count = len(batch["label"])
            loss_sum += float(loss.detach().item()) * count
            ce_sum += float(ce.detach().item()) * count
            n_questions += count

        dev_metrics = evaluate(model, dev_groups, tok.pad_token_id, device, torch, common,
                               args.max_tokens, args.max_seqs)
        row = {
            "epoch": epoch + 1,
            "train_loss": loss_sum / max(1, n_questions),
            "train_ce": ce_sum / max(1, n_questions),
            "train_reward": reward_sum / max(1, n_reward_batches) if args.method == "rlcd" else "",
            "dev": dev_metrics,
        }
        history.append(row)
        print("Epoch %d: loss=%.5f ce=%.5f reward=%s dev=%s" % (
            epoch + 1, row["train_loss"], row["train_ce"], row["train_reward"],
            json.dumps(dev_metrics, ensure_ascii=False)), flush=True)
        improved = dev_metrics["soft_cross_entropy"] < best_loss
        if improved:
            best_loss = dev_metrics["soft_cross_entropy"]
            best_epoch = epoch + 1
            stale_epochs = 0
            best_state = {k: v.detach().half().contiguous().cpu() for k, v in model.state_dict().items()}
        else:
            stale_epochs += 1
        row_csv = {k: row.get(k, "") for k in fields}
        row_csv.update({"dev_soft_cross_entropy": dev_metrics["soft_cross_entropy"],
                        "dev_accuracy": dev_metrics["argmax_accuracy"], "best_epoch": best_epoch,
                        "elapsed_seconds": round(time.time() - start_time, 2)})
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=fields).writerow(row_csv)
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "epoch", **row}, ensure_ascii=False) + "\n")
        if stale_epochs >= args.patience:
            break

    if best_state is None:
        raise RuntimeError("没有获得有效的 dev checkpoint")
    model.load_state_dict(best_state, strict=True)
    if args.method == "lora_sft":
        model.encoder = model.encoder.merge_and_unload()
    final_state = {k: v.detach().half().contiguous().cpu() for k, v in model.state_dict().items()}
    save_file(final_state, str(out_dir / "model.safetensors"))
    model.encoder.config.save_pretrained(str(out_dir / "encoder"))
    tok.save_pretrained(str(out_dir / "tokenizer"))
    cfg["fine_tuned"] = True
    cfg["model_name"] = "laya-%s-pilot" % args.method
    cfg["experiment_note"] = (
        "LoRA supervised fine-tuning; pilot-only, not calibrated."
        if args.method == "lora_sft" else
        "RLCD-style Gaussian logit exploration + proper-score reward + leave-one-out baseline and CE auxiliary; pilot-only."
    )
    with (out_dir / "rl_agent_config.json").open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    dev_after = evaluate(model, dev_groups, tok.pad_token_id, device, torch, common,
                         args.max_tokens, args.max_seqs)
    report = {
        "started_at_utc": started,
        "method": args.method,
        "data_sha256": file_sha256(args.data),
        "base_model_sha256": file_sha256(model_dir / "model.safetensors"),
        "tuned_model_sha256": file_sha256(out_dir / "model.safetensors"),
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "transformers": __import__("transformers").__version__,
        "peft": __import__("peft").__version__,
        "safetensors": __import__("safetensors").__version__,
        "train_groups": len(train_groups),
        "dev_groups": len(dev_groups),
        "train_questions": sum(map(len, train_groups)),
        "dev_questions": sum(map(len, dev_groups)),
        "review_status_counts": dict(Counter((r.get("metadata") or {}).get("review_status", "missing")
                                              for r in train_records + dev_records)),
        "epochs_requested": args.epochs,
        "epochs_run": len(history),
        "best_epoch": best_epoch,
        "training_config": {
            "seed": args.seed,
            "learning_rate": lr,
            "patience": args.patience,
            "max_tokens": args.max_tokens,
            "max_seqs": args.max_seqs,
            "autocast_dtype": str(amp_dtype),
            "optimizer": "AdamW",
            "weight_decay": 0.01,
            "train_scope": train_scope,
            "rl_samples": args.rl_samples if args.method == "rlcd" else None,
            "exploration_std": args.exploration_std if args.method == "rlcd" else None,
            "aux_weight": args.aux_weight if args.method == "rlcd" else None,
            "lora_rank": args.lora_rank if args.method == "lora_sft" else None,
            "lora_alpha": args.lora_alpha if args.method == "lora_sft" else None,
            "lora_dropout": args.lora_dropout if args.method == "lora_sft" else None,
            "selection_metric": "dev_soft_cross_entropy",
            "allow_assistant_reviewed_pilot": args.allow_assistant_reviewed_pilot,
            "allow_unreviewed_pseudolabels": args.allow_unreviewed_pseudolabels,
        },
        "trainable_parameters": trainable,
        "total_parameters": total,
        "gpu": torch.cuda.get_device_name(0),
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
        "training_seconds": round(time.time() - start_time, 2),
        "dev_before": dev_before,
        "dev_after": dev_after,
        "history": history,
        "calibrated": False,
        "note": "112 条 assistant-reviewed 合成 pilot 仅用于验证训练链路；不代表真实业务泛化，也不能用于证明概率校准。",
    }
    with (out_dir / "experiment.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Saved:", out_dir, flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
