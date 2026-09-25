# ShareGPT 中文对话决策数据：全量微调实验

本报告记录 2026-09-24 在 AutoDL RTX 3090 上进行的 Head-only SFT、LoRA-SFT 与 RLCD-style 并行实验。112 条 pilot 保持不变；本次使用完整 v2 候选集，三种方法使用相同切分、seed 和 dev checkpoint 选择规则。

## 数据与切分

全量候选共有 1,900 条来源组隔离的对话状态、9,500 道决策题。所有记录的审核状态仍是 `needs_human_review`，标签来源为 DeepSeek 多轮投票软目标代理；本次训练通过 `--allow-unreviewed-pseudolabels` 显式开启研究性伪标签实验，没有把数据改标成已审核。

| Split | 记录数 | 决策题数 | 用途 |
|---|---:|---:|---|
| train | 1,200 | 6,000 | 梯度更新 |
| dev | 200 | 1,000 | 早停与 checkpoint 选择 |
| calibration | 100 | 500 | checkpoint 确定后留出评估 |
| test | 400 | 2,000 | checkpoint 确定后锁定留出评估 |

校准集与测试集没有参与训练或早停。这里的 calibration 只表示预留切分；本实验没有拟合温度缩放等校准变换。所有指标均以未审核的 DeepSeek 伪标签为参照，不是人工金标或真实概率校准结果。

源候选文件 SHA256：`a4dfdf763b0e22dd5ded3c404df1e23543dafde1ece7a789eab903410ae0535b`。固定切分 manifest SHA256：`ce037421ef6c19616625633c4464888bf48e708e5e6f9fd89f1e47786367449d`；train/dev JSONL：`70602eaf90f16cab2f495e2a8cc6be2756076bd0f9b2b2ce04ce4c1d4a434d04`；calibration JSONL：`78af2ce974781553b9ec76eeec1350209e2338f9134f6d7d68a87a5527d313f6`；test JSONL：`9527e5e11423d4521de6346c2b9623b4763ec1e62ea83b2477498d2b668be019`。

## 方法与环境

共同设置：seed 42、最多 4 轮、dev patience 2、`max_tokens=1024`、`max_seqs=4`，按 dev soft cross-entropy 保存最佳 epoch。三条任务同时运行在一张 NVIDIA GeForce RTX 3090 上。

| 方法 | 可训练部分 | 学习率与方法参数 | 运行轮数 / 最佳轮数 |
|---|---|---|---:|
| Head-only SFT | 决策 head；冻结 encoder 和 act head | `head_lr=1e-4` | 3 / 1 |
| LoRA-SFT | encoder 的 `Wqkv`、attention `Wo` LoRA + 决策 head；冻结 act head | `lr=5e-5`，rank 8、alpha 16、dropout 0.05 | 4 / 3 |
| RLCD-style | 完整 encoder + 决策 head；冻结 act head | `lr=2e-5`，4 个扰动样本、探索标准差 0.5、CE 辅助权重 0.1 | 4 / 3 |

RLCD-style 使用 proper-score 奖励、logit 高斯探索、leave-one-out baseline 和 CE 辅助损失，是本项目的实验实现，不是 Laya 上游 RLCD 的完整复现。环境为 Python 3.12.3、PyTorch 2.8.0+cu128、CUDA 12.8、Transformers 5.17.0、PEFT 0.21.0、Safetensors 0.8.0。

## 结果

以下 accuracy 和 soft cross-entropy 都以对应 split 的 DeepSeek 软目标为参照。每个 accuracy 基于表中题数计算。

| 方法 | Dev 最佳 CE / Accuracy | Calibration CE / Accuracy | 锁定 Test CE / Accuracy |
|---|---:|---:|---:|
| Head-only SFT | 0.861 / 74.2% | 0.959 / 72.0% | 0.863 / 74.0% |
| LoRA-SFT | 0.950 / 82.0% | 1.100 / 80.0% | 0.939 / 82.4% |
| RLCD-style | 2.018 / 81.4% | 2.155 / 80.4% | 1.945 / 82.6% |

LoRA-SFT 在这份伪标签测试集上取得较好的 CE 与准确率折中。RLCD-style 的 test argmax accuracy 比 LoRA-SFT 高 0.2 个百分点，但 CE 明显更高，说明其概率输出与伪标签软目标的匹配较差；不能仅按 argmax accuracy 判断概率质量。Head-only 的留出表现低于另外两种 encoder 更新方法。

基座在 dev 上的 CE / accuracy 为 1.503 / 44.9%；没有把未预注册的基座测试集指标加入这次锁定 test 比较。详细训练曲线、配置、数据/model 哈希和 checkpoint 位于 AutoDL 持久数据盘：

```text
数据：/root/autodl-tmp/datasets/laya-datasets/sharegpt_zh_38k/v2/laya_candidates.jsonl
切分：/root/autodl-tmp/experiments/laya/full-v2-splits-20260924/
实验：/root/autodl-tmp/experiments/laya/full-v2-20260924-231145/
留出报告：/root/autodl-tmp/experiments/laya/full-v2-20260924-231145/holdout_metrics.json
```

holdout_metrics.json SHA256：`26bc3be04c835e0e18c1e5d90fc655f260cd41e35911e9f9d12c539fdb8e6a91`。

权重没有复制进 Git。要复跑或查看逐轮日志，按[全量数据操作步骤](../../FINETUNING.md#真实对话决策数据)连接 AutoDL 并读取上述目录。外发数据前还要检查上游 ShareGPT 语料许可与署名要求；目前的伪标签需要人工审核后才能作为业务训练或校准依据。
