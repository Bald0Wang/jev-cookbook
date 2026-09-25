#!/usr/bin/env python3
"""GPU head-only fine-tuning for reviewed Laya JSONL records.

This is a small domain-adaptation baseline, not the upstream RLCD trainer.
It refuses generated candidates until their metadata says human review passed.
"""

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


APPROVED_REVIEW_STATES = {"approved", "human_reviewed", "accepted"}


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_reviewed_jsonl(path, allow_assistant_pilot=False, allow_unreviewed_pseudolabels=False):
    records = []
    group_splits = {}
    ids = set()
    with open(path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("第 %d 行 JSON 无效: %s" % (line_number, exc))
            if not isinstance(record, dict):
                raise ValueError("第 %d 行必须是 JSON 对象" % line_number)
            if record.get("split") not in ("train", "dev"):
                raise ValueError("第 %d 行 split 必须是审核后设置的 train 或 dev" % line_number)
            metadata = record.get("metadata") or {}
            if not isinstance(metadata, dict):
                raise ValueError("第 %d 行 metadata 必须是对象" % line_number)
            review_status = metadata.get("review_status")
            allowed_states = APPROVED_REVIEW_STATES | ({"assistant_reviewed_pilot"} if allow_assistant_pilot else set())
            pseudo_sources = {"deepseek_pseudo_label", "deepseek_flash_independent_vote_proxy"}
            explicit_pseudo_candidate = (
                allow_unreviewed_pseudolabels
                and review_status == "needs_human_review"
                and metadata.get("label_source") in pseudo_sources
            )
            if review_status not in allowed_states and not explicit_pseudo_candidate:
                raise ValueError("第 %d 行尚未通过人工审核" % line_number)
            if (metadata.get("label_source") in pseudo_sources and not metadata.get("reviewer")
                    and not allow_unreviewed_pseudolabels):
                raise ValueError("第 %d 行是 DeepSeek 伪标签，请记录 reviewer 后再训练" % line_number)
            rid, group_id = record.get("id"), record.get("source_group_id")
            if not isinstance(rid, str) or not rid or rid in ids:
                raise ValueError("第 %d 行 id 缺失或重复" % line_number)
            if not isinstance(group_id, str) or not group_id:
                raise ValueError("第 %d 行缺少 source_group_id" % line_number)
            ids.add(rid)
            split = record["split"]
            previous = group_splits.setdefault(group_id, split)
            if previous != split:
                raise ValueError("source_group_id %s 跨 train/dev 泄漏" % group_id)
            if not isinstance(record.get("state"), (str, dict)) or not record.get("state"):
                raise ValueError("第 %d 行 state 为空或格式错误" % line_number)
            if not isinstance(record.get("qs"), list) or not record["qs"]:
                raise ValueError("第 %d 行 qs 必须是非空数组" % line_number)
            records.append(record)

    train = [r for r in records if r["split"] == "train"]
    dev = [r for r in records if r["split"] == "dev"]
    if not train or not dev:
        raise ValueError("数据必须同时包含非空 train 和 dev；dev 应是独立人工审核数据")
    return train, dev


def compile_records(records, tok, cfg, common, train_mode, seed):
    rng = random.Random(seed) if train_mode else None
    groups = []
    for record in records:
        group = common.encode_record(record, tok, cfg, rng=rng, train=train_mode)
        if group:
            groups.append(group)
    if not groups:
        raise ValueError("记录无法编译成模型输入；请检查 y/soft、题型、候选和长度")
    return groups


def evaluate(model, groups, pad_id, device, torch, common, max_tokens, max_seqs):
    model.eval()
    loss_total = 0.0
    correct = 0
    count = 0
    qtype_counts = Counter()
    qtype_correct = Counter()
    batches = common.pack_groups(groups, max_tokens=max_tokens, max_seqs=max_seqs)
    with torch.inference_mode():
        for group_batch in batches:
            batch = common.collate_items(group_batch, pad_id)
            with torch.autocast("cuda", dtype=torch.float16):
                logits, _ = model(
                    batch["input_ids"].to(device),
                    batch["attention_mask"].to(device),
                    batch["marker_pos"].to(device),
                    batch["marker_mask"].to(device),
                    batch["qtype"].to(device),
                )
            mask = batch["marker_mask"].to(device)
            targets = batch["target"].to(device)
            labels = batch["label"].to(device)
            predicted = logits.float().masked_fill(~mask, -1e4).argmax(-1)
            per_loss = -(targets * torch.log_softmax(logits.float().masked_fill(~mask, -1e4), -1)).sum(-1)
            qtypes = batch["qtype"].tolist()
            matches = predicted.eq(labels).tolist()
            loss_total += float(per_loss.sum().item())
            correct += sum(matches)
            count += len(matches)
            for qtype, matched in zip(qtypes, matches):
                name = common.QTYPE_NAMES[qtype]
                qtype_counts[name] += 1
                qtype_correct[name] += int(matched)
    model.train()
    model.encoder.eval()
    if model.act_head is not None:
        model.act_head.eval()
    return {
        "soft_cross_entropy": loss_total / max(1, count),
        "argmax_accuracy": correct / max(1, count),
        "questions": count,
        "by_qtype_accuracy": {
            name: qtype_correct[name] / n for name, n in sorted(qtype_counts.items())
        },
    }


def main():
    parser = argparse.ArgumentParser(description="在已审核的 Laya JSONL 上做 CUDA head-only 微调")
    parser.add_argument("--data", required=True, help="含 train/dev 的审核后 JSONL")
    parser.add_argument("--model-dir", default="laya/models/multilingual")
    parser.add_argument("--output-dir", required=True, help="新目录；不会覆盖基座权重")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--head-lr", type=float, default=1e-4)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-seqs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--allow-assistant-reviewed-pilot", action="store_true",
                        help="允许明确标记为 assistant_reviewed_pilot 的小型实验数据；不能作为人工 gold")
    parser.add_argument("--allow-unreviewed-pseudolabels", action="store_true",
                        help="仅供明确的伪标签实验：保留 needs_human_review 状态，不代表人工审核通过")
    args = parser.parse_args()

    if args.epochs < 1 or args.patience < 1 or args.max_tokens < 1 or args.max_seqs < 1:
        parser.error("epochs、patience、max-tokens、max-seqs 都必须为正数")
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

    try:
        import torch
        from safetensors.torch import load_file, save_file
        from transformers import AutoTokenizer
    except ImportError as exc:
        parser.error("缺少训练依赖，请先安装 laya/requirements.txt: %s" % exc)
    if not torch.cuda.is_available():
        parser.error("CUDA 不可用；此脚本拒绝静默回退到 CPU")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from laya.models import rl_common as common

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    device = torch.device("cuda:0")
    started = datetime.now(timezone.utc).isoformat()
    print("GPU:", torch.cuda.get_device_name(0))
    print("PyTorch:", torch.__version__, "CUDA:", torch.version.cuda)

    cfg_path = model_dir / "rl_agent_config.json"
    with cfg_path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    tok = AutoTokenizer.from_pretrained(str(model_dir / "tokenizer"))
    train_groups = compile_records(train_records, tok, cfg, common, True, args.seed)
    dev_groups = compile_records(dev_records, tok, cfg, common, False, args.seed)
    print("审定数据：train=%d 组 / %d 题；dev=%d 组 / %d 题" % (
        len(train_groups), sum(map(len, train_groups)), len(dev_groups), sum(map(len, dev_groups))))

    model = common.build_model(cfg, encoder_dir=str(model_dir / "encoder"))
    weights = load_file(str(model_dir / "model.safetensors"), device="cpu")
    model.load_state_dict(weights, strict=True)
    del weights
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(not name.startswith("encoder.") and not name.startswith("act_head."))
    model.to(device)
    model.head_checkpointing = True
    model.train()
    model.encoder.eval()
    model.act_head.eval()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.head_lr,
        weight_decay=0.01,
        foreach=False,
    )
    dev_before = evaluate(model, dev_groups, tok.pad_token_id, device, torch, common,
                          args.max_tokens, args.max_seqs)
    print("Dev before:", json.dumps(dev_before, ensure_ascii=False))
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "training_log.csv"
    jsonl_path = out_dir / "training_log.jsonl"
    csv_fields = [
        "epoch", "train_loss", "dev_soft_cross_entropy", "dev_accuracy",
        "dev_choice_accuracy", "dev_noul_accuracy", "dev_score_accuracy",
        "best_epoch", "elapsed_seconds",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerow({
            "epoch": 0, "train_loss": "", "dev_soft_cross_entropy": dev_before["soft_cross_entropy"],
            "dev_accuracy": dev_before["argmax_accuracy"],
            "dev_choice_accuracy": dev_before["by_qtype_accuracy"].get("choice", ""),
            "dev_noul_accuracy": dev_before["by_qtype_accuracy"].get("noul", ""),
            "dev_score_accuracy": dev_before["by_qtype_accuracy"].get("score", ""),
            "best_epoch": 0, "elapsed_seconds": 0,
        })
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as jsonl_file:
        jsonl_file.write(json.dumps({"event": "baseline", "epoch": 0, "dev": dev_before}, ensure_ascii=False) + "\n")

    best_loss = float("inf")
    best_epoch = 0
    stale_epochs = 0
    best_state = None
    epochs_run = 0
    epoch_history = []
    start_time = time.time()
    for epoch in range(args.epochs):
        epoch_groups = compile_records(train_records, tok, cfg, common, True, args.seed + epoch + 1)
        random.Random(args.seed + epoch).shuffle(epoch_groups)
        batches = common.pack_groups(epoch_groups, max_tokens=args.max_tokens, max_seqs=args.max_seqs)
        model.train()
        model.encoder.eval()
        model.act_head.eval()
        loss_sum = 0.0
        n_questions = 0
        for group_batch in batches:
            batch = common.collate_items(group_batch, tok.pad_token_id)
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            marker_pos = batch["marker_pos"].to(device)
            marker_mask = batch["marker_mask"].to(device)
            target = batch["target"].to(device)
            qtype = batch["qtype"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.float16):
                logits, _ = model(input_ids, attention_mask, marker_pos, marker_mask, qtype)
            logits = logits.float().masked_fill(~marker_mask, -1e4)
            loss = -(target * torch.log_softmax(logits, -1)).sum(-1).mean()
            if not torch.isfinite(loss):
                raise RuntimeError("训练 loss 出现 NaN/Inf")
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            optimizer.step()
            loss_sum += float(loss.detach().item()) * len(batch["label"])
            n_questions += len(batch["label"])

        dev_metrics = evaluate(model, dev_groups, tok.pad_token_id, device, torch, common,
                               args.max_tokens, args.max_seqs)
        epochs_run = epoch + 1
        train_loss = loss_sum / max(1, n_questions)
        epoch_info = {"epoch": epochs_run, "train_loss": train_loss, "dev": dev_metrics}
        epoch_history.append(epoch_info)
        print("Epoch %d: train_loss=%.6f dev=%s" % (
            epochs_run, train_loss, json.dumps(dev_metrics, ensure_ascii=False)))
        improved = dev_metrics["soft_cross_entropy"] < best_loss
        if improved:
            best_loss = dev_metrics["soft_cross_entropy"]
            best_epoch = epochs_run
            stale_epochs = 0
            best_state = {k: v.detach().half().contiguous().cpu() for k, v in model.state_dict().items()}
            should_stop = False
        else:
            stale_epochs += 1
            should_stop = stale_epochs >= args.patience
        log_by_qtype = dev_metrics["by_qtype_accuracy"]
        log_row = {
            "epoch": epochs_run,
            "train_loss": train_loss,
            "dev_soft_cross_entropy": dev_metrics["soft_cross_entropy"],
            "dev_accuracy": dev_metrics["argmax_accuracy"],
            "dev_choice_accuracy": log_by_qtype.get("choice", ""),
            "dev_noul_accuracy": log_by_qtype.get("noul", ""),
            "dev_score_accuracy": log_by_qtype.get("score", ""),
            "best_epoch": best_epoch,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }
        with csv_path.open("a", encoding="utf-8", newline="") as csv_file:
            csv.DictWriter(csv_file, fieldnames=csv_fields).writerow(log_row)
        with jsonl_path.open("a", encoding="utf-8", newline="\n") as jsonl_file:
            jsonl_file.write(json.dumps({"event": "epoch", **epoch_info}, ensure_ascii=False) + "\n")
        if should_stop:
            break

    if best_state is None:
        raise RuntimeError("没有获得有效的 dev checkpoint")
    model.load_state_dict(best_state, strict=True)
    dev_after = evaluate(model, dev_groups, tok.pad_token_id, device, torch, common,
                         args.max_tokens, args.max_seqs)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_file(best_state, str(out_dir / "model.safetensors"))
    model.encoder.config.save_pretrained(str(out_dir / "encoder"))
    tok.save_pretrained(str(out_dir / "tokenizer"))
    cfg["fine_tuned"] = True
    cfg["model_name"] = "laya-reviewed-zh-head-tuned"
    cfg["experiment_note"] = "Reviewed Chinese JSONL, CUDA head-only supervised fine-tuning; not calibrated."
    with (out_dir / "rl_agent_config.json").open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    report = {
        "started_at_utc": started,
        "data_sha256": file_sha256(args.data),
        "base_model_sha256": file_sha256(model_dir / "model.safetensors"),
        "tuned_model_sha256": file_sha256(out_dir / "model.safetensors"),
        "python": sys.version.split()[0],
        "transformers": __import__("transformers").__version__,
        "safetensors": __import__("safetensors").__version__,
        "numpy": __import__("numpy").__version__,
        "training_log_csv": str(csv_path),
        "training_log_jsonl": str(jsonl_path),
        "train_groups": len(train_records),
        "dev_groups": len(dev_records),
        "review_status_counts": dict(Counter(
            (r.get("metadata") or {}).get("review_status", "missing")
            for r in train_records + dev_records
        )),
        "train_questions": sum(map(len, train_groups)),
        "dev_questions": sum(map(len, dev_groups)),
        "epochs_requested": args.epochs,
        "epochs_run": epochs_run,
        "best_epoch": best_epoch,
        "training_config": {
            "seed": args.seed,
            "patience": args.patience,
            "head_lr": args.head_lr,
            "max_tokens": args.max_tokens,
            "max_seqs": args.max_seqs,
            "loss": "soft_cross_entropy",
            "optimizer": "AdamW",
            "weight_decay": 0.01,
            "autocast_dtype": "float16",
            "selection_metric": "dev_soft_cross_entropy",
            "train_scope": "decision head; encoder and act_head frozen",
            "allow_assistant_reviewed_pilot": args.allow_assistant_reviewed_pilot,
            "allow_unreviewed_pseudolabels": args.allow_unreviewed_pseudolabels,
        },
        "trainable_parameters": trainable,
        "total_parameters": total,
        "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 1024 ** 3, 3),
        "training_seconds": round(time.time() - start_time, 2),
        "dev_before": dev_before,
        "dev_after": dev_after,
        "history": epoch_history,
        "calibrated": False,
        "note": "Head-only supervised baseline. This small generated-data dev split is from the same task specification, not an OOD or production-quality estimate.",
    }
    with (out_dir / "experiment.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Saved:", out_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
