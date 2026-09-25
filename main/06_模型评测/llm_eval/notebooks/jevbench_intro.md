```python
# Cell 0 — Platform detection & dependency install
import sys, os, subprocess, importlib
from pathlib import Path

def detect_platform() -> str:
    if 'google.colab' in sys.modules:
        return 'colab'
    if 'PAI' in os.environ or 'aliyun' in os.environ.get('HOSTNAME', ''):
        return 'aliyun_pai'
    img = os.environ.get('JUPYTER_IMAGE', '').lower()
    if 'modelscope' in img:
        return 'modelscope'
    if 'bml' in os.environ.get('HOSTNAME', '').lower():
        return 'baidu_bml'
    if 'tione' in os.environ.get('HOSTNAME', '').lower():
        return 'tencent_tione'
    return 'jupyter_local'

PLATFORM = detect_platform()
print(f"platform: {PLATFORM}")
print(f"python:   {sys.version.split()[0]}")

# Make sure we run from repo root (notebook lives under notebooks/, but tasks/ is at root).
NOTEBOOK_DIR = Path.cwd().resolve()
for ancestor in [NOTEBOOK_DIR, *NOTEBOOK_DIR.parents]:
    if (ancestor / "pyproject.toml").exists() and (ancestor / "llm_eval").is_dir():
        if ancestor != NOTEBOOK_DIR:
            os.chdir(ancestor)
            print(f"cd -> {ancestor}")
        break

def install(pkg: str, quiet: bool = True) -> None:
    flag = '-q' if quiet else ''
    if PLATFORM == 'colab':
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', flag, pkg])
    else:
        from IPython import get_ipython
        get_ipython().run_line_magic('pip', f'install {flag} {pkg}')

# Install llm_eval from this checkout, and matplotlib for charts.
for pkg, name in [('-e .', 'llm_eval'), ('matplotlib', 'matplotlib')]:
    try:
        m = importlib.import_module(name)
        print(f"  ok: {name} already installed")
    except ImportError:
        print(f"  installing {name}...")
        install(pkg, quiet=True)
        importlib.import_module(name)
        print(f"  ok: {name} installed")

# Matplotlib backend-safe: avoid font warnings on minimal containers.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']
print("matplotlib backend:", matplotlib.get_backend())

```

    platform: jupyter_local
    python:   3.14.6
    cd -> /Users/micheal/knowledgebase/知识/工作区/jev/llm_eval
      ok: llm_eval already installed
      ok: matplotlib already installed
    matplotlib backend: Agg


# Cell 1 — JevBench 入门

## JevBench 入门：结构化决策模型评测

> 25 分钟从"听过 JevBench"走到"我的 API 已经跑出第一份结果并读懂"。

**JevBench** 是一个专门评测**结构化决策模型**的基准测试，对应 *"typed decision model"* 这种用法：
给定一段事实 (state) 和受限于固定选项集 (rubric + label set)，模型必须返回对**精确选项集**的概率分布——
不写自由文本，不做文字解释。

### 这个 notebook 给谁看

| 你想做的事 | 你应该看 |
|---|---|
| 理解 JevBench 是什么 / 不是什么 | Cell 1–3, 5, 7 |
| 不消耗 API 跑通流程 | Cell 0–9, 13 |
| 用自己的 API 实测 | Cell 10–12 |
| 同时测多个模型对比 | Cell 12 + 14 |
| 接入 Colab / 魔搭 / 阿里云 PAI | Cell 0 (auto-detect) |

### 默认 zero-cost

- **所有示例用 `mock` adapter**，不需要任何 API key。
- **Cell 12 才是真实 API 调用**——它会自动检测你 `export` 了哪些 key，没 key 时优雅跳过。
- **不会写你的 key 进任何文件**，也不会 echo 到日志。

按 Shift+Enter 一路往下跑就行。

# Cell 2 — 什么是 JevBench

## 什么是 JevBench

JevBench 评测的不是"模型有多能说"，而是"模型能不能稳定地做**对固定选项集的判定**"。
它围绕五条互相约束的轴：

| 轴 | 关心什么 | 典型问题 |
|---|---|---|
| **smart** | 答得对不对 | accuracy、Brier、ECE、calibration |
| **cheap** | 跑一次判定多少钱 | $/1k decisions (按 provider 自报 tariff × 实际 token) |
| **fast** | 多快 | p50 / p95 端到端延迟（含网络） |
| **reliable** | 输出能不能信任 | schema_validity、paraphrase consistency、置信度可不可信 |
| **open** | 权重 / 代码能不能用 | 三项独立事实：代码 license、权重是否可下、权重 license |

合成方式（v1.3）：**JevBench Score = 几何平均(Intelligence 30%, Calibration 25%, Speed 25%, Cost 25%)**，Intelligence < 50 时按 `(I/50)²` 折扣。

### 六族题

| 族 | 任务 |
|---|---|
| `routing` | 客服请求分发 |
| `adequacy` | 答案合格度判定 |
| `policy` | yes/no 合规检查 |
| `intent` | 意图分类 |
| `ordinal` | 严重度评分 |
| `extraction` | 字段抽取 |

### 它跟 MMLU / LMSYS / HELM 的区别

- **MMLU**: 多选题，正确率单维度。
- **LMSYS Arena**: 聊天偏好，人类投票。
- **HELM**: 多维度横扫，但偏学术 benchmark。
- **JevBench**: 唯一**专为"输出必须是结构化概率分布"的模型**设计，并把**延迟和成本**作为一等公民。

当你的业务需要的是"判定 + 概率"而不是"对话 + 推理"时，JevBench 是更直接的对照表。

# Cell 3 — 为什么需要专门的决策模型评测

## 为什么需要专门的决策模型评测

很多生产场景要的**不是聊天，而是判定**：

- 客服请求路由到哪个部门
- 答案合格度评分（生成式模型的输出质量门控）
- 内容是否合规的 yes/no 判定
- 用户的真实意图分类
- 工单严重度 0–3 打分
- 字段抽取（订单号 / 地址 / 金额）

把这些场景硬塞给通用 LLM 的"自由文本回答"，下游就得做正则解析、做边界 case、做错误恢复——**而且得不到 calibration**。
`{A: 0.7, B: 0.2, C: 0.1}` 这种概率分布天然适合：
- 阈值化决策（argmax）
- 拒绝 / 转人工（低置信度）
- 集成 / 串行 / 多模型仲裁

但**"让通用 LLM 写出一个合法的概率分布"和"模型原生支持这种 API"是两件事**。
JevBench 把这件事显式分开：
- `native` 分布：模型 API 本身就给概率分布（TypeSafe 的 Jev、djev、kev 等）
- `verbalized` 分布：让通用 LLM 用 JSON schema 写出来（精度和稳定性都吃亏）

跑同一份题，两类模型得分能直接对比。


```python
# Cell 4 — 环境自检
import sys, importlib

print("Python:", sys.version.split()[0])

required = [
    ("llm_eval", "the benchmark harness we built"),
    ("matplotlib", "for charts"),
    ("json", "stdlib, but just confirming"),
]
missing = []
for name, desc in required:
    try:
        m = importlib.import_module(name)
        v = getattr(m, "__version__", "stdlib")
        print(f"  ✓ {name:12s} {v}  ({desc})")
    except ImportError:
        missing.append(name)
        print(f"  ✗ {name:12s} MISSING  ({desc})")

if missing:
    print("\nFix: re-run cell 0 (it installs llm_eval and matplotlib from this checkout).")
else:
    print("\nAll required packages present.")

```

    Python: 3.14.6
      ✓ llm_eval     0.1.0  (the benchmark harness we built)
      ✓ matplotlib   3.11.2  (for charts)
      ✓ json         2.0.9  (stdlib, but just confirming)
    
    All required packages present.


# Cell 5 — 本框架的结构

## 本框架 (`llm_eval`) 的结构

