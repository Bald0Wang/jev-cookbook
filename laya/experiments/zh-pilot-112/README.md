# 中文 112 条 GPU 微调试跑

本目录记录一次 Laya 多语言决策头的中文小样本 GPU 试跑，供复核流程和讨论标注规范使用。数据全部为合成工单，标签由 DeepSeek 生成并经过辅助抽查；`assistant_reviewed_pilot` **不等于人工金标**。

## 文件

- [`train-dev.jsonl`](train-dev.jsonl)：实际训练/验证数据，90 个 train group、22 个 dev group；group 未跨 split。训练 270 道题，验证 66 道题。
- [`training_log.csv`](training_log.csv) / [`training_log.jsonl`](training_log.jsonl)：逐 epoch 的训练损失、验证交叉熵、准确率及题型指标。
- [`training_report.html`](training_report.html)：可离线打开的可视化报告。
- [`experiment.json`](experiment.json)：模型和数据哈希、设备、训练配置与评估结果。

## 结果摘要

使用 NVIDIA GeForce RTX 4070 Ti、CUDA 12.6、PyTorch 2.14.0+cu126、Transformers 5.17.0、Safetensors 0.8.0、NumPy 2.4.6；冻结 encoder，只训练 14,770,945 个决策头参数。随机种子 42，head 学习率 `1e-4`，token budget 4096、最多 8 sequences/batch。8 轮训练用时约 14 秒，峰值显存约 1.77 GiB。以验证交叉熵选择第 6 轮检查点。

| 验证指标 | 基座 | 微调后 |
|---|---:|---:|
| Argmax accuracy | 56.1% | 71.2% |
| Soft cross-entropy | 0.997 | 0.666 |

验证集很小，且与训练集共享同一任务规范；结果不能说明线上效果、OOD 泛化或概率校准。题型拆分、每轮曲线和完整限制请看 HTML 报告。

## 复跑

先按 [`../../models/README.md`](../../models/README.md) 下载 `multilingual` 权重，并安装项目依赖。以下命令从仓库根目录运行；输出目录放在系统临时目录，避免把大型 checkpoint 加入 Git：

```powershell
py -3 .\laya\finetune_reviewed_jsonl.py `
  --data .\laya\experiments\zh-pilot-112\train-dev.jsonl `
  --model-dir .\laya\models\multilingual `
  --output-dir "$env:TEMP\laya-zh-pilot-repro" `
  --epochs 8 --patience 2 --max-tokens 4096 --max-seqs 8 `
  --allow-assistant-reviewed-pilot

py -3 .\laya\visualize_training.py --run-dir "$env:TEMP\laya-zh-pilot-repro"
```

运行需要 CUDA 版 PyTorch 和可用 NVIDIA GPU。`--allow-assistant-reviewed-pilot` 是因为这份公开试跑数据尚未经人工金标审核；正式训练应先按团队流程审核数据，并使用 `approved` / `human_reviewed` 状态，不应沿用此试跑开关。

出于体积考虑，本目录不包含 644 MB 的微调模型权重；运行报告和日志可复核本次结果，重新训练可重建检查点。
