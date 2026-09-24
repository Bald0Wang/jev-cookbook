# Laya 中文监督微调实操

本文按“准备环境 → 下载权重 → 检查数据 → 运行微调 → 查看结果 → 对照推理”的顺序，复现一次 Laya 多语言决策头的 GPU 微调。对应的 Jupyter Notebook 在 [`notebooks/zh_head_finetuning.ipynb`](notebooks/zh_head_finetuning.ipynb)，可以逐格运行。

> **模型还没下载也能从 Notebook 开始：** 找到仓库目录后，紧接着的第一步会检查 `laya/models/multilingual`；缺少权重时自动安装 ModelScope Hub CLI 并下载中文多语言 checkpoint。若手动运行 CLI，按下文先创建 Python 环境，再执行第 2 节下载命令。

> **先理解微调对象：** Laya 不是普通的自回归聊天模型。当前代码由多语言 encoder 和决策 head 组成，输出 choice / noul / score 等结构化决策。本教程使用仓库里的 CUDA head-only 监督 trainer：冻结 encoder 和 act head，只更新决策 head。它不是 MiniCPM/Qwen 的文本生成 LoRA 配方，也不等于复现 Laya 上游 RLCD 训练。

## 1. 环境准备

建议使用 NVIDIA GPU、CUDA 可用的 PyTorch 和 Python 3.11。当前示例记录的环境为 Python 3.11.15、PyTorch 2.14.0+cu126、Transformers 5.17.0、Safetensors 0.8.0、NumPy 2.4.6。依赖文件给出最低版本范围；每次运行的实际版本也会写入 `experiment.json`。

从仓库根目录创建环境。Windows PowerShell：

```powershell
py -3.11 -m venv .venv-laya
.\.venv-laya\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\laya\requirements.txt
```

Linux：

```bash
python3.11 -m venv .venv-laya
source .venv-laya/bin/activate
python -m pip install --upgrade pip
python -m pip install -r laya/requirements.txt
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

Notebook 已把路径发现、训练目录创建和这一步的样例代码整理成可逐格执行的流程。单条对照仅检查 checkpoint 能否加载与输出格式，不是模型质量评估。

## 7. 结果边界与后续工作

这条流程证明的是：ModelScope 权重可加载、Laya 编码器和决策头能在 CUDA 上完成监督更新、训练日志可保存和绘图。112 条合成记录、22 个 dev group 的同规范验证集不足以判断生产价值；数据未经人工金标审核，也没有独立校准集、锁定测试集或 OOD 测试集。

正式发布前，应补足人工审核数据、按来源组切分的独立评估集、校准和风险覆盖指标，并保存代码 commit 与数据 manifest。想进一步研究上游 RLCD，需要单独实现并验证组采样与 policy-gradient trainer；本文 head-only 监督训练不能称作 RLCD 复现。
