#!/usr/bin/env python3
"""Generate draft Laya JSONL examples with the DeepSeek Chat Completions API.

Generated labels are model suggestions. Keep the output in a review queue until
people or deterministic business rules have checked every accepted label.
"""

import argparse
import copy
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path


DEFAULT_MODEL = "deepseek-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"


def json_text(value, sort_keys=False):
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"), allow_nan=False)


def load_spec(path):
    with open(path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    for field in ("task_family", "policy_version", "lang", "task_description"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError("spec 缺少非空字符串字段: " + field)
    if not isinstance(spec.get("state_requirements"), list) or not spec["state_requirements"]:
        raise ValueError("spec.state_requirements 必须是非空字符串数组")
    if not all(isinstance(x, str) and x.strip() for x in spec["state_requirements"]):
        raise ValueError("spec.state_requirements 的每项都必须是非空字符串")
    if not isinstance(spec.get("questions"), list) or not spec["questions"]:
        raise ValueError("spec.questions 必须是非空数组")

    seen = set()
    for q in spec["questions"]:
        if not isinstance(q, dict):
            raise ValueError("questions 中每项都必须是对象")
        qid, qtype = q.get("id"), q.get("t")
        if not isinstance(qid, str) or not qid.strip() or qid in seen:
            raise ValueError("问题 id 必须是非空且唯一的字符串")
        seen.add(qid)
        if qtype not in ("choice", "noul", "score"):
            raise ValueError("问题 %s 的 t 必须是 choice、noul 或 score" % qid)
        if not isinstance(q.get("ins"), str) or not q["ins"].strip():
            raise ValueError("问题 %s 缺少非空 ins" % qid)
        if not isinstance(q.get("labeling_policy"), str) or not q["labeling_policy"].strip():
            raise ValueError("问题 %s 必须写清 labeling_policy" % qid)
        crit = q.get("crit")
        if qtype == "choice" and (not isinstance(crit, dict) or len(crit) < 2):
            raise ValueError("choice 问题 %s 的 crit 必须是至少含两个选项的对象" % qid)
        if qtype == "noul" and (not isinstance(crit, dict) or "false" not in crit or "true" not in crit):
            raise ValueError("noul 问题 %s 的 crit 必须同时定义 false 和 true" % qid)
        if qtype == "score" and (not isinstance(crit, list) or len(crit) < 2):
            raise ValueError("score 问题 %s 的 crit 必须是至少含两个有序等级的数组" % qid)

    examples = spec.get("examples", [])
    if not isinstance(examples, list):
        raise ValueError("spec.examples 必须是数组")
    qids = {q["id"] for q in spec["questions"]}
    for i, example in enumerate(examples):
        if not isinstance(example, dict) or not valid_state(example.get("state")):
            raise ValueError("examples[%d].state 必须是非空对象或字符串" % i)
        if not isinstance(example.get("labels"), dict) or set(example["labels"]) != qids:
            raise ValueError("examples[%d].labels 必须为每个问题提供一个标签" % i)
        for q in spec["questions"]:
            label_index(q, example["labels"][q["id"]])
    return spec


def valid_state(state):
    if isinstance(state, dict):
        return bool(state)
    return isinstance(state, str) and bool(state.strip())


def label_index(q, value):
    qtype, crit = q["t"], q["crit"]
    if qtype == "choice":
        keys = list(crit.keys())
        if not isinstance(value, str) or value not in keys:
            raise ValueError("choice 标签必须是 crit 中的选项 key")
        return keys.index(value)
    if qtype == "noul":
        if not isinstance(value, bool):
            raise ValueError("noul 标签必须是 JSON 布尔值 true 或 false")
        return 1 if value else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= len(crit):
        raise ValueError("score 标签必须是 0 到 %d 的整数" % (len(crit) - 1))
    return value


def build_prompt(spec, count):
    public_spec = {k: v for k, v in spec.items() if k != "examples"}
    return (
        "请按给定业务规范合成训练候选数据。只输出 JSON object，不要 Markdown，形状为 "
        '{"items":[{"state":{},"labels":{},"evidence":{}}]}。\n'
        "本批必须给出恰好 %d 条互不重复的样本。state 应符合规范中的字段和信息边界；覆盖常见、边界、易混淆和缺少关键信息的情形，"
        "但标签必须严格按 labeling_policy，不要为追求类别均衡而违背规则。\n"
        "labels 的键必须恰好等于每道题的 id。choice 值必须是 crit 中的选项 key；noul 值必须是 JSON 布尔值；"
        "score 值必须是从 0 开始的等级整数。不要生成 soft 概率或置信度。"
        "evidence 为每个问题提供一句简短、可核对的文本证据；证据仅供审核，不是正确性的证明。"
        "不要包含个人身份信息、真实客户资料、额外字段或解释性前言。\n\n"
        "任务规范：\n%s\n\n少量示例（只用于理解格式和规则，不要复述或改写示例）：\n%s"
        % (count, json_text(public_spec), json_text(spec.get("examples", [])))
    )


def call_api(api_key, base_url, model, prompt, temperature, max_tokens, timeout):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是遵守标签规范的数据集编写助手。只返回符合要求的 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ValueError("模型输出达到 max_tokens 上限；请调高 --max-tokens 或降低 --batch-size")
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("API 返回内容不是文本 JSON")
            try:
                usage = body.get("usage") or {}
                return json.loads(content), body.get("id", ""), usage
            except json.JSONDecodeError as exc:
                raise ValueError("模型返回内容不是有效 JSON: %s" % exc)
        except urllib.error.HTTPError as exc:
            last_error = "DeepSeek API HTTP %s" % exc.code
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                break
        except urllib.error.URLError as exc:
            last_error = "网络请求失败: %s" % exc.reason
            if attempt == 2:
                break
        time.sleep(2 ** attempt)
    raise RuntimeError(last_error or "DeepSeek API 请求失败")


def make_record(spec, item, model, run_id, row_number, completion_id):
    if not isinstance(item, dict) or not valid_state(item.get("state")):
        raise ValueError("生成项必须含非空对象或字符串 state")
    labels = item.get("labels")
    question_ids = {q["id"] for q in spec["questions"]}
    if not isinstance(labels, dict) or set(labels) != question_ids:
        raise ValueError("labels 的键必须恰好对应 spec 中的全部问题 id")

    qs = []
    for q in spec["questions"]:
        generated_q = {key: copy.deepcopy(q[key]) for key in ("id", "t", "ins", "crit")}
        generated_q["y"] = label_index(q, labels[q["id"]])
        qs.append(generated_q)
    evidence = item.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    evidence = {str(k): v[:500] for k, v in evidence.items() if k in question_ids and isinstance(v, str)}

    record_id = "synthetic-%s-%06d" % (run_id, row_number)
    return {
        "id": record_id,
        "split": "train_candidate",
        "source_group_id": record_id,
        "task_family": spec["task_family"],
        "lang": spec["lang"],
        "state": item["state"],
        "qs": qs,
        "metadata": {
            "policy_version": spec["policy_version"],
            "label_source": "deepseek_pseudo_label",
            "review_status": "needs_human_review",
            "generator_model": model,
            "generation_run_id": run_id,
            "generation_completion_id": completion_id,
            "review_evidence": evidence,
        },
    }


def existing_state_hashes(path):
    hashes = set()
    if not path.exists():
        return hashes
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                hashes.add(json_text(record["state"], sort_keys=True))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError("输出文件第 %d 行无效，无法安全追加: %s" % (line_number, exc))
    return hashes


def main():
    parser = argparse.ArgumentParser(description="用 DeepSeek 生成待审核的 Laya 微调 JSONL 候选数据")
    parser.add_argument("--spec", required=True, help="任务规范 JSON 文件")
    parser.add_argument("--out", default="laya/data_generation/generated/train_candidate.jsonl", help="输出 JSONL 路径")
    parser.add_argument("--count", type=int, default=20, help="本次新增的样本数")
    parser.add_argument("--batch-size", type=int, default=4, help="每次 API 请求生成的样本数，范围 1–20")
    parser.add_argument("--workers", type=int, default=4, help="并发 API 请求数，范围 1–16")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="DeepSeek 模型名；V4.1 Flash 当前为 deepseek-flash")
    parser.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--append", action="store_true", help="输出文件已存在时追加，并跳过重复 state")
    args = parser.parse_args()

    if args.count < 1 or not 1 <= args.batch_size <= 20 or not 1 <= args.workers <= 16:
        parser.error("--count 必须大于 0；--batch-size 范围 1–20；--workers 范围 1–16")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        parser.error("请先将密钥设为 DEEPSEEK_API_KEY 环境变量；不要把密钥写进参数或文件")

    try:
        spec = load_spec(args.spec)
        out_path = Path(args.out)
        if out_path.exists() and not args.append:
            raise ValueError("输出文件已存在；如要续写请显式添加 --append")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        seen_states = existing_state_hashes(out_path) if args.append else set()
        run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        histograms = {q["id"]: Counter() for q in spec["questions"]}
        written = 0
        api_calls = 0
        max_calls = max(3, ((args.count + args.batch_size - 1) // args.batch_size) * 3)
        total_usage = Counter()
        generation_started = time.monotonic()

        while written < args.count and api_calls < max_calls:
            remaining = args.count - written
            request_plan = []
            reserved = 0
            for offset in range(args.workers):
                if reserved >= remaining or api_calls + len(request_plan) >= max_calls:
                    break
                batch_count = min(args.batch_size, remaining - reserved)
                batch_number = api_calls + len(request_plan) + 1
                request_plan.append((batch_number, batch_count))
                reserved += batch_count

            results = []
            errors = []
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                future_map = {}
                for batch_number, batch_count in request_plan:
                    prompt = build_prompt(spec, batch_count)
                    future = pool.submit(
                        call_api, api_key, args.base_url, args.model, prompt,
                        args.temperature, args.max_tokens, args.timeout,
                    )
                    future_map[future] = (batch_number, batch_count)
                for future in as_completed(future_map):
                    batch_number, batch_count = future_map[future]
                    try:
                        result, completion_id, usage = future.result()
                        results.append((batch_number, batch_count, result, completion_id, usage))
                    except Exception as exc:
                        errors.append("批次 %d 失败: %s" % (batch_number, exc))
            api_calls += len(request_plan)

            # Main thread owns de-duplication and file writes; request calls above run concurrently.
            for batch_number, batch_count, result, completion_id, usage in sorted(results):
                total_usage.update({k: v for k, v in usage.items() if isinstance(v, (int, float))})
                items = result.get("items") if isinstance(result, dict) else None
                if not isinstance(items, list) or not items:
                    raise ValueError("API 返回 JSON 必须包含非空 items 数组")
                if len(items) > batch_count:
                    raise ValueError("API 返回样本数超过本批请求数")
                records = [make_record(spec, item, args.model, run_id,
                                       (batch_number - 1) * args.batch_size + i + 1, completion_id)
                           for i, item in enumerate(items)]
                accepted = []
                for record in records:
                    state_key = json_text(record["state"], sort_keys=True)
                    if state_key in seen_states:
                        continue
                    seen_states.add(state_key)
                    accepted.append(record)
                if accepted:
                    with out_path.open("a", encoding="utf-8", newline="\n") as output:
                        for record in accepted:
                            output.write(json_text(record) + "\n")
                        output.flush()
                for record in accepted:
                    written += 1
                    for q, generated_q in zip(spec["questions"], record["qs"]):
                        if q["t"] == "choice":
                            selected = list(q["crit"])[generated_q["y"]]
                        elif q["t"] == "noul":
                            selected = "true" if generated_q["y"] else "false"
                        else:
                            selected = str(generated_q["y"])
                        histograms[q["id"]][selected] += 1
                print("并发批次 %d：新增 %d / %d 条" % (batch_number, written, args.count))
            if errors:
                raise RuntimeError("；".join(errors) + "。已写入成功批次，可用 --append 续跑。")

        print("输出文件：%s" % out_path)
        print("新增样本：%d；重复 state 已跳过；所有新增记录均标记为 needs_human_review。" % written)
        for qid, counts in histograms.items():
            print("%s 标签分布：%s" % (qid, json_text(dict(counts))))
        print("逻辑 API 批次：%d；token 用量：%s" % (api_calls, json_text(dict(total_usage))))
        elapsed = time.monotonic() - generation_started
        print("并发 worker：%d；生成耗时：%.2f 秒；平均速度：%.2f 条/秒" % (
            args.workers, elapsed, written / elapsed if elapsed else 0.0))
        if written < args.count:
            print("达到请求上限但未生成足量唯一样本，可续跑 --append。", file=sys.stderr)
            return 1
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print("生成失败：%s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
