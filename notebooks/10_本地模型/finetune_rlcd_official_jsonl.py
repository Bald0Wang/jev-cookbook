#!/usr/bin/env python3
"""Run Laya's upstream RLCD recipe on the local conversation-decision JSONL.

This adapts the official typed-decisions notebook's full-encoder policy-gradient
recipe to the repository's source-grouped JSONL and fixed train/dev/calibration/
test split. The data remains marked as unreviewed pseudo-labels.
"""

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("qs"), list):
                raise ValueError("第 %d 行不是有效的对话决策记录" % line_number)
            metadata = row.get("metadata") or {}
            if metadata.get("review_status") != "needs_human_review":
                raise ValueError("第 %d 行审核状态不符合预期" % line_number)
            if metadata.get("label_source") not in {
                "deepseek_pseudo_label", "deepseek_flash_independent_vote_proxy"
            }:
                raise ValueError("第 %d 行不是预期的 DeepSeek 伪标签来源" % line_number)
            if not row.get("source_group_id"):
                raise ValueError("第 %d 行缺少 source_group_id" % line_number)
            rows.append(row)
    return rows


def expected_split(rows, name):
    wrong = [row for row in rows if row.get("split") != name]
    if wrong:
        raise ValueError("%s 文件包含错误 split 标记" % name)


def fit_temperature(samples, torch):
    if len(samples) < 10:
        return 1.0
    kmax = max(len(logits) for logits, _ in samples)
    z = torch.full((len(samples), kmax), -1e4, dtype=torch.float32)
    target = torch.zeros_like(z)
    for index, (logits, target_row) in enumerate(samples):
        z[index, :len(logits)] = torch.tensor(logits, dtype=torch.float32)
        target[index, :len(target_row)] = torch.tensor(target_row, dtype=torch.float32)
    log_temperature = torch.zeros(1, requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.1, max_iter=100)

    def closure():
        optimizer.zero_grad()
        loss = -(target * torch.log_softmax(z / log_temperature.exp(), dim=-1)).sum(-1).mean()
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(torch.clamp(log_temperature.exp(), 0.1, 10.0).item())