```
llm_eval/
├── task.py          题目 dataclass + 校验 + 哈希
├── scorer.py        分布校验 + argmax + Brier + MAE（fail-closed）
├── metrics.py       aggregate：accuracy / brier / ece / 延迟 / cost / paraphrase
├── ledger.py        fcntl 文件锁 + append-only 预算 ledger
├── runner.py        串行驱动 adapter；401/429/连续错停跑
├── summarize.py     public_export() 重算 + 白名单
├── multi_config.py  JSON 多 runner 配置加载
├── multi_runner.py  多 runner 编排
├── compare.py       跨模型汇总表
├── cli.py           run / summarize / multi-run / compare 4 个子命令
└── adapters/        各家 API 的薄壳
        base.py            AdapterError + HTTP helper
        openai_compat.py   OpenAI 兼容 API 的通用实现
        deepseek.py / qwen.py / glm.py / moonshot.py / doubao.py / stepfun.py / xiaomi.py
        mock.py            不消耗 API 的伪响应（always right / uniform）
tasks/
├── smoke.jsonl                      6 题（1 paraphrase 对）
└── public/{easy,original,hard}.jsonl   JevBench v1.2 MIT 公开题 231 道
multi_run.example.json               多 runner 配置模板
tests/                              63 个单元测试
```

设计纪律（也写在 `IMPLEMENTATION.md` 里）：
- **不重试、不重映射、不修补**坏的响应
- **reserve-before / settle-after** 真实计费
- **公共导出** = 白名单 + 重算，永不 echo raw request / response
- **adapter 内部串行**——并发只在 notebook 这层做（cell 12）


```python
# Cell 6 — 浏览题库
from pathlib import Path
from collections import Counter

import llm_eval
from llm_eval.task import load_tasks

repo = Path.cwd()
print(f"repo root: {repo}\n")

print("=== task files ===")
for p in sorted((repo / "tasks").rglob("*.jsonl")):
    rel = p.relative_to(repo)
    n = sum(1 for _ in p.open())
    print(f"  {rel}  ({n} tasks)")

print("\n=== load public_all.jsonl (231 tasks) ===")
tasks = load_tasks(repo / "tasks" / "public_all.jsonl")
print(f"loaded: {len(tasks)}")

by_family = Counter(t.family for t in tasks)
by_topic = Counter(t.topic for t in tasks)
by_qtype = Counter(t.question_type for t in tasks)

print("\nby family:")
for k, v in sorted(by_family.items(), key=lambda kv: -kv[1]):
    print(f"  {k:14s} {v:3d}")

print("\nby topic:")
for k, v in sorted(by_topic.items(), key=lambda kv: -kv[1]):
    print(f"  {k:18s} {v:3d}")

print("\nby question_type:")
for k, v in sorted(by_qtype.items(), key=lambda kv: -kv[1]):
    print(f"  {k:8s} {v:3d}")

# Show 2 full records: one easy + one hard (per PRD §C)
print("\n=== sample 1 (easy: intent classification) ===")
easy = next(t for t in tasks if t.family == "intent" and t.question_type == "choice")
import json
print(json.dumps(easy.to_dict(), indent=2, ensure_ascii=False))

print("\n=== sample 2 (hard: long policy reasoning) ===")
hard = next(t for t in tasks if "long_policy" in t.id)
sample = hard.to_dict()
sample["state"] = {**sample["state"], "text": sample["state"].get("text", "")[:200] + "...[truncated for display]"}
print(json.dumps(sample, indent=2, ensure_ascii=False))

```

    repo root: /Users/micheal/knowledgebase/知识/工作区/jev/llm_eval
    
    === task files ===
      tasks/public/easy.jsonl  (48 tasks)
      tasks/public/hard.jsonl  (111 tasks)
      tasks/public/original.jsonl  (72 tasks)
      tasks/public_all.jsonl  (231 tasks)
      tasks/smoke.jsonl  (6 tasks)
    
    === load public_all.jsonl (231 tasks) ===
    loaded: 231
    
    by family:
      intent          24
      extraction      24
      long_policy     19
      multi_hop       18
      judge_hard      17
      temporal_numeric  15
      fact            12
      tool_selection  12
      policy          12
      ordinal         12
      adequacy        12
      routing         12
      probability     10
      trap             8
      ambiguous        7
      tradeoff         6
      adversarial      6
      routing_hard     5
    
    by topic:
                         135
      everyday            36
      coding              24
      support_ops         24
      rules_law           12
    
    by question_type:
      choice   139
      noul      74
      score     18
    
    === sample 1 (easy: intent classification) ===
    {
      "id": "easy-intent-00",
      "family": "intent",
      "question_type": "choice",
      "instructions": "Which intent does the user's message express?",
      "state": {
        "text": "Where is my package? I ordered it last week and it still hasn't arrived."
      },
      "labels": [
        "track_order",
        "cancel_order",
        "change_address",
        "report_damage",
        "billing_question"
      ],
      "expected": "track_order",
      "criteria": {
        "billing_question": "Asks about a charge, invoice or payment",
        "cancel_order": "Wants to cancel an order",
        "change_address": "Wants to change the delivery address",
        "report_damage": "Received an item that is broken or damaged",
        "track_order": "Wants to know where an order is or when it arrives"
      },
      "split": "public",
      "group": null,
      "provenance": "JevBench v1.1 easy tier, original authored item",
      "topic": "everyday"
    }
    
    === sample 2 (hard: long policy reasoning) ===
    {
      "id": "hard-opus-a-long_policy-01",
      "family": "long_policy",
      "question_type": "choice",
      "instructions": "Acting as the coverage reviewer, decide how the building water-damage portion of claim HX-2026-118804 must be settled under the policy form and the endorsements attached to the current term.",
      "state": {
        "text": "HARBORLINE MUTUAL INSURANCE COMPANY\nHOMEOWNERS POLICY FORM HM-3 (EDITION 04/2023) — EXCERPTS, ENDORSEMENTS AND CLAIM FILE HX-2026-118804\nPrepared for coverage review. Page numbers omitted. Bracketed n...[truncated for display]"
      },
      "labels": [
        "deny_vacancy_exclusion",
        "deny_repeated_seepage",
        "pay_subject_to_10000_sublimit",
        "pay_subject_to_15000_sublimit",
        "pay_full_estimate_less_deductible"
      ],
      "expected": "pay_subject_to_15000_sublimit",
      "criteria": {
        "deny_repeated_seepage": "The building water damage is excluded as repeated seepage or leakage (Exclusion 4.3) with no exception applying.",
        "deny_vacancy_exclusion": "The building water damage is excluded because the dwelling was vacant for more than 60 consecutive days before the loss (Exclusion 4.7).",
        "pay_full_estimate_less_deductible": "The loss is covered without any sublimit; the full estimate is paid after deducting the $1,000 deductible.",
        "pay_subject_to_10000_sublimit": "The loss is covered but payment is capped by the concealed-water sublimit of $10,000.",
        "pay_subject_to_15000_sublimit": "The loss is covered but payment is capped by the concealed-water sublimit of $15,000."
      },
      "split": "public",
      "group": "hard-opus-a-long_policy-01",
      "provenance": "JevBench v1.2 hard tier (original authored scenario)",
      "topic": ""
    }


# Cell 7 — 9 个指标

## JevBench 评测什么 — 9 个指标

| 指标 | 范围 | 一句话解释 |
|---|---|---|
| **accuracy** | [0, 1] | 模型 argmax 答对的比例。对照 `majority_class_accuracy` 才有意义（不然 60% 看起来不错，但永远选 `yes` 就是 82%）。 |
| **`majority_class_accuracy`** | [0, 1] | 永远选最高频 label 能拿多少分。每个 family 都有偏斜（adequacy 是 82%），accuracy 必须对照这个下限读。 |
| **`schema_validity`** | [0, 1] | 响应能被解析成合法概率分布的比例。**headline 容忍度 2%**（允许 `0.999` 这种舍入误差）。 |
| **`schema_validity_strict`** | [0, 1] | 冻结的 1e-3 容忍度。两个都报：headline 容忍度 vs 严格数字。 |
| **Brier** | [0, 2] | 多类 `Σ (p_k − y_k)²`；二元题用 2-class 约定让数字可比。**越低越好**。 |
| **ECE** | [0, 1] | 期望校准误差。10 个等宽 bin 按 top-label 置信度分；空 bin 缺席而非 0。**越低越好**。 |
| **`ordinal_mae`** | [0, N−1] | 序数题上概率加权期望值 vs 参考 level 的 MAE。和 argmax accuracy 是**两个不同预测**，同时报。 |
| **`paraphrase_consistency`** | [0, 1] | 同一题的两种问法：(a) 答得一样、(b) 都答对。**两个都报**——只报"答得一样"会让"两个都错"的高分。 |
| **latency p50 / p95** | seconds | 端到端延迟（含网络）。首个请求单独报，scale-to-zero 端点把冷启动算在第一个头上。 |
| **cost** | USD / 1k decisions | `derived_usage_times_tariff`（实测 token × provider 自报 tariff）。无计费账户写 `null` + 显式 basis 标签（如 `no_billable_account_public_endpoint`）。**单位是"每千次判定"，不是每千 token**。 |

