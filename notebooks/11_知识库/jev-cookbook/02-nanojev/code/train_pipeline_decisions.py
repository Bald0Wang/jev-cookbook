#!/usr/bin/env python3
"""Train independent conditional distributions or explicit teacher targets.

The original toy CLI remains reproducible. This entry point adds optional soft gold,
local-checkpoint warm starts, complete-question microbatches and dev-only selection.
No teacher calls, chain-of-thought generation or automatic candidate truncation.
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import random
import time

from predict_toy_decisions import (
    local_checkpoint_files, prepare_examples, read_json, reject_nonfinite,
    unique_object, validate_request,
)

GOLD_PROB_KINDS = {"programmatic_conditional_distribution", "optimal_action_policy", "deterministic_truth",
                   "expert_policy_distribution"}
GOLD_LABEL_KINDS = {"observed_outcome", "deterministic_truth", "reference_argmax_compatibility",
                    "unspecified_compatibility_label", "hard_gold_unspecified", "unobserved"}
SPLITS = ("train", "dev", "calibration", "test", "ood")


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def candidate_ids(question):
    if question["type"] == "boolean":
        return ["false", "true"]
    if question["type"] == "choice":
        return list(question["criteria"])
    return [str(i) for i in range(len(question["criteria"]))]


def per_question(value, qid, default=None):
    return value.get(qid, default) if isinstance(value, dict) else (default if value is None else value)


def probability_vector(value, ids, label, require_unit_sum=True):
    if not isinstance(value, dict) or set(value) != set(ids):
        raise ValueError(f"{label}: probability keys must exactly match all candidate IDs")
    result = []
    for key in ids:
        p = value[key]
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError(f"{label}: probabilities must be finite numbers in [0,1]")
        result.append(float(p))
    total = math.fsum(result)
    if require_unit_sum and abs(total - 1) > 1e-8:
        raise ValueError(f"{label}: probabilities sum to {total}, expected 1; no target imputation")
    return result


def validate_training_row(row):
    if not isinstance(row, dict):
        raise ValueError("Each JSONL row must be an object")
    for key in ("id", "state_id", "family_id", "split", "state", "questions"):
        if key not in row:
            raise ValueError(f"Missing record field: {key}")
    if row["split"] not in SPLITS:
        raise ValueError("Unknown split")
    for key in ("state_id", "family_id"):
        if not isinstance(row[key], str) or not row[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    validate_request({"states": [{key: row[key] for key in ("id", "state", "questions")}]})
    qids = set(row["questions"])
    for key in ("gold", "gold_probs"):
        if key in row and (not isinstance(row[key], dict) or set(row[key]) - qids):
            raise ValueError(f"{key} must map known question IDs to targets")
    for key in ("gold_probs_kind", "gold_label_kind"):
        if isinstance(row.get(key), dict) and set(row[key]) - qids:
            raise ValueError(f"{key} contains unknown question IDs")
    teacher = row.get("teacher")
    if teacher is not None:
        if not isinstance(teacher, dict) or not isinstance(teacher.get("native_probs", {}), dict):
            raise ValueError("teacher must contain a native_probs mapping")
        if set(teacher.get("native_probs", {})) - qids:
            raise ValueError("teacher.native_probs contains unknown question IDs")
    targets = {}
    for qid, q in row["questions"].items():
        ids, k = candidate_ids(q), len(candidate_ids(q))
        gold_index = None
        if qid in row.get("gold", {}):
            gold = row["gold"][qid]
            if q["type"] == "boolean":
                if type(gold) is not bool:
                    raise ValueError("Boolean hard gold must be a JSON boolean")
                gold_index = int(gold)
            elif q["type"] == "choice":
                if not isinstance(gold, str) or gold not in ids:
                    raise ValueError("Choice hard gold must name an offered candidate")
                gold_index = ids.index(gold)
            else:
                if type(gold) is not int or not 0 <= gold < k:
                    raise ValueError("Score hard gold must be a valid zero-based integer level")
                gold_index = gold
        soft = None
        kind = None
        if qid in row.get("gold_probs", {}):
            soft = probability_vector(row["gold_probs"][qid], ids, f"{row['id']}:{qid}:gold_probs")
            kind = per_question(row.get("gold_probs_kind"), qid)
            if kind not in GOLD_PROB_KINDS:
                raise ValueError(f"gold_probs requires a declared kind in {sorted(GOLD_PROB_KINDS)}")
            if kind == "deterministic_truth" and not (sum(p == 1.0 for p in soft) == 1 and sum(p != 0 for p in soft) == 1):
                raise ValueError("deterministic_truth requires a one-hot distribution")
        label_kind = per_question(row.get("gold_label_kind"), qid,
                                  "unspecified_compatibility_label" if soft is not None else "hard_gold_unspecified")
        if label_kind not in GOLD_LABEL_KINDS:
            raise ValueError("Unknown gold_label_kind")
        if soft is not None and gold_index is not None and label_kind == "deterministic_truth":
            if soft[gold_index] != 1.0:
                raise ValueError("Declared deterministic hard truth conflicts with soft target")
        gold_target = soft if soft is not None else ([float(i == gold_index) for i in range(k)] if gold_index is not None else None)
        raw, teacher_target, rounding, teacher_error = None, None, None, None
        observed = (teacher or {}).get("native_probs", {}).get(qid)
        if observed is not None:
            # Invalid teacher values are quarantined only from the teacher arm.
            # Independent gold remains usable; preserve the source object in the audit.
            try:
                raw = probability_vector(observed, ids, f"{row['id']}:{qid}:teacher", require_unit_sum=False)
                rounding = (teacher or {}).get("rounding")
                decimals = (rounding or {}).get("probabilityDecimals")
                if decimals is not None and (type(decimals) is not int or not 0 <= decimals <= 15):
                    raise ValueError("Invalid declared teacher decimal precision")
                scale = 10 ** decimals if decimals is not None else None
                if scale and any(abs(p * scale - round(p * scale)) > 1e-6 for p in raw):
                    raise ValueError("Teacher values violate declared decimal precision")
                unit_sum = sum(round(p * scale) for p in raw) == scale if scale else abs(math.fsum(raw) - 1) < 1e-6
                if not unit_sum or math.fsum(raw) <= 0:
                    raise ValueError("Rounded target has no identity probability-simplex representative")
                teacher_target = raw
            except (ValueError, TypeError, AttributeError) as exc:
                teacher_error = str(exc)
        if gold_target is None and teacher_target is None:
            # Keep unlabelled/malformed-teacher examples for a coverage audit; no arm silently invents targets.
            pass
        targets[qid] = {"gold_index": gold_index, "gold_probs": soft, "gold_probs_kind": kind,
                        "gold_label_kind": label_kind, "gold_distribution_probs": gold_target,
                        "teacher_raw_probs": raw, "teacher_probs": teacher_target,
                        "teacher_rounding": rounding, "teacher_target_error": teacher_error,
                        "teacher_raw_mapping": observed}
    return targets


def read_training_records(path):
    path = Path(path)
    files = [path] if path.is_file() else [path / f"{s}.jsonl" for s in SPLITS if (path / f"{s}.jsonl").is_file()]
    if not files:
        raise ValueError("No input JSONL files")
    records, ids, state_splits, source_splits = [], set(), {}, {}
    for filename in files:
        for lineno, line in enumerate(filename.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line, object_pairs_hook=unique_object, parse_constant=reject_nonfinite)
            try:
                validate_training_row(row)
                if row["id"] in ids:
                    raise ValueError("Duplicate record ID")
                ids.add(row["id"])
                for key, registry in ((row["state_id"], state_splits),
                                      (row.get("metadata", {}).get("source_group_id"), source_splits)):
                    if key is not None:
                        if key in registry and registry[key] != row["split"]:
                            raise ValueError("The same state/source group crosses dataset splits")
                        registry[key] = row["split"]
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{filename.name}:{lineno}: {exc}") from exc
            records.append(row)
    return records, files


def load_training_examples(path, tokenizer, max_length):
    records, _ = read_training_records(path)
    examples, audit = [], []
    for row in records:
        targets = validate_training_row(row)
        prepared = prepare_examples({"states": [{key: row[key] for key in ("id", "state", "questions")}]},
                                    tokenizer, max_length)
        for ex in prepared:
            t = targets[ex["qid"]]
            ex.update(t, state_id=row["state_id"], family_id=row["family_id"], split=row["split"], source=row)
            examples.append(ex)
            audit.append({"id": ex["id"], "split": ex["split"], "family_id": ex["family_id"],
                          "type": ex["type"], "k": len(ex["candidate_ids"]),
                          "max_path_tokens": max(map(len, ex["leaf_tokens"])),
                          "gold_distribution_kind": t["gold_probs_kind"] or ("hard_gold_one_hot" if t["gold_index"] is not None else None),
                          "gold_label_kind": t["gold_label_kind"],
                          "gold_distribution_usable": t["gold_distribution_probs"] is not None,
                          "teacher_raw_sum": math.fsum(t["teacher_raw_probs"]) if t["teacher_raw_probs"] is not None else None,
                          "teacher_proxy_usable": t["teacher_probs"] is not None,
                          "teacher_argmax_matches_gold": max(range(len(t["teacher_probs"])), key=t["teacher_probs"].__getitem__) == t["gold_index"] if t["teacher_probs"] is not None and t["gold_index"] is not None else None,
                          "target_transform": "identity_rounded_proxy" if t["teacher_probs"] is not None else "quarantined_or_missing",
                          "teacher_target_error": t["teacher_target_error"],
                          "teacher_raw_mapping": t["teacher_raw_mapping"]})
    return examples, audit


def target_for(example, objective):
    if objective == "observed_outcome":
        i = example["gold_index"]
        if example.get("gold_label_kind") != "observed_outcome" or i is None:
            return None
        return [float(j == i) for j in range(len(example["candidate_ids"]))]
    if objective == "teacher":
        return example["teacher_probs"]
    if objective == "gold_distribution":
        return example["gold_distribution_probs"]
    if objective == "gold":
        i = example["gold_index"]
        return [float(j == i) for j in range(len(example["candidate_ids"]))] if i is not None else None
    raise ValueError("Unknown objective")


def grouped_target_loss(logits, examples, objective):
    import torch
    losses = []
    for z, ex in zip(logits, examples):
        k = len(ex["candidate_ids"])
        target = target_for(ex, objective)
        if target is None:
            raise ValueError(f"Missing/quarantined {objective} target entered training: {ex['id']}")
        t = torch.tensor(target, dtype=torch.float32, device=z.device)
        # Normalize over this complete question only. Padded candidate logits never enter the loss.
        losses.append(-(t * z[:k].float().log_softmax(-1)).sum())
    return torch.stack(losses)


def pack_complete_questions(examples, max_questions, max_tokens):
    """Budget counts all candidate paths times the longest padded path; no candidate splitting."""
    if max_questions <= 0 or max_tokens < 0:
        raise ValueError("Invalid microbatch limits")
    result, group, paths, width = [], [], 0, 0
    for ex in examples:
        n, size = len(ex["leaf_tokens"]), max(map(len, ex["leaf_tokens"]))
        if max_tokens and n * size > max_tokens:
            raise ValueError(f"Complete question {ex['id']} requires {n*size} padded tokens, over budget {max_tokens}; increase explicit budget or use a separately implemented gradient-cache path, never split its softmax or truncate candidates")
        prospective = (paths + n) * max(width, size)
        if group and (len(group) >= max_questions or (max_tokens and prospective > max_tokens)):
            result.append(group)
            group, paths, width = [], 0, 0
        group.append(ex)
        paths += n
        width = max(width, size)
    if group:
        result.append(group)
    return result


def distribution_metrics(target, logits):
    if target is None:
        return None
    largest = max(logits)
    log_norm = largest + math.log(math.fsum(math.exp(z - largest) for z in logits))
    logp = [z - log_norm for z in logits]
    p = [math.exp(z) for z in logp]
    ce = -math.fsum(t * z for t, z in zip(target, logp))
    entropy = -math.fsum(t * math.log(t) for t in target if t > 0)
    return {"ce": ce, "kl": ce - entropy, "tv": .5 * math.fsum(abs(t-s) for t, s in zip(target, p))}


def evaluate_pipeline(model, examples, pad_token, args, objective, path=None):
    import torch
    from train_toy_decisions import prediction_record
    model.eval()
    rows, totals, count, kinds = [], {k: 0.0 for k in ("ce", "kl", "tv")}, 0, {}
    all_targets = {name: {"n": 0, "ce": 0.0, "kl": 0.0, "tv": 0.0} for name in ("teacher", "gold_distribution", "observed_outcome")}
    with torch.inference_mode():
        for group in pack_complete_questions(examples, args.microbatch_questions, args.max_microbatch_tokens):
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=args.precision == "bf16"):
                z, _ = model(group, pad_token)
            for ex, values in zip(group, z):
                logits = values[:len(ex["candidate_ids"])].float().cpu().tolist()
                if not all(math.isfinite(v) for v in logits):
                    raise RuntimeError("Nonfinite evaluation logits")
                record = prediction_record(ex, values)
                rows.append(record)
                for target_name in all_targets:
                    metrics = distribution_metrics(target_for(ex, target_name), logits)
                    if metrics is not None:
                        all_targets[target_name]["n"] += 1
                        for key in ("ce", "kl", "tv"):
                            all_targets[target_name][key] += metrics[key]
                metrics = distribution_metrics(target_for(ex, objective), logits)
                if metrics is None:
                    continue
                count += 1
                for key in totals:
                    totals[key] += metrics[key]
                kind = ((ex.get("gold_probs_kind") or "hard_gold_one_hot") if objective == "gold_distribution"
                        else "observed_outcome" if objective == "observed_outcome" else "teacher_rounded_proxy")
                bucket = kinds.setdefault(kind, {"n": 0, "ce": 0.0, "kl": 0.0, "tv": 0.0})
                bucket["n"] += 1
                for key in totals:
                    bucket[key] += metrics[key]
    if path:
        Path(path).write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows), encoding="utf-8")
    for bucket in list(kinds.values()) + list(all_targets.values()):
        if bucket["n"]:
            for key in ("ce", "kl", "tv"):
                bucket[key] /= bucket["n"]
    return {"questions": len(examples), "objective": objective, "eligible_questions": count,
            **{f"target_{key}": value / count if count else None for key, value in totals.items()},
            "by_target_kind": kinds, "independent_targets": all_targets,
            "note": "question-mean distribution recovery; policy targets and reference argmax labels are not observed outcomes"}


def data_schema_summary(records):
    counts, usable = Counter(), Counter()
    for row in records:
        for qid, t in validate_training_row(row).items():
            counts[row["split"]] += 1
            if t["gold_distribution_probs"] is not None:
                usable[(row["split"], "gold_distribution")] += 1
            if t["teacher_probs"] is not None:
                usable[(row["split"], "teacher")] += 1
    return {"records": len(records), "questions_by_split": dict(counts),
            "eligible_by_split_objective": {f"{s}/{o}": n for (s, o), n in sorted(usable.items())}}


def self_check():
    """Necessary schema, masking and accumulation checks; CPU only, no model download."""
    row = {"id": "check", "state_id": "check", "family_id": "check", "split": "train", "state": "A fair coin is unobserved.",
           "questions": {"b": {"type": "boolean", "instructions": "Heads?"},
                         "c": {"type": "choice", "instructions": "Choose", "criteria": {"a": "A", "b": "B", "c": "C"}}},
           "gold_probs": {"b": {"false": .5, "true": .5}, "c": {"a": 0, "b": .5, "c": .5}},
           "gold_probs_kind": {"b": "programmatic_conditional_distribution", "c": "optimal_action_policy"}}
    targets = validate_training_row(row)
    assert targets["b"]["gold_index"] is None
    assert targets["c"]["gold_probs_kind"] == "optimal_action_policy"
    bad = json.loads(json.dumps(row)); bad["gold_probs"]["b"]["true"] = .7
    try:
        validate_training_row(bad)
        raise AssertionError("Invalid unit sum accepted")
    except ValueError:
        pass
    bad = json.loads(json.dumps(row)); bad["gold_probs"]["b"] = {"false": .5, "other": .5}
    try:
        validate_training_row(bad)
        raise AssertionError("Candidate mismatch accepted")
    except ValueError:
        pass
    bad = json.loads(json.dumps(row)); bad["teacher"] = {"native_probs": {"b": {"false": -1, "true": 2}}}
    t = validate_training_row(bad)["b"]
    assert t["teacher_probs"] is None and t["gold_distribution_probs"] == [.5, .5]
    examples = [{"id": qid, "candidate_ids": candidate_ids(row["questions"][qid]),
                 "leaf_tokens": [[1, 2]] * (1 if qid == "b" else 3), **targets[qid]} for qid in ("b", "c")]
    assert len(pack_complete_questions(examples, 1, 6)) == 2
    try:
        pack_complete_questions(examples, 2, 5)
        raise AssertionError("Oversize complete question accepted")
    except ValueError:
        pass
    numerical = "skipped: torch unavailable; run --self-check in the training environment for CPU gradient checks"
    if importlib.util.find_spec("torch") is not None:
        import torch
        z = torch.tensor([[.2, -.7, 100.0], [-.2, .3, .8]], requires_grad=True)
        grouped_target_loss(z, examples, "gold_distribution").mean().backward()
        g = z.grad.detach().clone()
        independent = z.detach().clone().requires_grad_()
        for i, ex in enumerate(examples):
            (grouped_target_loss(independent[i:i+1], [ex], "gold_distribution").sum() / len(examples)).backward()
        assert torch.allclose(g, independent.grad, atol=1e-7, rtol=1e-6)
        assert g[0, 2] == 0
        for i, ex in enumerate(examples):
            k = len(ex["candidate_ids"])
            expected = (z[i, :k].detach().softmax(-1) - torch.tensor(ex["gold_distribution_probs"])) / len(examples)
            assert torch.allclose(g[i, :k], expected, atol=1e-7, rtol=1e-6)
        boolean_z = torch.tensor(.3, requires_grad=True)
        boolean_logits = torch.stack([boolean_z * 0, boolean_z]).unsqueeze(0)
        grouped_target_loss(boolean_logits, [examples[0]], "gold_distribution").sum().backward()
        assert torch.allclose(boolean_z.grad, boolean_z.detach().sigmoid() - .5, atol=1e-7)
        numerical = "passed: grouped soft CE gradient, padding mask, question-mean accumulation and Boolean derivative"
    print(json.dumps({"schema_checks": "passed", "complete_question_budget": "passed", "numerical_checks": numerical}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input")
    p.add_argument("--output-dir")
    p.add_argument("--model", default="Qwen/Qwen3-0.6B")
    p.add_argument("--revision", default="main")
    p.add_argument("--init-checkpoint", help="Local DecisionModel warm start; optimizer is new, not an exact training resume")
    p.add_argument("--objective", choices=["teacher", "gold_distribution", "observed_outcome"], default="gold_distribution")
    p.add_argument("--loss", choices=["ce", "brier", "paired_brier_pg"], default="ce")
    p.add_argument("--reward-samples", type=int, default=32)
    p.add_argument("--gradient-checkpointing", action="store_true", help="Reduce activation memory for complete long maze inputs")
    p.add_argument("--set-head", choices=["none", "attention"], help="Defaults to attention, or the warm-start checkpoint's setting")
    p.add_argument("--steps", type=int, default=300)
    p.add_argument("--head-steps", type=int, help="Defaults to12 for a new head and0 for a checkpoint warm start")
    p.add_argument("--batch-questions", type=int, default=12, help="Effective questions per optimizer update, equal weight")
    p.add_argument("--microbatch-questions", type=int, default=4)
    p.add_argument("--max-microbatch-tokens", type=int, default=16384, help="Complete candidate paths times padded length;0 disables cap")
    p.add_argument("--eval-every", type=int, default=50)
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--backbone-lr", type=float, default=2e-5)
    p.add_argument("--head-lr", type=float, default=2e-4)
    p.add_argument("--head-warmup-lr", type=float, default=1e-3)
    p.add_argument("--precision", choices=["bf16", "fp32"], default="bf16")
    p.add_argument("--disable-native-triton", action="store_true")
    p.add_argument("--validate-only", action="store_true", help="Stdlib schema/split/target audit only, no tokenizer/GPU")
    p.add_argument("--self-check", action="store_true", help="CPU-only necessary schema/numerical checks; no model download")
    args = p.parse_args()
    if args.reward_samples < 2:
        p.error("--reward-samples must be >= 2")
    if args.loss == "paired_brier_pg" and args.objective != "observed_outcome":
        p.error("paired_brier_pg requires --objective observed_outcome")
    if args.self_check:
        self_check()
        return
    if not args.input:
        p.error("--input is required")
    records, files = read_training_records(args.input)
    if args.validate_only:
        print(json.dumps(data_schema_summary(records), ensure_ascii=False))
        return
    if not args.output_dir:
        p.error("--output-dir is required")
    args.head_steps = (0 if args.init_checkpoint else 12) if args.head_steps is None else args.head_steps
    if min(args.steps, args.batch_questions, args.microbatch_questions, args.eval_every, args.max_length) <= 0 or args.head_steps < 0 or args.max_microbatch_tokens < 0:
        p.error("Invalid steps/batch/token limits")
    if any(not math.isfinite(v) or v <= 0 for v in (args.backbone_lr, args.head_lr, args.head_warmup_lr)):
        p.error("Learning rates must be finite and positive")
    out = Path(args.output_dir)
    if (out / "config.json").exists() or (out / "best.safetensors").exists():
        raise ValueError("Use a new output directory; existing checkpoints are not overwritten")
    out.mkdir(parents=True, exist_ok=True)
    import torch
    from safetensors.torch import load_file, save_file
    from transformers import AutoConfig, AutoModel, AutoTokenizer
    from train_toy_decisions import DecisionModel
    if args.disable_native_triton:
        from torch._native import triton_utils
        triton_utils.deregister_op_overrides()
    if not torch.cuda.is_available() or (args.precision == "bf16" and not torch.cuda.is_bf16_supported()):
        raise RuntimeError("A usable CUDA device with the requested precision is required")
    torch.backends.cuda.matmul.allow_tf32 = False
    random.seed(args.seed); torch.manual_seed(args.seed); torch.cuda.manual_seed_all(args.seed)
    init_config = None
    if args.init_checkpoint:
        _, checkpoint_files = local_checkpoint_files(args.init_checkpoint)
        init_config = read_json(checkpoint_files["run_config"])
        if args.set_head is not None and args.set_head != init_config["set_head"]:
            raise ValueError("Warm-start architecture cannot change set_head")
        args.set_head = init_config["set_head"]
        tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_files["tokenizer"]), local_files_only=True, trust_remote_code=False)
        body_config = AutoConfig.from_pretrained(str(checkpoint_files["body_config"]), local_files_only=True, trust_remote_code=False)
        backbone = AutoModel.from_config(body_config, attn_implementation="sdpa", trust_remote_code=False).float()
        model = DecisionModel(backbone, args.set_head)
        weights = load_file(str(checkpoint_files["weights"]), device="cpu")
        model.load_state_dict(weights, strict=True)
        del weights
    else:
        args.set_head = args.set_head or "attention"
        tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision, trust_remote_code=False)
        backbone = AutoModel.from_pretrained(args.model, revision=args.revision, dtype=torch.float32,
                                             attn_implementation="sdpa", trust_remote_code=False)
        model = DecisionModel(backbone, args.set_head)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.backbone.config.use_cache = False
    if args.gradient_checkpointing:
        model.backbone.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    if args.max_length > getattr(model.backbone.config, "max_position_embeddings", args.max_length):
        raise ValueError("Requested max_length exceeds backbone context limit")
    examples, audit = load_training_examples(args.input, tokenizer, args.max_length)
    splits = {s: [e for e in examples if e["split"] == s] for s in SPLITS}
    for s in ("train", "dev", "test"):
        if not splits[s]:
            raise ValueError(f"{s} must be nonempty")
    train = [e for e in splits["train"] if target_for(e, args.objective) is not None]
    if len(train) < args.batch_questions:
        raise ValueError("Fewer eligible training questions than one effective batch")
    if not any(target_for(e, args.objective) is not None for e in splits["dev"]):
        raise ValueError("No eligible dev targets for the selected objective")
    # Fail before training if even one complete question cannot satisfy the declared budget.
    for group in splits.values():
        pack_complete_questions(group, args.microbatch_questions, args.max_microbatch_tokens)
    model.cuda()
    config = {**vars(args), "schema_version": "openjev-decision-pipeline-v1",
              "model": init_config.get("model", args.model) if init_config else args.model,
              "resolved_model_revision": init_config.get("resolved_model_revision") if init_config else getattr(model.backbone.config, "_commit_hash", None),
              "initialization": "local DecisionModel warm start, fresh optimizer" if init_config else "pretrained backbone with new decision head",
              "data_sha256": {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
              "deps": {k: importlib.metadata.version(k) for k in ("torch", "transformers", "safetensors")},
              "gpu": torch.cuda.get_device_name(0), "parameter_storage": "float32",
              "forward_autocast": "bfloat16" if args.precision == "bf16" else "disabled",
              "parameter_count": sum(t.numel() for t in model.parameters()),
              "train_questions": len(train), "all_train_questions": len(splits["train"]),
              "schema_counts": data_schema_summary(records),
              "loss_description": "equal question weight; complete candidate normalization; sampled loss is a score-function surrogate" if args.loss == "paired_brier_pg" else "per-question proper loss; complete candidate normalization",
              "rlcd_candidate": "independent paired categorical proper-reward policy gradient" if args.loss == "paired_brier_pg" else None,
              "selection": "minimum dev target CE; held-out test first evaluated after training and checkpoint selection",
              "parallelism": "complete candidate paths batched in one backbone call per microbatch; no prefix sharing"}
    dump(out / "config.json", config); dump(out / "target_audit.json", audit)
    tokenizer.save_pretrained(out / "tokenizer"); model.backbone.config.save_pretrained(out / "backbone_config")
    initial = evaluate_pipeline(model, splits["dev"], tokenizer.pad_token_id, args, args.objective, out / "initial_dev.jsonl")
    dump(out / "initial_dev_metrics.json", initial)
    head = [param for name, param in model.named_parameters() if not name.startswith("backbone.")]
    body = list(model.backbone.parameters())
    optimizer = torch.optim.AdamW([{"params": body, "lr": args.backbone_lr}, {"params": head, "lr": args.head_lr}], weight_decay=.01)
    best, best_step, logs = float("inf"), None, []
    started = time.perf_counter()
    from calibrated_objectives import grouped_calibrated_loss
    reward_generator = torch.Generator(device="cuda").manual_seed(args.seed + 104729)
    torch.cuda.reset_peak_memory_stats()
    for step in range(args.head_steps + args.steps):
        warm = step < args.head_steps
        for param in body:
            param.requires_grad_(not warm)
        optimizer.param_groups[1]["lr"] = args.head_warmup_lr if warm else args.head_lr
        batch = random.sample(train, args.batch_questions)
        groups = pack_complete_questions(batch, args.microbatch_questions, args.max_microbatch_tokens)
        model.train(); optimizer.zero_grad(set_to_none=True)
        loss_sum = 0.0
        for group in groups:
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=args.precision == "bf16"):
                logits, _ = model(group, tokenizer.pad_token_id)
                # A single denominator for the full optimizer update, regardless of microbatch sizes or K.
                loss = grouped_calibrated_loss(logits, group, args.objective, args.loss,
                                              args.reward_samples, reward_generator).sum() / len(batch)
            if not torch.isfinite(loss):
                raise RuntimeError("Nonfinite loss")
            loss.backward(); loss_sum += float(loss.detach())
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        item = {"step": step + 1, "phase": "head" if warm else "full", "loss": loss_sum,
                "questions": len(batch), "microbatches": len(groups), "elapsed_seconds": time.perf_counter() - started,
                "batch_question_ids_sha256": hashlib.sha256("\n".join(ex["id"] for ex in batch).encode()).hexdigest()}
        if not warm and ((step + 1 - args.head_steps) % args.eval_every == 0 or step + 1 == args.head_steps + args.steps):
            metrics = evaluate_pipeline(model, splits["dev"], tokenizer.pad_token_id, args, args.objective)
            item["dev"] = metrics
            if metrics["target_ce"] is not None and math.isfinite(metrics["target_ce"]) and metrics["target_ce"] < best:
                best, best_step = metrics["target_ce"], step + 1
                save_file({k: v.detach().cpu().contiguous().clone() for k, v in model.state_dict().items()}, out / "best.safetensors")
        logs.append(item)
        if step % 12 == 0 or "dev" in item:
            print(json.dumps(item), flush=True)
    if best_step is None:
        raise RuntimeError("No finite dev checkpoint was selected")
    model.load_state_dict(load_file(out / "best.safetensors"))
    final = {}
    for split in ("dev", "calibration", "test", "ood"):
        if splits[split]:
            final[split] = evaluate_pipeline(model, splits[split], tokenizer.pad_token_id, args, args.objective,
                                            out / f"predictions_{split}.jsonl")
    with (out / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for split in final:
            handle.write((out / f"predictions_{split}.jsonl").read_text(encoding="utf-8"))
    summary = {"best_step": best_step, "best_dev_target_ce": best, "selected_on": "dev target CE",
               "objective": args.objective, "metrics_by_split": final, "temperature": 1.0,
               "temperature_fitted": False, "training_seconds": time.perf_counter() - started,
               "max_gpu_allocated_gb": torch.cuda.max_memory_allocated() / 1e9}
    dump(out / "train_log.json", logs); dump(out / "summary.json", summary)
    print(json.dumps({"done": str(out), **summary}), flush=True)


if __name__ == "__main__":
    main()
