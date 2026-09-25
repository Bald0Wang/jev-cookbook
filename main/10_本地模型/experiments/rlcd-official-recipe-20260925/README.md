# Laya RLCD 官方配方适配复跑

## 目的与依据

2026-09-25 在 AutoDL RTX 3090 上，把 Laya 官方 Notebook 的 RLCD 训练逻辑应用到项目的全量中文对话决策数据。入口脚本为 [`finetune_rlcd_official_jsonl.py`](../../finetune_rlcd_official_jsonl.py)。官方核心步骤包括：4 组 logit 扰动、有效选项上的零均值噪声、每轮将噪声标准差从 0.4 退火到 0.1、`w_sph=0.75` / `w_rps=1.0`、组内中心化并以全组标准差归一化优势、`1.0 × soft CE` 辅助项、encoder/head 分组学习率和 cosine scheduler。实现可参见 [官方训练 Notebook](https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb) 与[官方奖励函数](https://github.com/NandhaKishorM/laya/blob/main/laya/common.py)。

这是一轮**官方训练逻辑在本地任务上的适配复跑**，不是逐字节复现官方基准：上游数据是 `LocalLLaMA/typed-decisions`，本次使用本项目全量 ShareGPT 对话决策 JSONL；标签仍是 `needs_human_review` 的 DeepSeek 投票伪标签。上游 Notebook 标注 421M 参数；本次 AutoDL 的本地多语言 Laya checkpoint 实测共有 321,908,995 参数，其中 321,710,593 个可训练。单卡替代官方 2×T4 DDP，保留来源组隔离与项目数据字段。

## 训练配置

| 配置 | 本次值 |
|---|---:|
| 数据 | 全量 train 1,200 组 / 6,000 题；dev 200 组 / 1,000 题 |
| 独立留出 | calibration 100 组 / 500 题；test 400 组 / 2,000 题 |
| 训练轮数 / checkpoint | 4 轮；按 dev soft CE 选最佳轮次 |
| 探索样本 / sigma | 4；0.4、0.3、0.2、0.1 |
| Proper-score 权重 | `w_sph=0.75`，`w_rps=1.0` |
| CE 辅助权重 | `1.0` |
| 学习率 | encoder `2.5e-5`；decision head `1e-4` |
| 调度器 | cosine annealing，最低 LR `1e-6` |
| 批量 | `max_tokens=4096`、`max_seqs=8`、gradient accumulation `16` |
| 有效批量 | 按真实可变长微批次统计约 63.1 道决策 / update，接近官方 DDP 的 64 |
| 总优化步 | 96 / epoch，384 步 |
| 可训练范围 | 完整 encoder + decision head；冻结 act head |
| GPU 峰值显存 | 6.361 GiB / RTX 3090 24 GiB |

单卡通过梯度累积把有效批量配到约 63 道决策，与官方 2×T4 DDP 的 64 道接近。模型与数据文件哈希记录在 `experiment.json`：基座权重 `9d628fd9…aa8f204`；train/dev JSONL `70602eaf…a434d04`；calibration JSONL `78af2ce9…7d313f6`；test JSONL `9527e5e1…be019`。

在 AutoDL 上复跑时，使用一个新的空输出目录：

```bash
PY=/root/autodl-tmp/laya-venv/bin/python
SCRIPT=/root/autodl-tmp/laya-training-project/laya/finetune_rlcd_official_jsonl.py
SPLIT=/root/autodl-tmp/experiments/laya/full-v2-splits-20260924
MODEL=/root/autodl-tmp/models/laya/multilingual
OUT=/root/autodl-tmp/experiments/laya/rlcd-official-recipe-rerun/artifacts

PYTHONUNBUFFERED=1 "$PY" -u "$SCRIPT" \
  --train-dev "$SPLIT/train-dev.jsonl" \
  --calibration "$SPLIT/calibration.jsonl" \
  --test "$SPLIT/test.jsonl" \
  --model-dir "$MODEL" --output-dir "$OUT" \
  --epochs 4 --patience 4 --max-tokens 4096 --max-seqs 8 --grad-accum 16 \
  --seed 42 --rl-samples 4 --sigma-start 0.4 --sigma-end 0.1 \
  --w-sph 0.75 --w-rps 1.0 --ce-weight 1.0 \
  --lr-encoder 2.5e-5 --lr-head 1e-4 --weight-decay 0.01 \
  --allow-unreviewed-pseudolabels
```

官方 Notebook 的 calibration 从训练样本池中留出；本次沿用项目更严格的独立来源组 calibration split，拟合 choice、score、noul 三个温度。test 只在固定参数、选定 checkpoint 和拟合温度后评估。这个 test split 已在先前基线报告中看过，所以本次结果是受控探索性比较，不是全新未触碰测试集的确认结论。

## 训练与指标

| Epoch | sigma | Train reward | Train soft CE | Dev soft CE | Dev accuracy |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.4 | -0.1887 | 0.7890 | **1.7084** | 81.2% |
| 2 | 0.3 | -0.0882 | 0.9155 | 2.1587 | 80.3% |
| 3 | 0.2 | -0.0162 | 1.0369 | 2.1501 | 82.9% |
| 4 | 0.1 | 0.0979 | 0.8914 | 2.1468 | 82.6% |

Dev soft CE 最佳在第 1 轮；后 3 轮没有超过它，训练仍按固定的 4 轮配方跑完。该现象说明平均 reward 改善并没有同步转化为更低的 dev CE；不应只看 reward 判断训练质量。

| 留出集与处理 | Soft CE | Accuracy | Brier | Top-label ECE |
|---|---:|---:|---:|---:|
| Calibration，拟温度前 | 1.9244 | 78.20% | 0.3852 | 0.1816 |
| Calibration，拟温度后 | 0.6480 | 78.20% | 0.3060 | 0.0576 |
| Test，拟温度前 | 1.6328 | 81.95% | 0.3140 | 0.1542 |
| Test，拟温度后 | **0.5695** | 81.95% | **0.2578** | **0.0525** |

拟合温度（choice、score、noul）为 **4.757、8.884、3.691**。温度缩放没有改变 argmax accuracy，却明显降低 pseudo-target NLL、Brier 和 ECE；尤其 score 温度较高，表示原始概率对这批伪标签过于尖锐。它不能修正错误伪标签，也不能证明真实人类结果的概率校准。

Test 分题型 CE：choice `2.040 → 0.885`（accuracy 72.88%）、score `3.118 → 0.721`（73.00%）、noul `0.483 → 0.178`（95.50%）。主要误差仍集中在 choice 与 score。

对照先前 full-v2 run：旧 RLCD-style test CE / accuracy 为 `1.945 / 82.60%`；本次新配方 raw test 为 `1.633 / 81.95%`。raw CE 下降约 16%，accuracy 下降 0.65 个百分点。先前 LoRA-SFT 为 `0.939 / 82.40%`，但其没有按本次同一个 calibration split 做温度拟合，因此不能把本次 calibrated RLCD 的 `0.570` 与未校准 LoRA 直接作算法优劣结论。

## 输出位置

AutoDL 持久数据盘上保留了训练产物与 checkpoint：

```text
/root/autodl-tmp/experiments/laya/rlcd-official-recipe-20260925/artifacts/
```

目录内有 `model.safetensors`、带温度的 `rl_agent_config.json`、`experiment.json`、`run_config.json`、`training_log.jsonl` 和 `checkpoint_latest/`。本地保存了日志和指标副本；615 MiB 权重仅保留在 AutoDL 持久盘。训练后服务器保持开机，供后续上传镜像。

结果副本：[`experiment.json`](experiment.json)、[`run_config.json`](run_config.json)、[`training_log.jsonl`](training_log.jsonl)、[`training.log`](training.log)。本次执行的脚本 SHA256：`036dfce46ebead124383f78d8cde1322f8d079c4746f2d3ab4cd1affcd967acc`；权重 SHA256：`5ef997ccef788fa196796d195f568e0a565a4625cb335717a77531a490f44d3d`。本地脚本与 AutoDL 脚本哈希已核对一致。

## 解读

本次复跑支持两个有限结论：

1. 按官方方式加入较强 soft CE、零均值投影探索、退火和参数分组后，raw test CE 比旧 RLCD-style 低，但 accuracy 没有提高；dev 最佳只出现在第 1 轮。
2. 这个新 checkpoint 原始概率仍偏尖锐，按独立 calibration split 拟温度可显著改善伪标签 NLL 和校准指标；标签本身仍是未审核伪标签，因此只说明概率输出对当前投票标签的匹配，不代表真实决策准确度。

下一次如要比较算法，应对 LoRA 也使用同一个 calibration split 拟温度，并引入人工审核子集与至少多个 seed；不要在本次 test 上继续选超参数。