每个指标的代码实现在：
- `llm_eval/scorer.py` — 单题打分（含分布校验、argmax、Brier、MAE）
- `llm_eval/metrics.py` — 聚合（ECE 10-bin、paraphrase consistency、latency p50/p95、cost）
- `llm_eval/summarize.py` — 公共导出白名单 + 重算


```python
# Cell 8 — 第一次跑：mock + smoke
import os, json
from pathlib import Path

import llm_eval
from llm_eval.adapters import get_adapter
from llm_eval.runner import run
from llm_eval.summarize import public_export
from llm_eval.task import load_tasks

# 输出统一落在 runs/notebook-demo/
OUT_ROOT = Path("runs/notebook-demo/smoke")
OUT_ROOT.mkdir(parents=True, exist_ok=True)

tasks = load_tasks("tasks/smoke.jsonl")
adapter = get_adapter(name="mock")  # default: 永远答对，confident

results = run(
    tasks=tasks,
    adapter=adapter,
    ledger_path=str(OUT_ROOT / "ledger.jsonl"),
    cap_usd=1.0,
    out_path=str(OUT_ROOT / "results.jsonl"),
    raw_dir=str(OUT_ROOT / "raw"),
    price_in_per_m=0.0,    # mock 免费
    price_out_per_m=0.0,
    delay_s=0.0,
    max_input_tokens=2000,
    max_output_tokens=200,
)

summary = public_export(results, tasks, run_meta={"cell": 8, "adapter": "mock"})
with open(OUT_ROOT / "summary.json", "w") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"completed: {len(results)} tasks")
print(f"output:    {OUT_ROOT}")
print(f"  - results.jsonl   ({len(results)} records)")
print(f"  - summary.json    (public-safe aggregate)")
print(f"  - ledger.jsonl    (cost events)")
print(f"  - raw/*.json      ({len(list((OUT_ROOT/'raw').iterdir()))} raw req/resp bodies)")

```

    completed: 6 tasks
    output:    runs/notebook-demo/smoke
      - results.jsonl   (6 records)
      - summary.json    (public-safe aggregate)
      - ledger.jsonl    (cost events)
      - raw/*.json      (6 raw req/resp bodies)



```python
# Cell 9 — 读懂 summary.json
import json

summary = json.load(open("runs/notebook-demo/smoke/summary.json"))

# 白话注释
field_notes = {
    "n_tasks": "题目总数",
    "n_scorable": "有 expected label 可打分的题数（= n_tasks 当全部题都有 expected）",
    "accuracy": "模型答对的比例",
    "majority_class_accuracy": "永远选最高频 label 的下限（baseline）",
    "schema_validity": "headline 容忍度（2%）下合法的比例",
    "schema_validity_strict": "严格容忍度（1e-3）下合法的比例",
    "brier": "校准损失，越低越好",
    "ece": "期望校准误差，越低越好",
    "ordinal_mae": "序数题的概率加权 MAE",
    "p50_s": "中位数延迟",
    "p95_s": "P95 延迟",
    "cost_usd_total": "总成本（USD）",
    "paraphrase_consistency": "paraphrase 对的同答 / 都对率",
    "per_family": "按 family 拆分的 accuracy",
    "per_topic": "按 topic 拆分的 accuracy",
    "run_meta": "本轮运行的元数据",
}

print(f"{'key':30s} {'value':20s}  note")
print("-" * 90)
for k in ["n_tasks", "n_scorable", "accuracy", "majority_class_accuracy",
         "schema_validity", "schema_validity_strict", "brier", "ece",
         "ordinal_mae", "p50_s", "p95_s", "cost_usd_total"]:
    v = summary.get(k)
    if isinstance(v, float):
        vstr = f"{v:.4f}"
    else:
        vstr = str(v)
    note = field_notes.get(k, "")
    print(f"{k:30s} {vstr:20s}  {note}")

print()
print("per_family:")
for fam, v in sorted(summary.get("per_family", {}).items()):
    print(f"  {fam:14s} n={v['n']:3d}  acc={v['accuracy']:.4f}")

print()
print("per_topic:")
for top, v in sorted(summary.get("per_topic", {}).items()):
    print(f"  {top:18s} n={v['n']:3d}  acc={v['accuracy']:.4f}")

print()
print("paraphrase_consistency:", summary.get("paraphrase_consistency"))

```

    key                            value                 note
    ------------------------------------------------------------------------------------------
    n_tasks                        6                     题目总数
    n_scorable                     6                     有 expected label 可打分的题数（= n_tasks 当全部题都有 expected）
    accuracy                       1.0000                模型答对的比例
    majority_class_accuracy        0.6667                永远选最高频 label 的下限（baseline）
    schema_validity                1.0000                headline 容忍度（2%）下合法的比例
    schema_validity_strict         1.0000                严格容忍度（1e-3）下合法的比例
    brier                          0.0000                校准损失，越低越好
    ece                            0.0000                期望校准误差，越低越好
    ordinal_mae                    0.0000                序数题的概率加权 MAE
    p50_s                          0.0550                中位数延迟
    p95_s                          0.0551                P95 延迟
    cost_usd_total                 None                  总成本（USD）
    
    per_family:
      intent         n=  3  acc=1.0000
      ordinal        n=  1  acc=1.0000
      policy         n=  2  acc=1.0000
    
    per_topic:
      everyday           n=  3  acc=1.0000
      rules_law          n=  2  acc=1.0000
      support_ops        n=  1  acc=1.0000
    
    paraphrase_consistency: {'pairs': 1, 'both_answered_valid': 1, 'both_correct': 1, 'unscorable_expected_none': 0, 'consistency': 1.0}


# Cell 10 — 接真实模型：环境准备

## 接真实模型：环境准备

### 两种方式提供 key（任选其一）

#### A. 直接在 cell 11 粘贴（**仅学习用，最方便**）

打开 cell 11，把你的 key 填进 `direct_keys` 字典。**注意**：填了的 key 会保存到 `.ipynb` 文件里，请勿把含 key 的 notebook 提交到 git 或分享给他人。

#### B. 用环境变量（**生产 / 共享场景**）

```bash
export DEEPSEEK_API_KEY="sk-..."          # DeepSeek
export DASHSCOPE_API_KEY="sk-..."         # 阿里百炼 / Qwen
export ZHIPU_API_KEY="..."                # 智谱 GLM
export MOONSHOT_API_KEY="sk-..."          # Moonshot Kimi
export ARK_API_KEY="..."                  # 字节豆包 / 火山方舟
export STEPFUN_API_KEY="..."              # 阶跃星辰
export XIAOMI_API_KEY="..."               # 小米 MiMo
```

Cell 11 自动检测两路来源，**A 优先于 B**。

### 安全纪律

- **Cell 11 顶部有红色警告**——粘贴 key 前请先读。
- **Cell 11 / 12 不 echo key**——检测结果只显示"set / not set"。
- **cap_usd 限制**：`LBEVAL_CAP_USD`（默认 0.30/provider）防止意外爆额度。
- **并发上限**：`LBEVAL_MAX_WORKERS`（默认 5）；超过 5 个 key 时 cell 12 会分批提示。
- **如果用了 A 方式**，运行前 `git diff notebooks/` 应该**没有**新增内容（`notebooks/*_executed.ipynb` 已在 .gitignore 里，但 canonical `.ipynb` 没有）。

### 跑哪一档

cell 12 默认跑 `tasks/public/easy.jsonl`（48 题），成本约 $0.001–$0.05/provider。
如果你想跑全部 231 题，改 cell 12 里的 `tasks_path` 到 `tasks/public_all.jsonl`。



```python
# Cell 11 — 检查 & 配置 API key

# ┌─────────────────────────────────────────────────────────────────────────┐
# │ ⚠️  DANGER ZONE — 明文 key 粘贴区（仅学习用！）                          │
# ├─────────────────────────────────────────────────────────────────────────┤
# │ 在这里直接填 key 会保存到 .ipynb 文件里。请勿：                          │
# │   ✗ 把含 key 的 notebook commit 到 git                                  │
# │   ✗ 把含 key 的 notebook 截图 / 拷贝给他人                              │
# │   ✗ 把 notebook 上传到任何公开 / 第三方平台                              │
# │                                                                          │
# │ 学习完成后请把这里填的 key 删干净，并清空 outputs：                       │
# │   菜单 → Cell → All Output → Clear  (Jupyter)                          │
# │   菜单 → Edit → Clear All Outputs  (VS Code)                           │
# └─────────────────────────────────────────────────────────────────────────┘

# 6 个当前可用的 provider（按你给的 key 列表）
direct_keys = {
    "MOONSHOT_API_KEY":  "",   # kimi k3（直连）
    "DEEPSEEK_API_KEY":  "",   # deepseek-flash（直连）
    "ZHIPU_API_KEY":     "",   # glm5.3 codeplan
    "ARK_API_KEY":       "",   # doubao 2.1 pro（直连）
    "STEPFUN_API_KEY":   "",   # step5 codingplan
    "XIAOMI_API_KEY":    "",   # mimo（直连）
}

# ┌──────────────────────────────────────────────────────────────────────────┐
# │ ↑ 替换上面的空字符串为你的 key，例如：                                    │
# │    "MOONSHOT_API_KEY":  "sk-...",                                       │
# │    "DEEPSEEK_API_KEY":  "sk-...",                                        │
# │    "ZHIPU_API_KEY":     "...",   # codeplan 的 key 通常和官方 key 同形    │
# │    "ARK_API_KEY":       "...",   # 火山方舟 key                          │
# │    "STEPFUN_API_KEY":   "...",   # 阶跃星辰 codingplan key              │
# │    "XIAOMI_API_KEY":    "...",                                          │
# └──────────────────────────────────────────────────────────────────────────┘

# ┌──────────────────────────────────────────────────────────────────────────┐
# │ base_url 覆盖区（直连 / Coding Plan 任选其一）───                       │
# ├──────────────────────────────────────────────────────────────────────────┤
# │ 留空 = 用 provider 官方默认地址                                          │
# │ Coding Plan / 中转站用户：在对应 key_env 的位置同时填 base_url          │
# │                                                                          │
# │ ⚠️  ZHIPU_API_KEY 和 STEPFUN_API_KEY 走 codingplan 时，                  │
# │     端点 URL 与"直连"不同。把下面两行取消注释，并填你的 codingplan 端点 │
# └──────────────────────────────────────────────────────────────────────────┘

base_url_overrides = {
    # 官方直连 URL（默认值，可不填）：
    "MOONSHOT_API_KEY": "https://api.moonshot.cn/v1",
    "DEEPSEEK_API_KEY": "https://api.deepseek.com/v1",
    "ARK_API_KEY":      "https://ark.cn-beijing.volces.com/api/v3",
    "XIAOMI_API_KEY":   "https://api.xiaomi.com/v1",  # placeholder
    # ↓ 如果你的 codingplan 端点和直连不同，把下面这两行的 # 去掉并填：
    # "ZHIPU_API_KEY":  "https://your-glm-codeplan-endpoint.com/v1",
    # "STEPFUN_API_KEY": "https://your-step-codeplan-endpoint.com/v1",
}

import os

# 合并 key：direct_keys > env var
effective = {}
for k, v in direct_keys.items():
    effective[k] = v if v else os.environ.get(k, "")

# 合并 base_url：base_url_overrides > env var _BASE_URL > 默认
def resolve_base_url(key_env: str, default_url: str) -> str:
    override = base_url_overrides.get(key_env, "")
    if override:
        return override
    env_url = os.environ.get(key_env + "_BASE_URL", "")
    if env_url:
        return env_url
    return default_url

# 当前 6 个 provider 配置
PROVIDER_TABLE = [
    {"name": "deepseek-flash",    "adapter": "deepseek", "model": "deepseek-flash",
     "key_env": "DEEPSEEK_API_KEY",
     "default_base_url": "https://api.deepseek.com/v1",
     "price_in_per_m": 0.27,  "price_out_per_m": 1.10,
     "notes": "deepseek（直连）"},
    {"name": "kimi-k3",          "adapter": "moonshot", "model": "kimi-k3",
     "key_env": "MOONSHOT_API_KEY",
     "default_base_url": "https://api.moonshot.cn/v1",
     "price_in_per_m": 0.10,  "price_out_per_m": 0.30,  # K3 价格待官方确认
     "notes": "kimi k3（直连）"},
    {"name": "glm-5.3-codeplan", "adapter": "glm",      "model": "glm-5.3",
     "key_env": "ZHIPU_API_KEY",
     "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
     "price_in_per_m": 0.50,  "price_out_per_m": 0.50,  # codeplan 价格待校准
     "notes": "glm5.3 codeplan"},
    {"name": "doubao-2.1-pro",    "adapter": "doubao",   "model": "doubao-2.1-pro",
     "key_env": "ARK_API_KEY",
     "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
     "price_in_per_m": 0.80,  "price_out_per_m": 1.00,  # 20 元 plan 的 token 价，待校准
     "notes": "doubao 2.1 pro（20 元 plan，直连）"},
    {"name": "step-5-codeplan",  "adapter": "stepfun",  "model": "step-5",
     "key_env": "STEPFUN_API_KEY",
     "default_base_url": "https://api.stepfun.com/v1",
     "price_in_per_m": 1.00,  "price_out_per_m": 2.00,  # codingplan 价格待校准
     "notes": "step5 codingplan"},
    {"name": "mimo",             "adapter": "xiaomi",   "model": "mimo",
     "key_env": "XIAOMI_API_KEY",
     "default_base_url": "https://api.xiaomi.com/v1",  # placeholder
     "price_in_per_m": None,  "price_out_per_m": None,
     "notes": "mimo（直连）"},
]

# 计算 effective base_url
for p in PROVIDER_TABLE:
    p["base_url"] = resolve_base_url(p["key_env"], p["default_base_url"])

print(f"{'provider':22s} {'key':6s} {'source':8s} {'base_url':50s}")
print('-' * 95)
for p in PROVIDER_TABLE:
    val = effective.get(p["key_env"], "")
    has = bool(val)
    mark = "✓" if has else "✗"
    src = "pasted" if direct_keys.get(p["key_env"]) else ("env" if os.environ.get(p["key_env"]) else "-")
    url_short = p["base_url"]
    if len(url_short) > 48:
        url_short = url_short[:45] + "..."
    note = p.get("notes", "")
    print(f"  {mark}  {p['name']:20s} {('set' if has else '-'):6s} {src:8s} {url_short:50s} {note}")

MAX = int(os.environ.get("LBEVAL_MAX_WORKERS", "5"))
CAP = os.environ.get("LBEVAL_CAP_USD", "1.50")
print(f"\nLBEVAL_MAX_WORKERS = {MAX} (cell 12 will batch if more keys are detected)")
print(f"LBEVAL_CAP_USD      = {CAP} (per-provider budget cap; default 1.50 for full benchmark)")

# 安全检查：如果用了 pasted 方式，提醒一次
any_pasted = any(direct_keys.values())
if any_pasted:
    print("\n⚠️  You have pasted plaintext keys above. Remember:")
    print("    - Do NOT commit this notebook if it has keys filled in")
    print("    - Do NOT share or upload this notebook")
    print("    - Clear outputs and remove keys before saving")

```

    provider               key    source   base_url                                          
    -----------------------------------------------------------------------------------------------
      ✗  deepseek-flash       -      -        https://api.deepseek.com/v1                        deepseek（直连）
      ✗  kimi-k3              -      -        https://api.moonshot.cn/v1                         kimi k3（直连）
      ✗  glm-5.3-codeplan     -      -        https://open.bigmodel.cn/api/paas/v4               glm5.3 codeplan
      ✗  doubao-2.1-pro       -      -        https://ark.cn-beijing.volces.com/api/v3           doubao 2.1 pro（20 元 plan，直连）
      ✗  step-5-codeplan      -      -        https://api.stepfun.com/v1                         step5 codingplan
      ✗  mimo                 -      -        https://api.xiaomi.com/v1                          mimo（直连）
    
    LBEVAL_MAX_WORKERS = 5 (cell 12 will batch if more keys are detected)
    LBEVAL_CAP_USD      = 1.50 (per-provider budget cap; default 1.50 for full benchmark)



```python
# Cell 12 — 跑真模型：并行所有可用 provider（≤5 一批，跑全量 benchmark）
import os, sys, time, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from IPython.display import display, Markdown

import llm_eval
from llm_eval.adapters import get_adapter
from llm_eval.multi_config import MultiRunConfig, RunnerConfig
from llm_eval.multi_runner import run_multi
from llm_eval.task import load_tasks

# PROVIDER_TABLE 复用 cell 11 的（含 base_url / price 等字段）。
# 如果你直接执行本 cell 而跳过了 cell 11，下面有一份简化副本（不会自动用粘贴 key）。
if "PROVIDER_TABLE" not in globals():
    PROVIDER_TABLE = [
        {"name": "deepseek-flash",    "adapter": "deepseek", "model": "deepseek-flash",
         "key_env": "DEEPSEEK_API_KEY",
         "default_base_url": "https://api.deepseek.com/v1",
         "price_in_per_m": 0.27, "price_out_per_m": 1.10},
        {"name": "kimi-k3",          "adapter": "moonshot", "model": "kimi-k3",
         "key_env": "MOONSHOT_API_KEY",
         "default_base_url": "https://api.moonshot.cn/v1",
         "price_in_per_m": 0.10, "price_out_per_m": 0.30},
        {"name": "glm-5.3-codeplan", "adapter": "glm",      "model": "glm-5.3",
         "key_env": "ZHIPU_API_KEY",
         "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
         "price_in_per_m": 0.50, "price_out_per_m": 0.50},
        {"name": "doubao-2.1-pro",    "adapter": "doubao",   "model": "doubao-2.1-pro",
         "key_env": "ARK_API_KEY",
         "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
         "price_in_per_m": 0.80, "price_out_per_m": 1.00},
        {"name": "step-5-codeplan",  "adapter": "stepfun",  "model": "step-5",
         "key_env": "STEPFUN_API_KEY",
         "default_base_url": "https://api.stepfun.com/v1",
         "price_in_per_m": 1.00, "price_out_per_m": 2.00},
        {"name": "mimo",             "adapter": "xiaomi",   "model": "mimo",
         "key_env": "XIAOMI_API_KEY",
         "default_base_url": "https://api.xiaomi.com/v1",
         "price_in_per_m": None, "price_out_per_m": None},
    ]
    # fallback base_url
    for p in PROVIDER_TABLE:
        p.setdefault("base_url", p["default_base_url"])

MAX_PARALLEL = min(int(os.environ.get("LBEVAL_MAX_WORKERS", "5")), 5)
CAP_USD = float(os.environ.get("LBEVAL_CAP_USD", "1.50"))
TASKS_PATH = os.environ.get("LBEVAL_TASKS_PATH", "tasks/public_all.jsonl")  # 231 题全量

OUT_ROOT = Path("runs/notebook-demo/real")
OUT_ROOT.mkdir(parents=True, exist_ok=True)

# 加载 tasks 用于预估成本 + 真实 token 校验
all_tasks = load_tasks(TASKS_PATH)
n_tasks = len(all_tasks)
print(f"benchmark: {TASKS_PATH}  ({n_tasks} tasks)")
print(f"  estimated per-provider cost (input tokens × price):")
for p in PROVIDER_TABLE:
    if p["price_in_per_m"] is not None:
        est_in = n_tasks * 1500 * p["price_in_per_m"] / 1e6
        est_out = n_tasks * 50 * (p["price_out_per_m"] or 0) / 1e6
        print(f"    {p['name']:18s}  ~${est_in + est_out:.4f}  (in {est_in:.4f} + out {est_out:.4f})")

# Key 来源合并：cell 11 的 `direct_keys` 优先，回退到 env var
_effective_keys = {}
_effective_base_urls = {}
if "direct_keys" in globals():
    for k, v in direct_keys.items():
        _effective_keys[k] = v if v else os.environ.get(k, "")
    _base_url_overrides = globals().get("base_url_overrides", {})
else:
    for p in PROVIDER_TABLE:
        _effective_keys[p["key_env"]] = os.environ.get(p["key_env"], "")

# base_url：cell 11 优先 / env var <KEY>_BASE_URL 次之 / 默认最后
def _resolve_base_url(p: dict) -> str:
    if "base_url_overrides" in globals():
        ov = _base_url_overrides.get(p["key_env"], "")
        if ov:
            return ov
    env_url = os.environ.get(p["key_env"] + "_BASE_URL", "")
    if env_url:
        return env_url
    return p.get("default_base_url", p.get("base_url", ""))

# Step 1 — 扫可用 provider
available = []
for p in PROVIDER_TABLE:
    if _effective_keys.get(p["key_env"]):
        p["base_url"] = _resolve_base_url(p)
        available.append(p)

print(f"\ndetected {len(available)} provider(s) with keys:")
for p in available:
    print(f"  ✓  {p['name']:18s}  base_url={p['base_url']}")
print(f"max parallel: {MAX_PARALLEL}   cap_usd/provider: ${CAP_USD}   tasks: {n_tasks}\n")

if not available:
    display(Markdown(
        "⚠️ **No API keys available.**\n\n"
        "Two ways to provide keys:\n\n"
        "**A. Paste directly in cell 11** (`direct_keys` dict) — convenient for learning, "
        "but the key is saved into this notebook file.\n\n"
        "**B. `export DEEPSEEK_API_KEY=...` in your shell** before launching Jupyter — "
        "safer for production.\n\n"
        "Without keys, all subsequent comparison charts (cell 14) fall back to the mock data from cell 13."
    ))
else:
    # Step 2 — 分批
    def chunked(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]
    batches = list(chunked(available, MAX_PARALLEL))

    all_runs = []
    for batch_idx, batch in enumerate(batches):
        print(f"\n=== batch {batch_idx+1}/{len(batches)}: {[p['name'] for p in batch]} ===")

        def run_one(spec):
            try:
                cfg = MultiRunConfig(
                    run_id=f"cell12-{spec['name']}",
                    tasks_path=TASKS_PATH,
                    runners=[RunnerConfig(
                        name=spec["name"], adapter=spec["adapter"], model=spec["model"],
                        key_env="",   # 我们用 os.environ 注入
                        price_in_per_m=spec["price_in_per_m"],
                        price_out_per_m=spec["price_out_per_m"],
                        skip_if_done=True,
                    )],
                    cap_usd=CAP_USD,
                    delay_s=0.3,
                    out_root=str(OUT_ROOT / "_tmp"),
                )
                # 注入 key 与 base_url
                os.environ[spec["key_env"]] = _effective_keys[spec["key_env"]]
                # base_url 通过 env var KEY_BASE_URL 注入（adapter factory 看 endpoint 参数）
                # multi_runner → adapter get_adapter 用 endpoint=（如果提供）
                # 我们临时 monkey-patch PROVIDERS 来覆盖 base_url
                from llm_eval.adapters import PROVIDERS as _PROVIDERS
                original = _PROVIDERS.get(spec["adapter"], {}).get("base_url")
                if original and spec["base_url"] != original:
                    _PROVIDERS.setdefault(spec["adapter"], {})["base_url"] = spec["base_url"]
                try:
                    manifest = run_multi(cfg)
                finally:
                    if not (direct_keys.get(spec["key_env"]) if "direct_keys" in globals() else False):
                        os.environ.pop(spec["key_env"], None)
                    if original and spec["base_url"] != original:
                        _PROVIDERS[spec["adapter"]]["base_url"] = original
                return (spec["name"], "ok", manifest)
            except Exception as e:
                return (spec["name"], "error", repr(e))

        with ThreadPoolExecutor(max_workers=len(batch)) as ex:
            futures = [ex.submit(run_one, p) for p in batch]
            for fut in futures:
                name, status, payload = fut.result()
                if status == "ok":
                    summary_path = OUT_ROOT / "_tmp" / f"cell12-{name}" / name / "summary.json"
                    if summary_path.exists():
                        import shutil
                        target = OUT_ROOT / name
                        target.mkdir(parents=True, exist_ok=True)
                        for fname in ("results.jsonl", "summary.json", "ledger.jsonl"):
                            if (summary_path.parent / fname).exists():
                                shutil.copy(summary_path.parent / fname, target / fname)
                        src_raw = summary_path.parent / "raw"
                        if src_raw.is_dir():
                            shutil.copytree(src_raw, target / "raw", dirs_exist_ok=True)
                        print(f"  [done] {name}: copied to {target}")
                    all_runs.append(name)
                else:
                    print(f"  [error] {name}: {payload[:200]}")

        # 批结束提示
        if batch_idx + 1 < len(batches):
            remaining = [p["name"] for p in available[batch_idx+1:]]
            display(Markdown(
                f"⚠️ **还有 {len(remaining)} 个 provider 没跑**：{remaining}。\n\n"
                f"再次执行本 cell 跑下一批（当前上限 {MAX_PARALLEL}）。"
                f"`LBEVAL_MAX_WORKERS` 可调。"
            ))

    print(f"\nbatch summary: {len(all_runs)} provider(s) ran successfully")
    print(f"output root: {OUT_ROOT}")

# === Troubleshooting 子节 ===
# 常见情况：
# 1. summary.schema_validity 偏低（< 0.7）：
#    - 模型返回了概率但某些题没覆盖所有 label → 该模型在长 label 集上有 schema 漏报
#    - 模型有时返回空字符串 → 推测是 rate-limit 或服务端偶发；flash 变体比主入口更明显
# 2. summary.accuracy 高但 brier/ece 也高：
#    - 答对了但置信度校准差（自信错的也自信对）
#    - 解决方向：调 prompt 让模型给出更分散的分布，或换支持原生的 decision model
# 3. 大量 error 记录 → adapter 没适配该 provider 的 response_format；改 llm_eval/adapters/openai_compat.py
# 4. cost_usd_total = None → 该 provider 没在 multi_runner.json 里设 price，框架拒绝"编"价格
# 5. 直填 key 后报错"key empty"：注意 cell 11 里 `"DEEPSEEK_API_KEY": ""` 是空字符串就视作未填，
#    填一个真 key 即可（任意非空字符串都能识别为 "set"）。
# 6. base_url 覆盖不生效：检查 cell 11 的 base_url_overrides 字典 key 是否跟 key_env 一致。

```

    benchmark: tasks/public_all.jsonl  (231 tasks)
      estimated per-provider cost (input tokens × price):
        deepseek-flash      ~$0.1063  (in 0.0936 + out 0.0127)
        kimi-k3             ~$0.0381  (in 0.0347 + out 0.0035)
        glm-5.3-codeplan    ~$0.1790  (in 0.1732 + out 0.0058)
        doubao-2.1-pro      ~$0.2888  (in 0.2772 + out 0.0115)
        step-5-codeplan     ~$0.3696  (in 0.3465 + out 0.0231)
    
    detected 0 provider(s) with keys:
    max parallel: 5   cap_usd/provider: $1.5   tasks: 231
    



⚠️ **No API keys available.**

Two ways to provide keys:

**A. Paste directly in cell 11** (`direct_keys` dict) — convenient for learning, but the key is saved into this notebook file.

**B. `export DEEPSEEK_API_KEY=...` in your shell** before launching Jupyter — safer for production.

Without keys, all subsequent comparison charts (cell 14) fall back to the mock data from cell 13.



```python
# Cell 13 — 多模型横评（mock）+ 全指标对比
import json, os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

import llm_eval
from llm_eval.multi_config import MultiRunConfig, RunnerConfig
from llm_eval.multi_runner import run_multi
from llm_eval.compare import compare_run, write_markdown_table

# 用 mock 演示完整对比 + 全指标图（真实对比在 cell 14）
TASKS = "tasks/smoke.jsonl"  # cell 13 用 smoke（秒级）；真实全量在 cell 12/14

cfg = MultiRunConfig(
    run_id="cell13-multi-mock",
    tasks_path=TASKS,
    runners=[
        RunnerConfig(name="mock-perfect", adapter="mock", model="perfect",   key_env=""),
        RunnerConfig(name="mock-uniform", adapter="mock", model="uniform-1", key_env=""),
    ],
    cap_usd=1.0, delay_s=0.0,
    out_root="runs/notebook-demo/multi/_tmp",
)
manifest = run_multi(cfg)
print(f"runners: {len(manifest['runners'])}")
for r in manifest["runners"]:
    print(f"  {r['name']:20s} status={r['status']:8s} n_ok={r.get('n_ok','-')}")

# Compare
cmp = compare_run("runs/notebook-demo/multi/_tmp/cell13-multi-mock")
charts_dir = Path("runs/notebook-demo/multi/charts")
charts_dir.mkdir(parents=True, exist_ok=True)
write_markdown_table(cmp, str(charts_dir.parent / "compare.md"))
(cmp_path := charts_dir.parent / "compare.json").write_text(
    json.dumps(cmp, ensure_ascii=False, indent=2)
)

# === 内联展示全指标对比表（不只"已导出"） ===
rows = cmp["rows"]
cols = [
    ("adapter/model", lambda r: f"{r.get('adapter','')}/{r.get('model','')}"),
    ("accuracy",     lambda r: r.get("accuracy")),
    ("majority_base",lambda r: r.get("majority_class_accuracy")),
    ("schema_valid", lambda r: r.get("schema_validity")),
    ("schema_strict",lambda r: r.get("schema_validity_strict")),
    ("brier",        lambda r: r.get("brier")),
    ("ece",          lambda r: r.get("ece")),
    ("ordinal_mae",  lambda r: r.get("ordinal_mae")),
    ("p50_s",        lambda r: r.get("p50_s")),
    ("p95_s",        lambda r: r.get("p95_s")),
    ("cost_usd",     lambda r: r.get("cost_usd_total")),
]
def fmt(v):
    if v is None: return "—"
    if isinstance(v, float):
        return f"{v:.4f}" if abs(v) < 100 else f"{v:.2f}"
    return str(v)

header = "| runner | " + " | ".join(c[0] for c in cols) + " |"
sep = "|" + "|".join(["---"] * (len(cols) + 1)) + "|"
lines = [header, sep]
for name, row in rows.items():
    cells = [name] + [fmt(c[1](row)) for c in cols]
    lines.append("| " + " | ".join(cells) + " |")
display(Markdown("### Mock multi-model comparison (cell 13)\n\n" + "\n".join(lines)))

# === 3x3 图：全 9 指标对比 ===
metrics_9 = [
    ("accuracy",          "Accuracy (↑)",          "linear", 1.05),
    ("schema_validity",   "Schema valid (↑)",      "linear", 1.05),
    ("schema_validity_strict","Schema strict (↑)", "linear", 1.05),
    ("brier",             "Brier (↓)",             "log",    None),
    ("ece",               "ECE (↓)",               "log",    None),
    ("ordinal_mae",       "Ordinal MAE (↓)",       "linear",  None),
    ("p50_s",             "p50 latency (↓)",       "log",    None),
    ("p95_s",             "p95 latency (↓)",       "log",    None),
    ("cost_usd_total",    "Cost / 1k decisions (↓)","log",   None),
]
fig, axes = plt.subplots(3, 3, figsize=(15, 12))
names = list(rows.keys())
colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple"]
for idx, (key, title, scale, ymax) in enumerate(metrics_9):
    r, c = divmod(idx, 3)
    ax = axes[r, c]
    vals = [(rows[n].get(key) or 0) for n in names]
    ax.bar(names, vals, color=[colors[i % len(colors)] for i in range(len(names))])
    ax.set_title(title, fontsize=11)
    ax.tick_params(axis='x', rotation=20)
    if scale == "log":
        positive = [v for v in vals if v > 0]
        if len(positive) >= 1:
            ax.set_yscale("log")
    if ymax is not None:
        ax.set_ylim(0, ymax)
fig.suptitle("JevBench full-metric comparison (cell 13 mock)", fontsize=14)
fig.tight_layout()
chart_path = charts_dir / "13_full_metrics.png"
fig.savefig(chart_path, dpi=120, bbox_inches='tight')
display(Markdown(f"**chart saved**: `{chart_path}`"))
plt.close(fig)

# 也保存老 4 联图
fig, axes = plt.subplots(1, 4, figsize=(14, 4))
metrics_4 = [
    ("accuracy",      [rows[n].get("accuracy", 0) for n in names],      "Accuracy (↑)"),
    ("brier",         [rows[n].get("brier", 0) or 0 for n in names],     "Brier (↓)"),
    ("p50_s",         [rows[n].get("p50_s", 0) or 0 for n in names],     "p50 (s)"),
    ("cost_usd_total",[rows[n].get("cost_usd_total") or 0 for n in names], "Cost USD (↓)"),
]
for ax, (k, v, t) in zip(axes, metrics_4):
    ax.bar(names, v, color=[colors[i % len(colors)] for i in range(len(names))])
    ax.set_title(t)
    ax.tick_params(axis='x', rotation=15)
    if k in ("brier", "p50_s", "cost_usd_total") and any(x > 0 for x in v):
        ax.set_yscale("log")
fig.suptitle("JevBench 4-key comparison (cell 13 mock)", fontsize=13)
fig.tight_layout()
fig.savefig(charts_dir / "13_mock_compare.png", dpi=120, bbox_inches='tight')
plt.close(fig)

display(Markdown(
    f"\n所有产物：\n"
    f"- `runs/notebook-demo/multi/compare.json`\n"
    f"- `runs/notebook-demo/multi/compare.md`\n"
    f"- `runs/notebook-demo/multi/charts/13_full_metrics.png` (3×3 全指标)\n"
    f"- `runs/notebook-demo/multi/charts/13_mock_compare.png` (4 联简版)"
))

```

    [run]  mock-perfect (perfect)...


    [done] mock-perfect: 6 ok / 0 err / 0 unat in 0s


    [run]  mock-uniform (uniform-1)...


    [done] mock-uniform: 6 ok / 0 err / 0 unat in 0s


    runners: 2
      mock-perfect         status=ok       n_ok=6
      mock-uniform         status=ok       n_ok=6



### Mock multi-model comparison (cell 13)

| runner | adapter/model | accuracy | majority_base | schema_valid | schema_strict | brier | ece | ordinal_mae | p50_s | p95_s | cost_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mock-perfect | mock/perfect | 1.0000 | 0.6667 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0541 | 0.0551 | — |
| mock-uniform | mock/uniform-1 | 0.3333 | 1.0000 | 1.0000 | 1.0000 | 0.6917 | 0.0250 | 1.5000 | 0.0551 | 0.0551 | — |



**chart saved**: `runs/notebook-demo/multi/charts/13_full_metrics.png`




所有产物：
- `runs/notebook-demo/multi/compare.json`
- `runs/notebook-demo/multi/compare.md`
- `runs/notebook-demo/multi/charts/13_full_metrics.png` (3×3 全指标)
- `runs/notebook-demo/multi/charts/13_mock_compare.png` (4 联简版)



```python
# Cell 14 — 可视化对照表（真实结果 + 全指标内联）
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

# 优先用 cell 12 的真实结果；没跑（无 key）则 fallback 到 cell 13 的 mock 结果
real_dir = Path("runs/notebook-demo/real/_tmp")
fake_dir = Path("runs/notebook-demo/multi/_tmp/cell13-multi-mock")

cmp_source = None
src_label = None

if real_dir.is_dir():
    cmp_real = {}
    for cell_dir in real_dir.iterdir():
        if not cell_dir.is_dir():
            continue
        for r in cell_dir.iterdir():
            sp = r / "summary.json"
            if sp.exists():
                s = json.loads(sp.read_text())
                cmp_real[r.name] = {
                    "adapter": s.get("run_meta", {}).get("adapter", ""),
                    "model":   s.get("run_meta", {}).get("model", ""),
                    **{k: s.get(k) for k in [
                        "accuracy", "majority_class_accuracy",
                        "schema_validity", "schema_validity_strict",
                        "brier", "ece", "ordinal_mae",
                        "p50_s", "p95_s", "cost_usd_total"
                    ]},
                    "paraphrase_both_correct": (s.get("paraphrase_consistency") or {}).get("both_correct"),
                    "paraphrase_consistency":  (s.get("paraphrase_consistency") or {}).get("consistency"),
                }
                # token 总量从 results.jsonl 聚合
                in_t = out_t = 0
                rp = r / "results.jsonl"
                if rp.exists():
                    for line in rp:
                        try:
                            rec = json.loads(line)
                            usage = rec.get("usage") or {}
                            in_t += usage.get("prompt_tokens", 0) or 0
                            out_t += usage.get("completion_tokens", 0) or 0
                        except Exception:
                            pass
                cmp_real[r.name]["token_in"] = in_t
                cmp_real[r.name]["token_out"] = out_t
    if cmp_real:
        cmp_source = {"rows": cmp_real}
        src_label = "real API runs (cell 12, full benchmark)"

if cmp_source is None:
    cmp_path_fb = Path("runs/notebook-demo/multi/compare.json")
    if cmp_path_fb.exists():
        cmp = json.load(open(cmp_path_fb))
        cmp_source = cmp
        src_label = "mock fallback (no API key set — cell 12 was skipped)"
    else:
        display(Markdown("⚠️ No real runs (cell 12) and no mock compare.json (cell 13). Run cell 13 first."))
        cmp_source = {"rows": {}}

display(Markdown(f"## Cross-model metrics table — {src_label}"))

rows = cmp_source.get("rows", {})

# === 内联展示全指标表（12 列：含 token_in/token_out）===
cols = [
    ("adapter/model",  lambda r: f"{r.get('adapter','')}/{r.get('model','')}"),
    ("accuracy",       lambda r: r.get("accuracy")),
    ("majority_base",  lambda r: r.get("majority_class_accuracy")),
    ("schema_valid",   lambda r: r.get("schema_validity")),
    ("brier",          lambda r: r.get("brier")),
    ("ece",            lambda r: r.get("ece")),
    ("ordinal_mae",    lambda r: r.get("ordinal_mae")),
    ("p50_s",          lambda r: r.get("p50_s")),
    ("p95_s",          lambda r: r.get("p95_s")),
    ("token_in",       lambda r: r.get("token_in")),
    ("token_out",      lambda r: r.get("token_out")),
    ("cost_usd",       lambda r: r.get("cost_usd_total")),
]
def _fmt(v):
    if v is None: return "—"
    if isinstance(v, float):
        return f"{v:.2f}" if abs(v) >= 100 else f"{v:.4f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)
header = "| runner | " + " | ".join(c[0] for c in cols) + " |"
sep = "|" + "|".join(["---"] * (len(cols) + 1)) + "|"
lines = [header, sep]
for name, row in rows.items():
    cells = [name] + [_fmt(c[1](row)) for c in cols]
    lines.append("| " + " | ".join(cells) + " |")
display(Markdown("\n".join(lines)))

# Chart
names = list(rows.keys())
charts_dir = Path("runs/notebook-demo/multi/charts")
charts_dir.mkdir(parents=True, exist_ok=True)

# === 3×3 全指标图（含 token 总量）===
colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown"]
if not rows:
    display(Markdown("_no rows to chart._"))
else:
    metrics_9 = [
        ("accuracy",        "Accuracy (↑)",         1.05, False),
        ("schema_validity", "Schema valid (↑)",     1.05, False),
        ("brier",           "Brier (↓)",            None, True),
        ("ece",             "ECE (↓)",              None, True),
        ("ordinal_mae",     "Ordinal MAE (↓)",      None, False),
        ("p50_s",           "p50 latency (↓)",      None, True),
        ("p95_s",           "p95 latency (↓)",      None, True),
        ("cost_usd_total",  "Cost USD total (↓)",   None, True),
        ("token_in",        "Input tokens (↓)",     None, True),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(16, 13))
    for idx, (key, title, ymax, log_ok) in enumerate(metrics_9):
        r, c = divmod(idx, 3)
        ax = axes[r, c]
        vals = [rows[n].get(key) if isinstance(rows[n].get(key), (int, float)) else 0 for n in names]
        ax.bar(names, vals, color=[colors[i % len(colors)] for i in range(len(names))])
        ax.set_title(title, fontsize=11)
        ax.tick_params(axis='x', rotation=20)
        if log_ok and any(v > 0 for v in vals):
            ax.set_yscale("log")
        if ymax is not None:
            ax.set_ylim(0, ymax)
    fig.suptitle(f"JevBench full-metric comparison — {src_label}", fontsize=14)
    fig.tight_layout()
    chart_path = charts_dir / "14_full_metrics.png"
    fig.savefig(chart_path, dpi=120, bbox_inches='tight')
    display(Markdown(f"**chart saved**: `{chart_path}`"))
    plt.close(fig)

# === 关键 4 联图（accuracy / brier / p50 / cost）===
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
panels = [
    ("accuracy",        "Accuracy (↑)",     False, 1.05),
    ("brier",           "Brier (↓)",        True,  None),
    ("p50_s",           "p50 latency (s)",  True,  None),
    ("cost_usd_total",  "Cost USD",         True,  None),
]
for idx, (key, title, log_ok, ymax) in enumerate(panels):
    r, c = divmod(idx, 2)
    ax = axes[r, c]
    vals = [rows[n].get(key) or 0 for n in names]
    ax.bar(names, vals, color=[colors[i % len(colors)] for i in range(len(names))])
    ax.set_title(title)
    ax.tick_params(axis='x', rotation=15)
    if log_ok and any(v > 0 for v in vals):
        ax.set_yscale("log")
    if ymax is not None:
        ax.set_ylim(0, ymax)
fig.suptitle(f"JevBench 4-key comparison — {src_label}", fontsize=13)
fig.tight_layout()
chart_path = charts_dir / "14_real_compare.png"
fig.savefig(chart_path, dpi=120, bbox_inches='tight')
display(Markdown(f"**chart saved**: `{chart_path}`"))
plt.close(fig)

display(Markdown(
    f"\n所有产物：\n"
    f"- `runs/notebook-demo/multi/compare.json`\n"
    f"- `runs/notebook-demo/multi/compare.md`\n"
    f"- `runs/notebook-demo/multi/charts/14_full_metrics.png` (3×3 全指标)\n"
    f"- `runs/notebook-demo/multi/charts/14_real_compare.png` (4 联简版)\n"
    f"- 各 provider 的 raw output: `runs/notebook-demo/real/<name>/`"
))

```


## Cross-model metrics table — mock fallback (no API key set — cell 12 was skipped)



| runner | adapter/model | accuracy | majority_base | schema_valid | brier | ece | ordinal_mae | p50_s | p95_s | token_in | token_out | cost_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mock-perfect | mock/perfect | 1.0000 | 0.6667 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0541 | 0.0551 | — | — | — |
| mock-uniform | mock/uniform-1 | 0.3333 | 1.0000 | 1.0000 | 0.6917 | 0.0250 | 1.5000 | 0.0551 | 0.0551 | — | — | — |



**chart saved**: `runs/notebook-demo/multi/charts/14_full_metrics.png`



**chart saved**: `runs/notebook-demo/multi/charts/14_real_compare.png`




所有产物：
- `runs/notebook-demo/multi/compare.json`
- `runs/notebook-demo/multi/compare.md`
- `runs/notebook-demo/multi/charts/14_full_metrics.png` (3×3 全指标)
- `runs/notebook-demo/multi/charts/14_real_compare.png` (4 联简版)
- 各 provider 的 raw output: `runs/notebook-demo/real/<name>/`


# Cell 15 — 故障模式与设计纪律

## 故障模式与设计纪律

`llm_eval` runner 的不变量：

| 规则 | 做什么 | 不做什么 |
|---|---|---|
| **不重试** | 401/403/429 立即停跑 | 不 sleep 重试、不换 endpoint 重试 |
| **不重映射** | 模型答非所问时直接当 invalid | 不"补"成合法分布、不替模型猜 |
| **不修补** | malformed 分布记 invalid 并计 0 分 | 不重 parse、不删多余字段 |
| **reserve-before / settle-after** | 真扣费先 reserve，settle 用实测 | 余额超 cap 时**请求不发** |
| **20 连续错就停** | API 不可用时早停 | 不让一次跑完烧光预算 |
| **key 仅 env** | 不落盘不 echo | `--key-env ''` 时连 Authorization 都不发 |

### 三个最常见的"看着不对"现象

1. **`schema_validity` 偏低**
   模型有时返了概率但 keys 不完整（漏 label）→ 该题记 invalid 并计 0。
   多数情况下：模型 rounding 把 9 项题舍入到 `0.999`，落在 2% 容忍带里被 renorm 救回；
   真正低的：模型 prompt 让它"用自然语言回答"了。

2. **`accuracy` 高但 `brier` / `ece` 也高**
   答对了但置信度没校准——自信错的也自信对。
   `native` 分布（TypeSafe 的 Jev、djev 等）通常校准好；`verbalized`（让通用 LLM 写概率）容易翻车。

3. **大量 error 记录**
   API 返了非 200 / 空 content。DeepSeek-flash 这种 flash 变体观察到 ~28% 空响应率；
   主入口（deepseek-chat）通常稳定。

### 预算 ledger 怎么看

`runs/notebook-demo/real/<provider>/ledger.jsonl` 是 reserve/settle 流水。
任何 unsettled 的 reservation 都计为已花——中断不退款。


# Cell 16 — 下一步 + CLI 速查

## 下一步

### 添加新 provider

只需在 `llm_eval/adapters/__init__.py` 的 `PROVIDER_TABLE` 里加一条（preset），并在 `llm_eval/adapters/` 加个 8 行 thin shim 继承 `OpenAICompatAdapter`。无需改 runner。

### 添加新 metric

在 `llm_eval/metrics.aggregate()` 加聚合逻辑；在 `llm_eval/summarize._PUBLIC_FIELDS` 加白名单键——两者缺一不可，否则公共导出里看不到。

### 添加新题族

在 `tasks/` 下放 JSONL，每行一个 task record（用 `llm_eval.task.Task` 的字段）。在 `scripts/convert_jevbench.py` 的 `_TOPIC_HINTS` 里给新 family 配 topic。

### CLI 速查

```
llm-eval run        跑单个 (adapter, model) 对一组题
llm-eval summarize   把 results.jsonl 汇总成 summary.json
llm-eval multi-run   一次配置多个 runner 并行（按 ≤5 一批分批）
llm-eval compare     跨 runner 对比表（markdown + json）
```

每条命令加 `--help` 看完整参数。

### 跑更多题

- `tasks/smoke.jsonl` — 6 题（秒级）
- `tasks/public/easy.jsonl` — 48 题（默认）
- `tasks/public_all.jsonl` — 231 题（≈$0.04-0.05/provider）

### 参考

- 完整文档：`README.md` 在 repo 根
- 实现细节：`llm_eval/IMPLEMENTATION.md`（设计纪律详解）
- 上游规范：[github.com/fstandhartinger/jevbench](https://github.com/fstandhartinger/jevbench) (MIT)

