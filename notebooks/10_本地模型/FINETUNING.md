# Laya 中文监督微调实操

本文按“准备环境 → 下载权重 → 检查数据 → 运行微调 → 查看结果 → 对照推理”的顺序，复现一次 Laya 多语言决策头的 GPU 微调。112 条 pilot 的 Notebook 在 [`notebooks/zh_head_finetuning.ipynb`](notebooks/zh_head_finetuning.ipynb)；全量 v2 数据从环境检查、模型与数据准备、三种训练到留出评估的 Notebook 在 [`notebooks/full_v2_finetuning.ipynb`](notebooks/full_v2_finetuning.ipynb)，两者都可逐格运行。

> **Notebook 默认不下载大文件：** 请先按下文将中文多语言 checkpoint 放到 `LAYA_MODEL_DIR` 指定目录。为避免首次“运行全部”时意外占用网络和磁盘，模型单元格默认 `DOWNLOAD_MODEL_IF_NEEDED = False`；确认约 644 MB 下载后可显式改为 `True`。训练周边依赖也默认不自动安装，CUDA 版 PyTorch 应先按服务器驱动单独配置。

> **先理解微调对象：** Laya 不是普通的自回归聊天模型。当前代码由多语言 encoder 和决策 head 组成，输出 choice / noul / score 等结构化决策。本文提供 Head-only SFT、Encoder LoRA-SFT、历史 RLCD-style 实验入口，以及 `finetune_rlcd_official_jsonl.py` 官方训练逻辑适配器。后者按上游策略梯度、探索退火、损失权重和参数组在本项目 JSONL 上训练；数据格式、基座 checkpoint、单卡硬件与官方 Notebook 不同，因此称为官方配方适配复跑，不称作原始基准的精确复现。

## 1. 环境准备

建议使用 NVIDIA GPU、CUDA 可用的 PyTorch 和 Python 3.11。当前示例记录的环境为 Python 3.11.15、PyTorch 2.14.0+cu126、Transformers 5.17.0、Safetensors 0.8.0、NumPy 2.4.6。依赖文件给出最低版本范围；每次运行的实际版本也会写入 `experiment.json`。

从仓库根目录创建环境。Windows PowerShell：

```powershell
py -3.11 -m venv .venv-laya
.\.venv-laya\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\laya\requirements.txt
python -m pip install "peft>=0.17"
```

Linux：

```bash
python3.11 -m venv .venv-laya
source .venv-laya/bin/activate
python -m pip install --upgrade pip
python -m pip install -r laya/requirements.txt
python -m pip install 'peft>=0.17'
```

训练器不会把 CUDA 不可用的环境静默切换到 CPU。确认当前 Python 使用 CUDA 版 PyTorch：

```python
import torch
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
```

