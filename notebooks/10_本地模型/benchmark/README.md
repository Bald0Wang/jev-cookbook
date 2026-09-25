# Laya vs Jev — JevBench 评测

> 在本机独立部署 **Laya**（开源 typed-decision 模型），与托管的 **Jev**（TypeSafe AI）放
> 到同一个评测 harness 上跑 JevBench v1.1 + v1.2 公开题集（231 道），出
> **accuracy / calibration / latency / JevBench composite** 四维对比。

## 它是什么 / 不是什么

| 它是 | 它不是 |
|---|---|
| **native 端到端评测**：Laya serve 与 Jev API 都返回 `{state, questions}` 形状的 typed-decision，runner 直接拿分布，不做 JSON 解析或自然语言改写 | 一个聊天偏好评测 / leaderboard |
| 一个 4 维横向对比（accuracy / latency / cost / token + JevBench composite）的 harness | 一个产品化 SaaS / 排行服务 |
| 仿照 JevBench v1.2 / v1.3.0 的 scoring 公式 | JevBench 上游官方榜单的复刻（上游用 534 道，硬件是 Hetzner/RunPod）|

## 评测范围

| 项目 | 值 |
|---|---|
| **模型** | `Laya multilingual`（322M mmBERT-base，本机 `../models/multilingual/`） + `Jev 1.13.0`（TypeSafe AI，`TYPESAFE_API_KEY`） |
| **题集** | JevBench `public_all.jsonl`（231 道 = easy 48 + original 72 + hard 111，MIT） |
| **模式** | `native`（两类均直接返回概率分布；不写自然语言） |
| **预算** | `cap_usd=2.0` 全局共享（仅 Jev 走 API 计费，本机 Laya 自托管 = $0） |

## 怎么跑

```bash
cd jev-docs-zh-upstream/laya/benchmark

# 一次性 bootstrap
./scripts/fetch_public_tasks.sh        # 拉 JevBench 公开题 → tasks/*.jsonl
python3 scripts/convert_jevbench.py tasks/easy.jsonl     tasks/easy.llmeval.jsonl
python3 scripts/convert_jevbench.py tasks/original.jsonl tasks/original.llmeval.jsonl
python3 scripts/convert_jevbench.py tasks/hard.jsonl     tasks/hard.llmeval.jsonl
cat tasks/{easy,original,hard}.llmeval.jsonl > tasks/public_all.jsonl
cp ../llm_eval/.env .env               # TYPESAFE_API_KEY 等

# 启动 Laya serve
./scripts/start_laya_serve.sh          # 后台跑，PID → runs/laya_serve.pid
curl -s http://127.0.0.1:8811/healthz # → {"status":"ok","model":"laya-multilingual","device":"mps"}

# 一键跑 notebook
./scripts/run_notebook.sh
# → notebooks/laya_vs_jev_executed.ipynb
# → runs/notebook-demo/real/{laya-local,jev}/summary.json
# → runs/notebook-demo/multi/charts/{main_score,4dim_compare}.png

# 收尾
./scripts/stop_laya_serve.sh
```

或者不用脚本，直接开 notebook：

```bash
.venv/bin/jupyter lab notebooks/laya_vs_jev.ipynb
```

## 怎么读结果

每个 `summary.json` 至少包含以下字段（与 JevBench v1.3.0 公式一致）：

| 字段 | 含义 |
|---|---|
| `accuracy` | argmax 命中率（exact-label-set） |
| `majority_class_accuracy` | 永远选多数 label 的命中率（accuracy 的下限） |
| `schema_validity` / `schema_validity_strict` | 概率分布是否覆盖完整 label 集合、归一化 |
| `brier` | 多分类 Brier 分数（越低越好） |
| `ece` | top-label confidence 的 10-bin ECE（越低越好） |
| `p50_s` / `p95_s` | 中位 / 95 分位延迟（秒，含网络） |
| `cost_usd_total` | 实测 token × provider 公开价 |
| `jevbench_score` | 4 维几何平均：Intelligence / Calibration / Speed / Cost 各 25% |