def ece_score(confidences, correct, bins=15):
    if not confidences:
        return float("nan")
    conf = np.asarray(confidences, dtype=np.float64)
    corr = np.asarray(correct, dtype=np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        selected = (conf > low) & (conf <= high)
        if selected.any():
            error += float(selected.mean()) * abs(float(conf[selected].mean()) - float(corr[selected].mean()))
    return error


def evaluate(model, groups, tokenizer, common, torch, device, amp_dtype,
             max_tokens, max_seqs, temperatures=None, collect=False):
    model.eval()
    temperatures = temperatures or [1.0, 1.0, 1.0]
    totals = {"n": 0, "nll": 0.0, "brier": 0.0, "correct": 0,
              "conf": [], "matches": []}
    per_type = {}
    calibration_samples = {0: [], 1: [], 2: []}
    batches = common.pack_groups(groups, max_tokens=max_tokens, max_seqs=max_seqs)
    with torch.inference_mode():
        for group_batch in batches:
            batch = common.collate_items(group_batch, tokenizer.pad_token_id)
            with torch.autocast("cuda", dtype=amp_dtype):
                logits, _ = model(
                    batch["input_ids"].to(device),
                    batch["attention_mask"].to(device),
                    batch["marker_pos"].to(device),
                    batch["marker_mask"].to(device),
                    batch["qtype"].to(device),
                )
            logits = logits.float()
            mask = batch["marker_mask"].to(device)
            target = batch["target"].to(device)
            qtype = batch["qtype"].to(device)
            labels = batch["label"].to(device)
            scale = torch.tensor(temperatures, dtype=logits.dtype, device=device)[qtype].unsqueeze(-1)
            scaled_logits = logits.masked_fill(~mask, -1e4) / scale
            log_probs = torch.log_softmax(scaled_logits, dim=-1)
            probs = log_probs.exp()
            prediction = probs.argmax(-1)
            confidence = probs.max(-1).values
            correct = prediction.eq(labels)
            nll = -(target * log_probs).sum(-1)
            brier = ((probs - target) ** 2).sum(-1)
            totals["n"] += int(len(labels))
            totals["nll"] += float(nll.sum().item())
            totals["brier"] += float(brier.sum().item())
            totals["correct"] += int(correct.sum().item())
            totals["conf"] += confidence.detach().cpu().tolist()
            totals["matches"] += correct.detach().cpu().to(torch.int32).tolist()
            for qtype_id, logit_row, target_row, valid_row in zip(
                qtype.detach().cpu().tolist(), logits.detach().cpu(),
                target.detach().cpu(), mask.detach().cpu()
            ):
                k = int(valid_row.sum().item())
                if collect:
                    calibration_samples[qtype_id].append((
                        logit_row[:k].tolist(), target_row[:k].tolist()
                    ))
            for qtype_id in range(3):
                selected = qtype.eq(qtype_id)
                if not selected.any():
                    continue
                name = common.QTYPE_NAMES[qtype_id]
                item = per_type.setdefault(name, {
                    "n": 0, "nll": 0.0, "brier": 0.0, "correct": 0,
                    "conf": [], "matches": [],
                })
                item["n"] += int(selected.sum().item())
                item["nll"] += float(nll[selected].sum().item())
                item["brier"] += float(brier[selected].sum().item())
                item["correct"] += int(correct[selected].sum().item())
                item["conf"].extend(confidence[selected].detach().cpu().tolist())
                item["matches"].extend(correct[selected].detach().cpu().to(torch.int32).tolist())
    n = max(1, totals["n"])
    result = {
        "questions": int(totals["n"]),
        "soft_cross_entropy": totals["nll"] / n,
        "argmax_accuracy": totals["correct"] / n,
        "brier_score": totals["brier"] / n,
        "ece_top_label": ece_score(totals["conf"], totals["matches"]),
        "by_qtype": {},
    }
    for name, item in per_type.items():
        count = max(1, item["n"])
        result["by_qtype"][name] = {
            "questions": int(item["n"]),
            "soft_cross_entropy": item["nll"] / count,
            "argmax_accuracy": item["correct"] / count,
            "brier_score": item["brier"] / count,
            "ece_top_label": ece_score(item["conf"], item["matches"]),
        }
    model.train()
    model.encoder.eval()
    if model.act_head is not None:
        model.act_head.eval()
    return result, calibration_samples


def save_model_weights(model, destination, save_file, torch):
    state = {name: value.detach().half().contiguous().cpu()
             for name, value in model.state_dict().items()}
    save_file(state, str(destination))
    del state


def main():
    parser = argparse.ArgumentParser(description="Laya upstream-style RLCD recipe for local JSONL")
    parser.add_argument("--train-dev", required=True)
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--patience", type=int, default=4,
                        help="不提前停止时可设为等于 epochs；dev 仍按最佳 CE 选 checkpoint")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-seqs", type=int, default=8)
    parser.add_argument("--grad-accum", type=int, default=16,
                        help="单卡适配：按预编译批次大小匹配官方 DDP 的约 64 决策项有效 batch")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rl-samples", type=int, default=4)
    parser.add_argument("--sigma-start", type=float, default=0.4)
    parser.add_argument("--sigma-end", type=float, default=0.1)
    parser.add_argument("--w-sph", type=float, default=0.75)
    parser.add_argument("--w-rps", type=float, default=1.0)
    parser.add_argument("--ce-weight", type=float, default=1.0)
    parser.add_argument("--lr-encoder", type=float, default=2.5e-5)
    parser.add_argument("--lr-head", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-unreviewed-pseudolabels", action="store_true")
    args = parser.parse_args()
    if not args.allow_unreviewed_pseudolabels:
        parser.error("数据为 needs_human_review；研究性伪标签训练必须显式传入 --allow-unreviewed-pseudolabels")
    if min(args.epochs, args.patience, args.max_tokens, args.max_seqs, args.grad_accum, args.rl_samples) < 1:
        parser.error("epochs/patience/batch/accumulation/sample 参数都必须为正数")
    if args.rl_samples < 2 or args.sigma_start <= 0 or args.sigma_end <= 0:
        parser.error("RLCD 至少需要 2 个探索样本且 sigma 必须大于 0")

    project_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_dir.parent))
    from laya.finetune_reviewed_jsonl import load_reviewed_jsonl, compile_records
    from laya.models import rl_common as common

    try:
        import torch
        from safetensors.torch import load_file, save_file
        from transformers import AutoTokenizer
    except ImportError as exc:
        parser.error("缺少依赖: %s" % exc)
    if not torch.cuda.is_available():
        parser.error("当前训练器仅支持 CUDA")

    train_dev_rows = load_rows(args.train_dev)
    train_records, dev_records = load_reviewed_jsonl(
        args.train_dev, allow_unreviewed_pseudolabels=True)
    calibration_records = load_rows(args.calibration)
    test_records = load_rows(args.test)
    expected_split(calibration_records, "calibration")
    expected_split(test_records, "test")
    all_sets = {
        "train": {r["source_group_id"] for r in train_records},
        "dev": {r["source_group_id"] for r in dev_records},
        "calibration": {r["source_group_id"] for r in calibration_records},
        "test": {r["source_group_id"] for r in test_records},
    }
    names = list(all_sets)
    for index, name in enumerate(names):
        for other in names[index + 1:]:
            if all_sets[name] & all_sets[other]:
                raise ValueError("source_group_id 在 %s 与 %s 间泄漏" % (name, other))
    counts = {name: len(rows) for name, rows in (
        ("train", train_records), ("dev", dev_records),
        ("calibration", calibration_records), ("test", test_records))}
    if counts != {"train": 1200, "dev": 200, "calibration": 100, "test": 400}:
        raise ValueError("全量 v2 split 数量错误: %s" % counts)

    model_dir = Path(args.model_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    if not (model_dir / "model.safetensors").is_file():
        parser.error("基座模型缺少 model.safetensors: %s" % model_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        parser.error("输出目录非空；请指定新的实验目录: %s" % out_dir)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    device = torch.device("cuda:0")
    amp_dtype = torch.float16
    with (model_dir / "rl_agent_config.json").open(encoding="utf-8") as stream:
        cfg = json.load(stream)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir / "tokenizer"))
    train_groups = compile_records(train_records, tokenizer, cfg, common, False, args.seed)
    dev_groups = compile_records(dev_records, tokenizer, cfg, common, False, args.seed)
    calibration_groups = compile_records(calibration_records, tokenizer, cfg, common, False, args.seed)
    test_groups = compile_records(test_records, tokenizer, cfg, common, False, args.seed)
    train_batches = common.pack_groups(train_groups, args.max_tokens, args.max_seqs)
    updates_per_epoch = math.ceil(len(train_batches) / args.grad_accum)
    total_updates = updates_per_epoch * args.epochs
    print("GPU:", torch.cuda.get_device_name(0),
          "VRAM GiB:", round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2), flush=True)
    print("Data records:", counts, "questions:", {
        "train": sum(len(r["qs"]) for r in train_records),
        "dev": sum(len(r["qs"]) for r in dev_records),
        "calibration": sum(len(r["qs"]) for r in calibration_records),
        "test": sum(len(r["qs"]) for r in test_records),
    }, flush=True)
    print("Compiled train batches:", len(train_batches), "updates/epoch:", updates_per_epoch,
          "gradient accumulation:", args.grad_accum, "effective decisions/update approx:",
          round(sum(len(item) for group_batch in train_batches for item in group_batch)
                / len(train_batches) * args.grad_accum, 1), flush=True)
    print("Config:", json.dumps(vars(args), ensure_ascii=False, sort_keys=True), flush=True)
    if args.dry_run:
        print("Dry run passed: no model weights changed and no training started.", flush=True)
        return

    started = datetime.now(timezone.utc).isoformat()
    start_time = time.time()
    tokenizer_path = model_dir / "tokenizer"
    model = common.build_model(cfg, encoder_dir=str(model_dir / "encoder"))
    weights = load_file(str(model_dir / "model.safetensors"), device="cpu")
    model.load_state_dict(weights, strict=True)
    del weights
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(not name.startswith("act_head."))
    if hasattr(model.encoder, "gradient_checkpointing_enable"):
        try:
            model.encoder.gradient_checkpointing_enable(
                gradient_checkpointing_kwargs={"use_reentrant": False})
        except TypeError:
            model.encoder.gradient_checkpointing_enable()
    model.head_checkpointing = True
    model.to(device)
    model.train()
    model.act_head.eval()
    encoder_params = [p for p in model.encoder.parameters() if p.requires_grad]
    head_params = [p for n, p in model.named_parameters()
                   if not n.startswith("encoder.") and p.requires_grad]
    trainable = sum(p.numel() for p in encoder_params + head_params)
    total = sum(p.numel() for p in model.parameters())
    if not encoder_params or not head_params:
        raise RuntimeError("未能正确分离 encoder 与 decision head 参数组")
    optimizer = torch.optim.AdamW([
        {"params": encoder_params, "lr": args.lr_encoder},
        {"params": head_params, "lr": args.lr_head},
    ], weight_decay=args.weight_decay, foreach=False)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(1, total_updates), eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_dir = out_dir / "checkpoint_latest"
    latest_dir.mkdir()
    config = {"method": "rlcd_official_recipe_adapted", "started_at_utc": started,
              "base_model_dir": str(model_dir), "base_model_sha256": sha256(model_dir / "model.safetensors"),
              "train_dev_sha256": sha256(args.train_dev), "calibration_sha256": sha256(args.calibration),
              "test_sha256": sha256(args.test), "data_review_state": "needs_human_review",
              "label_source": "DeepSeek vote proxy; not human gold or calibrated probability",
              "counts": counts, "training_args": vars(args), "batch_count_per_epoch": len(train_batches),
              "optimizer_updates_per_epoch": updates_per_epoch, "total_optimizer_updates": total_updates,
              "trainable_parameters": trainable, "total_parameters": total,
              "parameter_groups": {"encoder_lr": args.lr_encoder, "decision_head_lr": args.lr_head,
                                   "act_head": "frozen"},
              "adaptations": [
                  "single RTX 3090 instead of upstream 2xT4 DDP",
                  "local source-grouped conversation-decision JSONL instead of typed-decisions HF schema",
                  "train/dev source-group split retained; temperature is fitted on the independent 100-group calibration split",
                  "gradient accumulation approximates upstream 64-decision effective batch",
              ]}
    (out_dir / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    history_path = out_dir / "training_log.jsonl"
    history = []
    best_epoch = 0
    best_loss = float("inf")
    stale_epochs = 0
    amp_and_optimizer = {"amp_dtype": str(amp_dtype), "optimizer": "AdamW", "scheduler": "CosineAnnealingLR"}
    print("Trainable parameters:", trainable, "/", total, "|", amp_and_optimizer, flush=True)
    torch.cuda.reset_peak_memory_stats()

    with history_path.open("w", encoding="utf-8") as history_file:
        for epoch in range(args.epochs):
            epoch_groups = list(train_groups)
            random.Random(args.seed + epoch).shuffle(epoch_groups)
            batches = common.pack_groups(epoch_groups, args.max_tokens, args.max_seqs)
            progress = epoch / max(1, args.epochs - 1)
            sigma = args.sigma_start + (args.sigma_end - args.sigma_start) * progress
            model.train()
            model.act_head.eval()
            sums = Counter()
            update_count = 0
            for start in range(0, len(batches), args.grad_accum):
                window = batches[start:start + args.grad_accum]
                window_questions = sum(len(group) for group_batch in window for group in group_batch)
                optimizer.zero_grad(set_to_none=True)
                for group_batch in window:
                    batch = common.collate_items(group_batch, tokenizer.pad_token_id)
                    input_ids = batch["input_ids"].to(device)
                    attention_mask = batch["attention_mask"].to(device)
                    marker_pos = batch["marker_pos"].to(device)
                    marker_mask = batch["marker_mask"].to(device)
                    target = batch["target"].to(device)
                    qtype = batch["qtype"].to(device)
                    with torch.autocast("cuda", dtype=amp_dtype):
                        logits, _ = model(input_ids, attention_mask, marker_pos, marker_mask, qtype)
                    logits = logits.float().masked_fill(~marker_mask, -1e4)
                    k = marker_mask.sum(-1, keepdim=True).float().clamp_min(1.0)
                    # Match upstream projected zero-mean exploration over valid options.
                    noise = torch.randn((args.rl_samples, *logits.shape), device=device) * sigma
                    noise = noise * marker_mask.unsqueeze(0)
                    noise = (noise - noise.sum(-1, keepdim=True) / k.unsqueeze(0)) * marker_mask.unsqueeze(0)
                    sampled_logits = logits.detach().unsqueeze(0) + noise
                    sampled_probs = torch.softmax(
                        sampled_logits.masked_fill(~marker_mask.unsqueeze(0), -1e4), dim=-1)
                    with torch.no_grad():
                        rewards = common.proper_reward(
                            sampled_probs, target, qtype, marker_mask,
                            w_sph=args.w_sph, w_rps=args.w_rps)
                        advantage = rewards - rewards.mean(0, keepdim=True)
                        advantage = advantage / (advantage.std() + 1e-6)
                    log_prob = -(((sampled_logits - logits.unsqueeze(0)) ** 2)
                                 * marker_mask.unsqueeze(0)).sum(-1) / (2 * sigma ** 2)
                    loss_rl = -(advantage * log_prob).mean()
                    ce = -(target * torch.log_softmax(logits, dim=-1)).sum(-1).mean()
                    n = int(len(batch["label"]))
                    loss = (loss_rl + args.ce_weight * ce) * n / window_questions
                    if not torch.isfinite(loss):
                        raise RuntimeError("训练 loss 出现 NaN/Inf")
                    scaler.scale(loss).backward()
                    sums["loss_rl"] += float(loss_rl.detach().item()) * n
                    sums["ce"] += float(ce.detach().item()) * n
                    sums["reward"] += float(rewards.mean().item()) * n
                    sums["questions"] += n
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(encoder_params + head_params, 1.0)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                update_count += 1
                if update_count % 25 == 0:
                    print("  Epoch %d/%d | Update %d/%d | sigma=%.3f | reward=%.4f | LR enc/head=%s | GPU GiB=%.2f" % (
                        epoch + 1, args.epochs, update_count, updates_per_epoch, sigma,
                        sums["reward"] / max(1, sums["questions"]),
                        "/".join("%.2e" % value for value in scheduler.get_last_lr()),
                        torch.cuda.max_memory_allocated() / 1024**3), flush=True)

            dev_metrics, _ = evaluate(model, dev_groups, tokenizer, common, torch, device,
                                      amp_dtype, args.max_tokens, args.max_seqs)
            row = {
                "event": "epoch", "epoch": epoch + 1, "sigma": sigma,
                "train_policy_loss": sums["loss_rl"] / max(1, sums["questions"]),
                "train_soft_ce": sums["ce"] / max(1, sums["questions"]),
                "train_reward": sums["reward"] / max(1, sums["questions"]),
                "dev": dev_metrics,
                "lr_encoder": scheduler.get_last_lr()[0],
                "lr_head": scheduler.get_last_lr()[1],
                "elapsed_seconds": round(time.time() - start_time, 2),
            }
            history.append(row)
            history_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            history_file.flush()
            print("Epoch %d/%d: sigma=%.3f reward=%.4f policy=%.4f CE=%.4f dev_CE=%.4f dev_acc=%.4f | %.1fs" % (
                epoch + 1, args.epochs, sigma, row["train_reward"], row["train_policy_loss"],
                row["train_soft_ce"], dev_metrics["soft_cross_entropy"],
                dev_metrics["argmax_accuracy"], row["elapsed_seconds"]), flush=True)

            save_model_weights(model, latest_dir / "model.safetensors", save_file, torch)
            (latest_dir / "checkpoint_meta.json").write_text(json.dumps({
                "epoch": epoch + 1, "sigma": sigma, "dev": dev_metrics,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if dev_metrics["soft_cross_entropy"] < best_loss:
                best_loss = dev_metrics["soft_cross_entropy"]
                best_epoch = epoch + 1
                stale_epochs = 0
                shutil.copy2(latest_dir / "model.safetensors", out_dir / "model.safetensors")
            else:
                stale_epochs += 1
            if stale_epochs >= args.patience:
                print("Early stopping after epoch", epoch + 1, flush=True)
                break

    if not (out_dir / "model.safetensors").is_file():
        raise RuntimeError("没有可用的 dev-best checkpoint")
    best_weights = load_file(str(out_dir / "model.safetensors"), device="cpu")
    model.load_state_dict(best_weights, strict=True)
    del best_weights
    model.eval()
    calibration_raw, logits_by_type = evaluate(
        model, calibration_groups, tokenizer, common, torch, device, amp_dtype,
        args.max_tokens, args.max_seqs, collect=True)
    fitted_temperatures = [1.0, 1.0, 1.0]
    for qtype in range(3):
        if logits_by_type[qtype]:
            fitted_temperatures[qtype] = fit_temperature(logits_by_type[qtype], torch)
    calibration_scaled, _ = evaluate(
        model, calibration_groups, tokenizer, common, torch, device, amp_dtype,
        args.max_tokens, args.max_seqs, temperatures=fitted_temperatures)
    test_raw, _ = evaluate(
        model, test_groups, tokenizer, common, torch, device, amp_dtype,
        args.max_tokens, args.max_seqs)
    test_scaled, _ = evaluate(
        model, test_groups, tokenizer, common, torch, device, amp_dtype,
        args.max_tokens, args.max_seqs, temperatures=fitted_temperatures)

    cfg["fine_tuned"] = True
    cfg["model_name"] = "laya-rlcd-official-recipe-adapted"
    cfg["temperature"] = fitted_temperatures
    cfg.pop("temperature_by_options", None)
    cfg["training"] = {
        "method": "rlcd_official_recipe_adapted",
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "seed": args.seed,
        "optimizer_updates": sum(math.ceil(len(common.pack_groups(train_groups, args.max_tokens, args.max_seqs))
                                           / args.grad_accum) for _ in history),
    }
    save_model_weights(model, out_dir / "model.safetensors", save_file, torch)
    model.encoder.config.save_pretrained(str(out_dir / "encoder"))
    tokenizer.save_pretrained(str(out_dir / "tokenizer"))
    (out_dir / "rl_agent_config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "rlcd_official_recipe_adapted",
        "data_review_state": "needs_human_review",
        "label_source": "DeepSeek vote proxy; not human gold or calibrated probability",
        "base_model_sha256": config["base_model_sha256"],
        "output_model_sha256": sha256(out_dir / "model.safetensors"),
        "data_sha256": {"train_dev": config["train_dev_sha256"],
                        "calibration": config["calibration_sha256"], "test": config["test_sha256"]},
        "split_records": counts,
        "split_questions": {"train": sum(len(r["qs"]) for r in train_records),
                            "dev": sum(len(r["qs"]) for r in dev_records),
                            "calibration": sum(len(r["qs"]) for r in calibration_records),
                            "test": sum(len(r["qs"]) for r in test_records)},
        "epochs_completed": len(history),
        "best_epoch": best_epoch,
        "training_config": config["training_args"],
        "optimizer_updates_per_epoch": updates_per_epoch,
        "total_optimizer_updates": updates_per_epoch * len(history),
        "trainable_parameters": trainable,
        "total_parameters": total,
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
        "training_seconds": round(time.time() - start_time, 2),
        "dev_best": min(history, key=lambda row: row["dev"]["soft_cross_entropy"])["dev"],
        "calibration_before_temperature": calibration_raw,
        "fitted_temperatures_choice_score_noul": fitted_temperatures,
        "calibration_after_temperature": calibration_scaled,
        "test_before_temperature": test_raw,
        "test_after_temperature": test_scaled,
        "test_note": "Same fixed test split previously inspected for the baseline report; this run is a controlled exploratory comparison, not a fresh untouched confirmation set.",
        "upstream_reference": "https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb",
    }
    (out_dir / "experiment.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Calibration temperatures [choice, score, noul]:",
          [round(value, 4) for value in fitted_temperatures], flush=True)
    print("Calibration CE raw/scaled:", calibration_raw["soft_cross_entropy"],
          calibration_scaled["soft_cross_entropy"], flush=True)
    print("Test CE/acc raw:", test_raw["soft_cross_entropy"], test_raw["argmax_accuracy"], flush=True)
    print("Test CE/acc calibrated:", test_scaled["soft_cross_entropy"],
          test_scaled["argmax_accuracy"], flush=True)
    print("Run completed:", out_dir, flush=True)


if __name__ == "__main__":
    main()