如果 `torch.cuda.is_available()` 是 `False`，先按本机驱动从 [PyTorch 安装选择器](https://pytorch.org/get-started/locally/)安装匹配的 CUDA wheel，再重启 Notebook kernel。不要继续启动训练。

## 2. 下载多语言权重

中文输入使用 ModelScope 的 `multilingual` checkpoint。模型约 644 MB；权重不存放在 Git 仓库中。

Windows PowerShell：

```powershell
python -m pip install modelscope-hub
.\.venv-laya\Scripts\ms-hub.exe download convaiinnovations/laya `
  --local-dir .\laya\models `
  --include "multilingual/**"
```

Linux：

```bash
python -m pip install modelscope-hub
ms-hub download convaiinnovations/laya \
  --local-dir ./laya/models \
  --include 'multilingual/**'
```

确认模型文件和 tokenizer 都已落盘：

```text
laya/models/multilingual/
├── model.safetensors
├── rl_agent_config.json
├── encoder/
└── tokenizer/
```

更详细的下载、校验和加载说明见[模型下载文档](models/README.md)。

## 3. 准备训练数据

仓库附带一份用于复现流程的中文小样本：[`experiments/zh-pilot-112/train-dev.jsonl`](experiments/zh-pilot-112/train-dev.jsonl)。文件共 112 条记录，按 `source_group_id` 切分为 90 个 train group 和 22 个 dev group；对应 270 道训练题和 66 道验证题。每条记录按 Laya JSONL schema 包含 `state`、`qs`、`split` 和审计 metadata。

> **数据性质：** 这些工单和标签是合成数据，经过辅助抽查并标记为 `assistant_reviewed_pilot`，不是人工金标。这个小验证集只用于复现和检查训练链路，不能代表真实业务泛化或概率校准结果。正式任务应先按[数据生成指南](DATA_GENERATION.md)生成候选，再由标注人员审核，并建立独立的真实验证集。

### 真实对话决策数据

保留 112 条 pilot 不变。公开中文对话语料的数据构造在[数据集 Notebook 第 7 节](notebooks/zh_dataset_construction.ipynb)中：输入是当前 user 轮次和此前上下文，标签是下一步回答策略、领域、澄清、外部核验和推理深度等辅助决策，不监督源数据中的 assistant 回复。脚本生成 1,900 条候选及 9,500 道决策题，附三轮 DeepSeek 伪标签软目标和逐题审核表。候选标注完成后仍需人工审核，审核前训练器会拒绝它们。

这份 JSONL 为 Head-only、LoRA-SFT 和 RLCD-style 提供相同的 state、typed questions、`y`、`soft` 与来源组切分。训练入口分别是 `finetune_reviewed_jsonl.py` 和 `finetune_variant_jsonl.py`。发布前还需检查上游数据许可；投票频率只是模型代理，不能当作人类校准概率。

数据至少要满足以下约定：

| 字段 | 作用 |
|---|---|
| `split` | `train` 或 `dev`；训练器拒绝 `train_candidate` |
| `source_group_id` | 同一来源组只能属于一个 split，避免 train/dev 泄漏 |
| `state` | 模型在决策时能看到的状态，可为字符串或对象 |
| `qs` | 一个或多个问题；题型与候选在整份数据中保持明确 |
| `metadata.review_status` | 正式数据应为 `approved` / `human_reviewed`；试跑集需显式启用下方 pilot 参数 |

Choice 和 score 的 `y` 是当前候选顺序中的零起始索引；noul 固定 `false=0, true=1`。候选顺序和标签必须一致。更多字段说明见[数据生成指南](DATA_GENERATION.md)。

## 4. 运行 CUDA 微调

从仓库根目录启动。每次使用一个新的输出目录；训练器会拒绝非空目录，并将 checkpoint、逐轮日志和实验报告写到该目录。示例超参数与仓库这次试跑一致：seed 42、head learning rate `1e-4`、最多 8 轮、dev loss 连续 2 轮不提升时早停。

Windows PowerShell：

```powershell
$runDir = Join-Path $env:TEMP ("laya-zh-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
python .\laya\finetune_reviewed_jsonl.py `
  --data .\laya\experiments\zh-pilot-112\train-dev.jsonl `
  --model-dir .\laya\models\multilingual `
  --output-dir $runDir `
  --epochs 8 `
  --patience 2 `
  --head-lr 1e-4 `
  --max-tokens 4096 `
  --max-seqs 8 `
  --seed 42 `
  --allow-assistant-reviewed-pilot
```

Linux：

```bash
RUN_DIR="${TMPDIR:-/tmp}/laya-zh-$(date +%Y%m%d-%H%M%S)"
python laya/finetune_reviewed_jsonl.py \
  --data laya/experiments/zh-pilot-112/train-dev.jsonl \
  --model-dir laya/models/multilingual \
  --output-dir "$RUN_DIR" \
  --epochs 8 --patience 2 --head-lr 1e-4 \
  --max-tokens 4096 --max-seqs 8 --seed 42 \
  --allow-assistant-reviewed-pilot
```

`--allow-assistant-reviewed-pilot` 仅供复现这批明确标记的试跑数据使用。换成通过人工审核的数据后，移除此参数，并将记录的 review status 设为 `approved` 或 `human_reviewed`。训练目标是 masked soft cross-entropy；每轮在 dev 上记录指标，按 dev soft cross-entropy 保存最佳 checkpoint。encoder 与 act head 保持冻结，原始 base checkpoint 不会被覆盖。

训练目录主要文件：

| 文件 | 内容 |
|---|---|
| `model.safetensors` | 选出的决策模型权重，含冻结 encoder 和微调 head |
| `training_log.csv` / `training_log.jsonl` | baseline 与每轮训练、验证指标 |
| `experiment.json` | 数据和模型 SHA256、软件版本、GPU、超参数、每轮历史及前后对照指标 |
| `rl_agent_config.json`、`encoder/`、`tokenizer/` | 加载微调 checkpoint 所需配置和 tokenizer 文件 |

### 4.1 LoRA-SFT 与 RLCD-style

LoRA-SFT 在 ModernBERT encoder 的 `Wqkv` 和 attention `Wo` 投影上加入 LoRA（默认 rank 8），并更新 Laya decision head；encoder 原权重冻结，训练结束后合并 LoRA，输出可由标准 Laya loader 加载的完整 checkpoint。

`finetune_variant_jsonl.py --method rlcd` 是历史 RLCD-style 路径：训练 encoder 和 decision head，对 logits 加固定高斯扰动，按 proper score 计算回报，再用 leave-one-out baseline 和较低权重的 soft CE 更新。它保留作旧基线。

要采用 Laya 官方训练 Notebook 的核心参数，使用 `finetune_rlcd_official_jsonl.py`：有效类别零均值探索噪声，sigma 从 0.4 退火到 0.1，4 个采样，`w_sph=0.75`、`w_rps=1.0`、CE 权重 1.0，encoder/head 学习率分别为 `2.5e-5` / `1e-4`，并使用 cosine scheduler。它使用本项目的对话决策 JSONL 和来源组切分；独立 calibration split 用来拟合题型温度。实现参数和最近一次结果见[官方配方复跑报告](experiments/rlcd-official-recipe-20260925/README.md)。RLCD 的目标函数直觉、与 REINFORCE / GRPO 的边界、当前结果解读及下一轮消融顺序见[RLCD 原理与实验优化](RLCD原理与实验优化.md)。

AutoDL 示例从共享数据盘读取 112 pilot。正式构造的 1,900 条 v2 仍是 `train_candidate` 且需要人工审核，默认情况下训练器会拒绝未审核样本。只有在明确开展伪标签研究实验时，才使用 `--allow-unreviewed-pseudolabels` 显式覆盖；这不会修改样本的审核状态，也不代表伪标签通过人工审核。

全量 v2 包含 1,900 条来源组隔离后的候选：1,200 条 train 用于梯度更新、200 条 dev 用于早停与 checkpoint 选择、100 条 calibration 与 400 条锁定 test 仅在三种方法选定 checkpoint 后做一次性留出评估。这样完整使用全量数据，同时不把验证/测试标签泄漏进训练或模型选择。各集合仍是 DeepSeek 投票代理标签，结果不能解释为人工金标效果。

在 AutoDL 上先生成固定切分，再并行启动三种方法。`prepare_candidate_splits.py` 会检查计数、重复 ID、来源组泄漏、五题结构与软目标，并保留 `needs_human_review` 状态：

```bash
python laya/data_generation/prepare_candidate_splits.py \
  --input /root/autodl-tmp/datasets/laya-datasets/sharegpt_zh_38k/v2/laya_candidates.jsonl \
  --output-dir /root/autodl-tmp/experiments/laya/full-v2-splits-20260924

DATA=/root/autodl-tmp/experiments/laya/full-v2-splits-20260924/train-dev.jsonl
MODEL=/root/autodl-tmp/models/laya/multilingual
RUN=/root/autodl-tmp/experiments/laya/full-v2-$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"

nohup python laya/finetune_reviewed_jsonl.py \
  --data "$DATA" --model-dir "$MODEL" --output-dir "$RUN/head-only" \
  --epochs 4 --patience 2 --head-lr 1e-4 \
  --max-tokens 1024 --max-seqs 4 --seed 42 \
  --allow-unreviewed-pseudolabels > "$RUN/head-only.log" 2>&1 &

nohup python laya/finetune_variant_jsonl.py --method lora_sft \
  --data "$DATA" --model-dir "$MODEL" --output-dir "$RUN/lora-sft" \
  --epochs 4 --patience 2 --lr 5e-5 --lora-rank 8 \
  --max-tokens 1024 --max-seqs 4 --seed 42 \
  --allow-unreviewed-pseudolabels > "$RUN/lora-sft.log" 2>&1 &

nohup python laya/finetune_variant_jsonl.py --method rlcd \
  --data "$DATA" --model-dir "$MODEL" --output-dir "$RUN/rlcd" \
  --epochs 4 --patience 2 --lr 2e-5 --rl-samples 4 \
  --exploration-std 0.5 --aux-weight 0.1 \
  --max-tokens 1024 --max-seqs 4 --seed 42 \
  --allow-unreviewed-pseudolabels > "$RUN/rlcd.log" 2>&1 &

echo "run directory: $RUN"
```

三种 checkpoint 均确定后，再对 calibration 和锁定 test 做留出评估：

```bash
python laya/evaluate_candidate_holdouts.py \
  --run-root "$RUN" \
  --split-dir /root/autodl-tmp/experiments/laya/full-v2-splits-20260924 \
  --allow-unreviewed-pseudolabels
```

评估脚本不会训练或选择 checkpoint，只在所有运行完成后加载已选模型并保存指标。单卡并行会共享显存；若出现 CUDA OOM，应检查日志并降低 `--max-tokens` 或分批串行运行。结果分别写入三个子目录，包含完整 checkpoint、训练日志和 `experiment.json`。

本次完整 v2 数据的实际运行指标、checkpoint 选择结果和 AutoDL 持久目录见[全量实验报告](experiments/full-v2-20260924/README.md)。旧 RLCD-style 概率指标偏弱的证据、配方差异和诊断过程见[RLCD 诊断报告](experiments/full-v2-20260924/RLCD_DIAGNOSIS.md)；按官方配方适配重训的配置、评估指标和 AutoDL 输出目录见[复跑报告](experiments/rlcd-official-recipe-20260925/README.md)。

下例是此前 112 条 pilot 的链路烟测命令，不是全量数据实验。pilot 使用合成样本，不能代表真实业务泛化或概率校准结果：

```bash
DATA=/root/autodl-tmp/datasets/laya-datasets/zh-pilot-112/train-dev.jsonl
MODEL=/root/autodl-tmp/models/laya/multilingual
RUN=/root/autodl-tmp/experiments/laya/pilot112-$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN"

nohup python laya/finetune_reviewed_jsonl.py \
  --data "$DATA" --model-dir "$MODEL" --output-dir "$RUN/head-only" \
  --epochs 8 --patience 2 --head-lr 1e-4 \
  --max-tokens 1024 --max-seqs 4 --seed 42 \
  --allow-assistant-reviewed-pilot > "$RUN/head-only.log" 2>&1 &

nohup python laya/finetune_variant_jsonl.py --method lora_sft \
  --data "$DATA" --model-dir "$MODEL" --output-dir "$RUN/lora-sft" \
  --epochs 6 --patience 2 --lr 5e-5 --lora-rank 8 \
  --max-tokens 1024 --max-seqs 4 --seed 42 \
  --allow-assistant-reviewed-pilot > "$RUN/lora-sft.log" 2>&1 &

nohup python laya/finetune_variant_jsonl.py --method rlcd \
  --data "$DATA" --model-dir "$MODEL" --output-dir "$RUN/rlcd" \
  --epochs 6 --patience 2 --lr 2e-5 --rl-samples 4 \
  --exploration-std 0.5 --aux-weight 0.1 \
  --max-tokens 1024 --max-seqs 4 --seed 42 \
  --allow-assistant-reviewed-pilot > "$RUN/rlcd.log" 2>&1 &

echo "run directory: $RUN"
```

进程启动后可分别查看 `tail -f "$RUN/head-only.log"`、`tail -f "$RUN/lora-sft.log"`、`tail -f "$RUN/rlcd.log"`。单卡并行会共享显存；若出现 CUDA OOM，停止三个进程并降低 `--max-tokens` 或分批串行运行。结果分别写入三个子目录，包含完整可加载 checkpoint、训练日志和 `experiment.json`。

```bash
python laya/visualize_training.py --run-dir "$RUN/head-only"
python laya/visualize_training.py --run-dir "$RUN/lora-sft"
python laya/visualize_training.py --run-dir "$RUN/rlcd"
```

112 pilot 是合成且经过辅助抽查的数据，主要用于确认三条训练链路和产物加载；其 dev 切分不能支撑真实业务效果或概率校准结论。v2 全量实验入口见本节前文，使用未审核 DeepSeek 伪标签的结果仅代表伪标签实验。用于业务评估或概率校准前，仍需人工审核并另建人工金标 calibration / test 集。

## 5. 查看曲线和实验指标

用日志生成不依赖在线服务的 HTML 报告：

```powershell
python .\laya\visualize_training.py --run-dir $runDir
```

Linux：

```bash
python laya/visualize_training.py --run-dir "$RUN_DIR"
```

打开 `$runDir/training_report.html`，查看基座与微调后验证指标、逐 epoch loss、准确率和题型拆分。CSV 可导入表格工具继续分析；完整本次结果也保存在 [`experiments/zh-pilot-112/`](experiments/zh-pilot-112/)。

本次固定数据的参考结果：验证 argmax accuracy 从 **56.1%** 到 **71.2%**，soft cross-entropy 从 **0.997** 到 **0.666**，按验证交叉熵选择第 6 轮。显卡、随机算子和软件版本可能造成小幅差异；应以自己运行目录中的报告为准。

## 6. 加载微调 checkpoint 做推理

训练结束后，输出目录本身就是可加载的 Laya checkpoint。可以用 Python 客户端对比同一条验证样本上的基座与微调模型：

```python
import json
from pathlib import Path
from laya.client import LayaClient

base_dir = Path("laya/models/multilingual")
# 将下方路径替换成训练命令打印的实际输出目录
run_dir = Path(r"C:\Users\your-name\AppData\Local\Temp\laya-zh-...")

data_path = Path("laya/experiments/zh-pilot-112/train-dev.jsonl")
records = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
record = next(item for item in records if item["split"] == "dev")
questions = {
    q["id"]: {"type": q["t"], "instructions": q["ins"], "criteria": q["crit"]}
    for q in record["qs"]
}

base = LayaClient(base_dir, device="cuda")
before = base.system_one(record["state"], questions)
del base

tuned = LayaClient(run_dir, device="cuda")
after = tuned.system_one(record["state"], questions)
print("基座：", json.dumps(before["answers"], ensure_ascii=False, indent=2))
print("微调：", json.dumps(after["answers"], ensure_ascii=False, indent=2))
```

Notebook 已把路径发现、训练目录创建和这一步的样例代码整理成可逐格执行的流程。单条对照仅检查 checkpoint 能否加载与输出格式，不是模型质量评估。全量 v2 三种方法的分步复现实验见 [`notebooks/full_v2_finetuning.ipynb`](notebooks/full_v2_finetuning.ipynb)。

## 7. 结果边界与后续工作

这条流程证明的是：ModelScope 权重可加载、Laya 编码器和决策头能在 CUDA 上完成监督更新、训练日志可保存和绘图。112 条合成记录、22 个 dev group 的同规范验证集不足以判断生产价值；数据未经人工金标审核，也没有独立校准集、锁定测试集或 OOD 测试集。

正式发布前，应补足人工审核数据、按来源组切分的独立评估集、校准和风险覆盖指标，并保存代码 commit 与数据 manifest。官方配方适配器已在单卡上跑通，但当前一次结果、一个 seed 和伪标签数据不足以验证上游论文结论；后续需用人工审核样本、多 seed 与同样温度流程校准 LoRA 基线作公平比较。本文 head-only 监督训练不能称作 RLCD 复现。