## 评分公式（沿用 JevBench v1.3.0）

```
Intelligence = (accuracy - chance) / (1 - chance)        → 0-100
Calibration  = 100 - 100·ECE                              → 0-100
Speed        = 100 - 20·log10(p50_s / 0.1s)              → 0-100
Cost         = 100 - 30·log10($ per 1k decisions / $0.001) → 0-100
                                                          (clamped at 0)

JevBench Score = geometric_mean(Intelligence, Calibration, Speed, Cost)
                  折扣：若 Intelligence < 50，则乘 (Intelligence / 50)²
```

任何轴为 `null` 时，对应不参与几何平均（不编造）。`chance` 取 `1 / max_label_set_size`。

## 文件清单

```
benchmark/
├── README.md                    ← 本文件
├── requirements.txt             ← torch / transformers / safetensors / matplotlib / jupyter / nbformat
├── .gitignore                   ← 排除 .env / runs/ / raw/ / .venv/
├── .env.example                 ← 提示 TYPESAFE_API_KEY
├── .env                         ← cp 自 ../llm_eval/.env（gitignore 内）
├── tasks/                       ← JevBench 公开题（fetch_public_tasks.sh 拉）
├── llm_eval/                    ← 评测框架最小拷贝（13 文件）
├── adapters/laya_local.py       ← 新增：本地 Laya serve adapter（继承 TypesafeAdapter）
├── scripts/
│   ├── convert_jevbench.py      ← 把 JevBench 题转 llm_eval 格式
│   ├── fetch_public_tasks.sh    ← curl 拉 3 个 JSONL
│   ├── start_laya_serve.sh      ← 后台启动 Laya serve
│   ├── stop_laya_serve.sh       ← 停止 serve
│   └── run_notebook.sh          ← nbconvert --execute 一键跑
├── notebooks/
│   ├── laya_vs_jev.ipynb        ← 教学 + 跑全量
│   └── laya_vs_jev_executed.ipynb ← 产物（gitignore）
└── runs/                        ← 评测产物（gitignore）
```

## 怎么解读 Laya vs Jev 的差异

- **Laya** 是 Convai Innovations 的开源 Apache-2.0 模型，322M multilingual checkpoint；自托管，无 provider 费率；
  本机 MPS / PyTorch 推理；schema 由用户在每次请求中提供（无重新训练），模型一次前向中并行处理多类问题。
- **Jev** 是 TypeSafe AI 的商业服务，参数与架构未公开；托管 API，$0.042/1M 输入 token；本机只发 HTTPS 请求。
- 两类输出的概率分布都是 `native`（模型自己出，不写 JSON），所以校准指标可比。
- Laya 的 latency 主要看本机设备（CPU ~0.79s/p50；MPS 应快不少）；Jev 的 latency 看网络 + 服务端排队。
- Laya 的 cost_usd_total 永远是 `0`（自托管），所以 Cost 轴 = 100（"免费"档位）。这会让 JevBench composite 偏向 Laya，但要看 Score 列、不是 raw accuracy。

## 限制与边界

- 231 道题是英文为主的 short decision（[JevBench 上游备注](https://github.com/fstandhartinger/jevbench)：242 decisions is a pilot, not a census, English-only）。
- Laya multilingual 在英文题上未必比 english checkpoint 强（详见 `laya/README.md` 第 1 节）。
- 上游 JevBench 在 Hetzner 服务器/RunPod GPU 上测量；本机 Mac（MPS 或 CPU）的 latency 不可直接横向对比。
- Cost 仅计 Jev 的 API 费用 + Laya 自托管 = $0；不计入 electricity / 机器占用。
- 本目录的 `llm_eval/` 是上游 `../llm_eval/` 的精简 fork，不修改上游；新增/修改限制在本目录内。

## License

本目录代码：MIT。Laya checkpoint：Apache-2.0。Jev API key：仅本机使用。JevBench 公开题：MIT。