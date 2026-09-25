# llm_eval

> **面向中文 LLM 决策能力的多 provider 评测框架** —— 仿照 [JevBench](https://github.com/fstandhartinger/jevbench) 设计。
> 默认对照集：**Jev (native System One)** + **DeepSeek V4.1 / Qwen3.8-Max / GLM-5.3 codeplan / Kimi K3 / 豆包 2.1 Pro / Step-5 codingplan / MiMo 2.6 Pro** 七个国内模型（verbalized）。

把 state 和精确 label 集交给模型，返回概率分布 —— **不写自然语言，不解析输出**。
每个模型在 4 个维度上被比较：**准确度 / 时间 / 价格 / token**。

## 这是什么 / 不是什么

| 它是 | 它不是 |
|---|---|
| 一个**对照 Jev 与中文通用 LLM 在结构化判定能力上的差距**的工具 | 一个聊天偏好评测 |
| 一个 4 维横向对比（accuracy / latency / cost / token）的 harness | 一个产品化的 SaaS / leaderboard |
| 严格遵循 JevBench 上游纪律的 fail-closed 评测器 | 帮你**编造**模型能力数字的工具（无 key 价格 = `null`，不 = 0）|

## 已接入的 8 个模型

| 名称 | 适配器 | 模式 | 默认 model | 输入 $/M | 输出 $/M | Key 环境变量 | 备注 |
|---|---|---|---|---|---|---|---|
| **Jev** (TypeSafe) | `jev` | **native** | `jev-1.13.0` | 0.042 | 0.0 | `TYPESAFE_API_KEY` | 上游基准行；output free |
| DeepSeek V4.1 | `deepseek` | verbalized | `deepseek-v4.1` | 0.27 | 1.10 | `DEEPSEEK_API_KEY` | cache-miss 价格 |
| Qwen3.8-Max | `qwen` | verbalized | `qwen3.8-max` | 0.004 | 0.012 | `DASHSCOPE_API_KEY` | 阿里百炼 |
| GLM-5.3 codeplan | `glm` | verbalized | `glm-5.3` | 0.50 | 0.50 | `ZHIPU_API_KEY` | 智谱 BigModel |
| Kimi K3 | `moonshot` | verbalized | `kimi-k3` | 0.10 | 0.30 | `MOONSHOT_API_KEY` | temperature=1 only |
| 豆包 2.1 Pro | `doubao` | verbalized | auto | 0.80 | 1.00 | `ARK_API_KEY` | endpoint id 自动从 `/models` 发现 |
| Step-5 codingplan | `stepfun` | verbalized | `step-5` | 1.00 | 2.00 | `STEPFUN_API_KEY` | 阶跃星辰 |
| MiMo 2.6 Pro | `xiaomi` | verbalized | `mimo-2.6-pro` | — | — | `XIAOMI_API_KEY` | **公网 endpoint 待发布**，默认 skip |

> **native vs verbalized**：Jev 是 JevBench 上游的"native"行 — 模型 API 本身就返回概率分布，不写自然语言。其余 7 个是"verbalized" — 框架要求通用 LLM 用 JSON schema 写出概率分布。**两类的输出不是同一个对象，分数单拉也合理，但对比仍可读**（verbalized 通常 calibration 更差，这是已知事实）。

## JevBench Score（综合分）

仿照上游 v1.3.0 公式：

```
Intelligence  = (accuracy - chance) / (1 - chance)        → 0-100
Calibration   = 100 - 100·ECE                              → 0-100
Speed         = 100 - 20·log10(p50_s / 0.1s)              → 0-100
Cost          = 100 - 30·log10($ per 1k decisions / $0.001) → 0-100
                 (clamped at 0)

JevBench Score = geometric_mean(Intelligence, Calibration, Speed, Cost)
                 折扣：若 Intelligence < 50，则乘 (Intelligence / 50)²
```

- `chance` 取 `1 / max_label_set_size`（数据集里最大的 label 集，最宽松）
- Cost 列单位是 **$ per 1,000 decisions**（不是 $ per 1k tokens）
- 任何轴为 `null` 时，对应不参与几何平均（不编造）

## 4 维横评图

按上游 JevBench 的设计，4 个维度对比：

- **accuracy**（越高越好）— argmax 命中率，已对照 `majority_class_accuracy` 基线
- **p50 latency / time**（越低越好）— 端到端，含网络
- **token_in**（越低越好）— 输入 token 总数
- **cost_usd / price**（越低越好）— 实测 usage × provider 公开价

## Quickstart

```sh
# 0. 装环境 + 跑测试
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m pytest tests/     # 90+ tests

# 1. 一次跑单个模型（mock — 不花 key）
mkdir -p runs/smoke
.venv/bin/python -m llm_eval.cli run --tasks tasks/smoke.jsonl --adapter mock \
  --results runs/smoke/results.jsonl --raw-dir runs/smoke/raw \
  --limit-ledger runs/smoke/ledger.jsonl --cap-usd 1
.venv/bin/python -m llm_eval.cli summarize --tasks tasks/smoke.jsonl \
  --results runs/smoke/results.jsonl --public-export runs/smoke/summary.json

# 2. 跑真模型（先 export key）
export TYPESAFE_API_KEY="tsk_..."           # Jev
export DEEPSEEK_API_KEY="sk-..."           # DeepSeek V4.1
export DASHSCOPE_API_KEY="sk-..."          # Qwen3.8-Max
export ZHIPU_API_KEY="..."                 # GLM-5.3
export MOONSHOT_API_KEY="sk-..."           # Kimi K3
export ARK_API_KEY="..."                   # 豆包 2.1 Pro
export STEPFUN_API_KEY="..."               # Step-5
# export XIAOMI_API_KEY="..."             # MiMo 2.6 Pro — endpoint placeholder 暂未启用

.venv/bin/python -m llm_eval.cli run --tasks tasks/public_all.jsonl --adapter jev \
  --key-env TYPESAFE_API_KEY \
  --price-in-per-m 0.042 --price-out-per-m 0 \
  --results runs/jev/results.jsonl --raw-dir runs/jev/raw \
  --limit-ledger runs/jev/ledger.jsonl --cap-usd 5 --delay-s 0.1

# 3. 同时跑 7 个模型 — 看 multi_run.example.json 模板
cp multi_run.example.json multi_run.cn.json   # 编辑填 8 个 model
.venv/bin/python -m llm_eval.cli multi-run --config multi_run.cn.json
.venv/bin/python -m llm_eval.cli compare --run-dir runs/2026-XX-XX-cn-all \
  --public-export compare.json --markdown compare.md

# 4. 一键 Jupyter 教程 — 包含 8 个模型 + main-score 图 + 4 维图
.venv/bin/jupyter notebook notebooks/jevbench_intro.ipynb
```

## 怎么获取每个模型的 API key

| Provider | 控制台 | 备注 |
|---|---|---|
| **TypeSafe AI (Jev)** | https://console.typesafe.ai/keys | 注册送少量免费额度 |
| DeepSeek | https://platform.deepseek.com/api_keys | 实名后买 plan 或按量 |
| 阿里百炼 (Qwen) | https://dashscope.console.aliyun.com/apiKey | "API-KEY" 模式 |
| 智谱 (GLM) | https://bigmodel.cn/ | "个人中心 → API Keys" |
| Moonshot (Kimi) | https://platform.moonshot.cn/console/api-keys | — |
| 火山方舟 (豆包) | https://www.volcengine.com/product/ark | 需开通推理服务 |
| 阶跃星辰 (StepFun) | https://platform.stepfun.com/ | codingplan 按 token 计费 |
| 小米 (MiMo) | — | 公网 endpoint 暂未发布，留 placeholder |

## 任务集（Tasks）

| 文件 | 题数 | 来源 | 难度 |
|---|---|---|---|
| `tasks/smoke.jsonl` | 6 | 自有 | smoke（含 1 对 paraphrase） |
| `tasks/public/easy.jsonl` | 48 | JevBench v1.1, MIT | easy |
| `tasks/public/original.jsonl` | 72 | JevBench v1, MIT | mixed |
| `tasks/public/hard.jsonl` | 111 | JevBench v1.2, MIT | hard |
| `tasks/public_all.jsonl` | 231 | 上 3 个并集 | 全部 |

公开题目经 `scripts/convert_jevbench.py` 一键转换，保留 MIT 协议。

## 实时进度 — 每题都"直播"

跑 cell 12 时，runner 默认会按 task 粒度实时打印（不需要开任何开关）：

```
[plan] run_id=cell12-deepseek-flash  tasks=tasks/public_all.jsonl  n=231
[plan] runners queued: 8 → jev, deepseek-v4.1, qwen3.8-max, glm-5.3-codeplan, ...
[plan] task ids (231): easy-intent-00, easy-intent-01, …  … (+211 more)

[run]  deepseek-v4.1 (deepseek-v4.1)  → 231 tasks on tasks/public_all.jsonl
[run]  deepseek-v4.1: 0 already on disk, 231 to run now
[run]  deepseek-v4.1 pending: easy-intent-00, easy-intent-01, …  … (+216 more)

[deepseek-v4.1] ── scope ── 231 tasks total · 0 already on disk · 231 to run
[deepseek-v4.1] progress bar: [······························] 0/231  (updates every 10 tasks)
[deepseek-v4.1] ▶ task 1/231  easy-intent-00  [intent/choice]  starting…
[deepseek-v4.1] ● task 1/231  easy-intent-00  status=ok✓  top=track_order(0.97)  expected='track_order'  (1.1s, $0.0002, 262↓79↑) 🎯 correct
[deepseek-v4.1] ▶ task 2/231  easy-intent-01  …
…
[deepseek-v4.1] ── tally @ 10/231 ── ok=9  invalid=1  error=0  unattempted=0  (10 records written)  [████·                    ] 10/231
[deepseek-v4.1] ✗ task 12/231  easy-intent-11  status=error  consecutive=1/20  (0.4s)  could not parse probs from: ''
…
[deepseek-v4.1] ── final ── ok=220  invalid=4  error=7  unattempted=0  records_on_disk=231/231
```

每行都标了 task_id + family/question_type + top 预测 + expected + 对错标记 (`🎯 correct` / `✗ wrong`) + 累计进度条。学习者可以一眼看到"哪些正在跑、哪些已经跑过、哪些答对、哪些没答对"。

可选环境变量（默认都关，太长会淹没输出）：

| env | 默认 | 作用 |
|---|---|---|
| `LBEVAL_PROGRESS_EVERY=N` | `10` | 每 N 题打一次 tally；设 `1` 看每题累计 |
| `LBEVAL_VERBOSE_PROMPT=1` | 关 | 每题打印 instructions + state_keys + labels |
| `LBEVAL_VERBOSE_OUTPUT=1` | 关 | 每题打印完整 probs JSON（截断 200 字符） |
| `LBEVAL_TASKS_PATH=...` | `tasks/public_all.jsonl` | 切数据集路径（231 / smoke 等） |
| `LBEVAL_MAX_WORKERS=N` | `5` | 并发 provider 数 |
| `LBEVAL_CAP_USD=N` | `1.5` | 每个 provider 预算上限（USD） |

## 纪律（不会破坏的硬约束）

- **一份预算共担**：`--limit-ledger` 跨所有模型共享，reserve-before / settle-after，余额超 cap 时请求不发
- **不重试**：401 / 403 / 429 立即停跑；连续 3 个 infra 错误停跑
- **不编数字**：无 key 价格 = `null`，empty metric = `null` with `n = 0`，malformed 分布 = schema 失败（计 0 分，不修补）
- **原始响应不落源码树**：runner 会拒绝把 raw 写到 `llm_eval/` 内部
- **Key 仅环境**：`--key-env ''` 时连 `Authorization` header 都不发（公网端点应该收到这种待遇）
- **fail-closed**：分布不合法 = 该题错，计 0 分，绝不修复

## 怎么扩展

- 新模型（OpenAI 兼容 `/v1/chat/completions`）→ 在 `llm_eval/adapters/__init__.py` 加一行 preset 即可，runner 不动
- 加 metric → `llm_eval/metrics.aggregate()` + `llm_eval/summarize._PUBLIC_FIELDS` 两边都要加
- 加 family → `scripts/convert_jevbench.py` 的 `_TOPIC_HINTS` + 任务 JSONL 的 `family` 字段

## 产物结构

```
runs/<run_id>/
├── _manifest.json                  # run 元数据 + 每个 runner 状态
├── jev/
│   ├── results.jsonl
│   ├── summary.json                 # 含 jevbench_score
│   ├── ledger.jsonl
│   └── raw/<task_id>.json
├── deepseek-v4.1/
├── qwen3.8-max/
└── ...
compare.json / compare.md          # multi-run 后产出
```

每个 runner 的 `summary.json` 含：`accuracy` / `schema_validity` / `brier` / `ece` / `p50_s` / `cost_usd_total` / **`jevbench_score`** (4 axes + composite)。

## Licence

MIT for this harness and any task records we authored (`tasks/smoke.jsonl`).
JevBench-sourced tasks (`tasks/public/*.jsonl`) keep their MIT licence — see https://github.com/fstandhartinger/jevbench.
Model weights, provider APIs and third-party SDKs keep their own licences.