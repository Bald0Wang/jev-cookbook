# Laya RLCD 原理、论文脉络与实验优化

本文解释 Laya 官方公开训练 Notebook 中 RLCD 的决策概率训练流程，并结合本项目 2026-09-25 的 full-v2 适配复跑，评估当前结果、限制和下一步方案。这里的 RLCD 以 [Laya 官方 Notebook](https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb) 和[奖励实现](https://github.com/NandhaKishorM/laya/blob/main/laya/common.py)为具体定义；相关论文用于解释策略梯度、概率评分与校准等基础，不代表这些论文提出了 Laya 的 RLCD 配方。

## 1. RLCD 解决什么问题

普通分类训练通常关心“选对类别”。Laya 面向的是结构化决策：给定对话或工单 `state`、typed question 与可选项，模型直接输出候选项概率，再由应用决定是否路由、升级人工或执行后续流程。

因此目标不只是让最大概率类别正确，也要让整个分布有意义。例如两个工单都预测为“billing”，其概率分别为 0.99 和 0.54，业务上可能需要不同的人工复核策略。RLCD 把决策分布当作预测对象，使用概率评分奖励训练，再通过概率指标检查输出。

设有效选项上的决策 logits 为 `zθ(x)`，将无效选项屏蔽后：

```text
pθ(k | x) = softmax(zθ(x))k
```

其中 `x` 表示 state 和问题定义。`choice` 是候选类别分布，`noul` 表示 yes/no 概率，`score` 则是有序档位分布。输入候选项变化时，Laya 的 marker/readout 机制会在同一决策结构上对当前选项评分；它不需要为每个业务标签生成自然语言答案。

## 2. 一轮 RLCD 更新如何工作

### 2.1 从基准分布产生探索样本

对同一问题的决策 logits，官方配方采样若干组扰动。只在有效候选项上加噪声，并将噪声投影成零均值：

```text
εj ~ N(0, σ²I)                 # 只保留有效选项维度
εj ← εj - mean(εj)             # 去掉所有类别共同平移的分量
pj = softmax(zθ(x) + εj)
```

Softmax 对所有 logits 加同一个常数不变，所以共同平移不会改变预测概率。去掉这一方向的噪声，能把探索集中在“候选项之间如何重新分配概率”上。`σ` 大时，样本分布探索更广；随着训练进度将 `σ` 从 0.4 退火至 0.1，后段扰动减小。

### 2.2 用 proper score 奖励分布质量

每个扰动样本 `pj` 都与目标分布 `q` 比较，Laya 的 `proper_reward` 按问题类型组合概率评分。官方 Notebook 使用 spherical score 权重 `w_sph=0.75`、有序评分 `w_rps=1.0`；完整正负号、归一化和边界截断以[上游实现](https://github.com/NandhaKishorM/laya/blob/main/laya/common.py)为准。

严格适当评分规则（strictly proper scoring rule）的关键性质是：若真实结果确实来自分布 `q`，那么对预测分布取期望后，诚实报告 `q` 会得到唯一最优期望分数。Gneiting 与 Raftery 对这类规则给出系统论述。这个性质依赖“目标分布代表真实不确定性”；如果 `q` 是偏差教师模型的投票频率，优化出来的只是对该教师代理目标的匹配。

### 2.3 用策略梯度将奖励传回 logits

扰动后的 `pj` 是从以当前 logits 为均值的噪声分布中采出的策略样本。对每个问题，先减去本问题采样奖励的平均值作为基线，再除以整个采样组的奖励标准差：

```text
Aij = (Rij - meanj(Rij)) / (std(all sampled rewards) + ε)
Lpolicy = -mean(Aij · log N(zj ; zθ(x), σ²PK))
```

`zj = zθ(x) + εj`，`PK` 表示有效选项上的零均值投影子空间。实现中的 log-density 省略了与参数无关的归一化常数；组内中心化使这类常数不影响该批次的策略梯度方向。

策略梯度 / likelihood-ratio 估计器利用 `∇θ log pθ(sample)` 将不可微的奖励反馈转换为参数梯度。高于组平均的样本获得正优势，更新会增加这类扰动结果在策略中的相对概率；低于组平均的样本得到负优势。Williams 的 REINFORCE 论文是这一 score-function 梯度估计思路的经典来源。

### 2.4 加入低方差的 soft CE 稳定项

Laya 官方配方同时对基准分布计算软标签交叉熵：

```text
L = Lpolicy + λCE · CE(q, pθ)
λCE = 1.0
```

策略梯度依赖有限个探索样本，方差可能较大；当软目标 `q` 已知时，交叉熵直接提供分布监督，作为稳定项。它和 reward 项不是完全相同的估计路径：前者直接拟合目标，后者通过探索样本及奖励推动策略。

本项目适配代码按 encoder / decision head 分组优化，学习率分别为 `2.5e-5` 和 `1e-4`，使用 cosine scheduler；每题 4 个 RL 样本。最新实验细节见[官方配方适配复跑报告](experiments/rlcd-official-recipe-20260925/README.md)。

### 2.5 训练后再做温度校准

训练集之外的 calibration split 可用于拟合温度 `T`：

```text
pT = softmax(z / T)
```

`T>1` 会压平较尖锐的预测，`T<1` 会让分布更尖。Guo 等人的工作讨论了神经网络概率校准及温度缩放这一后处理方法。温度缩放不会改变 argmax 类别，也不能修复错误标签；它只在校准集目标可信且与部署分布一致时，调整概率尺度。校准集、验证集和最终测试集应分开，不能在测试集上反复选温度或超参数。

## 3. 与 REINFORCE、GRPO 的关系

| 方法 | 采样对象与目标 | 与 Laya RLCD 的关系 |
|---|---|---|
| REINFORCE | 从策略采样动作，利用 reward × `∇ log π` 更新期望回报 | RLCD 的有限样本奖励梯度属于 score-function / policy-gradient 思路；REINFORCE 本身没有规定 Laya 的 typed decision、proper score 或 soft CE 配方 |
| DeepSeekMath 的 GRPO | 自回归模型为一个 prompt 采样多条文本 completion；用组内奖励构造优势，并在 PPO 风格目标中加入参考策略 KL 约束 | 都利用多个样本和组基线减少对价值模型的依赖；但 Laya 采样的是分类 logits 的小幅连续扰动，优化分布评分 + soft CE，没有生成长文本、PPO clipped ratio 或参考 LLM KL 项，不能称为 GRPO 复现 |
| Laya 官方 RLCD 配方 | typed decision logits 的零均值噪声采样；用适当概率分数算 reward，再结合组内中心化、soft CE、温度校准 | 针对有限候选项的概率决策任务，不是对话生成模型的 RLHF 配方 |

DeepSeekMath 原文第 4 节和附录 A.1.6 定义了 GRPO：它使用同一问题的一组模型生成结果、组相对优势、PPO 风格比率，并包含参考策略 KL 项。相同点只在较宽泛的“策略梯度 + 多样本组内基线”；采样对象、奖励、动作空间、损失结构都不同。

## 4. 本次实验说明了什么

本次是在 321.9M multilingual checkpoint 上，将上游核心训练逻辑适配到本项目的全量对话决策 JSONL；上游 Notebook 使用 421M typed-decisions 模型和 2×T4。它是**官方配方适配复跑**，不等于上游基准的精确复现。训练标签仍来自 DeepSeek 三轮投票，记录状态为 `needs_human_review`。

| 指标 | 观察 | 含义 |
|---|---:|---|
| Dev soft CE，epoch 1→4 | `1.708 → 2.159 → 2.150 → 2.147` | dev 概率拟合最佳在第 1 轮，后续没有恢复 |
| Train reward，epoch 1→4 | `-0.189 → -0.088 → -0.016 → 0.098` | reward 一直改善，但未转化为 dev CE 改善 |
| Test raw CE / accuracy | `1.633 / 81.95%` | 测试集上 top-1 尚可，概率质量仍需看 CE、Brier、ECE |
| Test calibrated CE / accuracy | `0.570 / 81.95%` | 温度缩放显著改善对伪标签的概率匹配，不改变 top-1 |
| Test Brier / ECE | `0.314 / 0.154` → `0.258 / 0.052` | 校准后这些指标下降；仍然只对当前伪标签目标成立 |
| choice / score / noul 温度 | `4.757 / 8.884 / 3.691` | 三类 logits 相对伪目标都需要明显变平，尤其 score |

主要证据是 reward 与 dev CE 方向分离。仅凭现有日志无法确定是 reward 混合权重、有限样本方差、伪目标质量、encoder 学习率、领域泛化还是题型比例造成。校准温度很大，说明原始输出相对这批软目标过尖；这不是模型“知道自己不确定”的证据，也不是人类结果的校准证明。

测试 split 曾被先前基线实验查看，本次测试不是全新 untouched test。旧 LoRA-SFT test soft CE 为 `0.939`，但没有使用同一个 calibration split 做温度拟合。因此当前不能把校准后 RLCD 的 `0.570` 与未校准 LoRA 直接比较，也不能用这个 test 继续调参。完整逐项结果及路径见[实验报告](experiments/rlcd-official-recipe-20260925/README.md)和[旧实验诊断](experiments/full-v2-20260924/RLCD_DIAGNOSIS.md)。

## 5. 建议的优化顺序

### A. 先补目标与评估的可信度

1. **构建人工审核子集。** 每条对话由至少两位标注者独立填写业务决策；分歧由第三人裁决。若要训练和评估概率，不只记录最终多数票，还要保存各标注者的选择或显式置信分布。伪标签建议保留作候选和难例挖掘，不能混作人类概率。
2. **补清楚任务定义。** 对每个问题定义选项含义、`score` 的顺序与边界、`noul` 的正负语义、允许的“不确定/转人工”情形。可以另存可核对的证据片段和标注理由，但不应把无依据的教师解释当标签。
3. **按来源对话分组切分。** 同一原始对话、相邻片段或重复/改写记录必须进入同一 split。已有旧 test 标记为已使用；新建来源隔离的 untouched test，在该集合上只做最终报告。
4. **公平比较基线。** Head-only、LoRA-SFT、RLCD 使用同一基座、数据 manifest、seed、来源切分和 dev 选模规则；所有模型在同一 calibration split 上独立拟温度，再各自在同一个新 test 上报告 raw / calibrated 指标。

### B. 让训练过程可诊断

下一轮给每个 epoch 和题型都保存 reward 分量及均值/标准差、优势标准差和极端比例、policy loss、CE、梯度范数、有效类别数、预测熵、最大概率、dev NLL / Brier / ECE / accuracy，并保存逐题 raw logits 和预测。这些量可以回答：训练是否只让 reward 增长、哪个题型驱动总 reward、哪些问题的梯度被组内归一化放大，以及概率是否系统性过尖。

分题型报告 `choice`、`score`、`noul` 指标和 reliability diagram。对有序 `score`，增加相邻档位容错率、平均档位绝对误差和累计分布误差；仅报告 argmax accuracy 会丢失概率与序关系信息。对自动路由场景增加 coverage-risk 曲线，衡量在低置信请求转人工时剩余自动决策的错误率。

### C. 再做小型受控消融

每次只改一个主要因素，固定新 dev 切分和训练 seed；筛选后再用至少 3 个 seed 检查稳定性。

| 次序 | 对照 | 要回答的问题 |
|---:|---|---|
| 1 | 纯 soft CE；纯 policy reward；当前 `policy + 1.0×CE` | reward 项是否真的优于稳定 SFT，组合项是否互补 |
| 2 | encoder LR `1e-5` vs `2.5e-5`（head LR 固定 `1e-4`） | 当前早期最佳后退化是否与 encoder 更新过强有关 |
| 3 | 4 vs 8 个扰动样本；固定其他配置 | 增加样本是否降低 reward/优势方差，收益是否值得成本 |
| 4 | `σ: 0.4→0.1` vs 较保守探索区间 | 是否需要更弱的 logit 探索；以 dev soft CE 与校准指标决定 |
| 5 | 全局奖励归一化 vs 按题型分别监控 / 归一化的实验臂 | 当前不同题型 reward 尺度是否导致某类问题支配梯度 |
| 6 | `w_sph` / `w_rps` 单独移除或逐项调整 | 哪个评分分量改善了选择/顺序概率，是否有副作用 |

注意第 5、6 项是要检验的假设，不应在没有受控对照时直接改成新默认。对已知的软目标，CE 通常是更低方差的监督路径；若 reward 更新没有独立收益，应优先解释它而不是继续加大 RL 权重。

### D. 固定 checkpoint 与温度拟合规则

- 当前 best dev checkpoint 是 epoch 1；下一次保留 4 epoch 上限、将 early-stopping patience 调为 1，让首次 dev 退化后停止多跑的 epoch，同时仍保存 best checkpoint。
- 温度只在 calibration 上拟合。校准集每类题数量目前是 choice 200、score 100、noul 200；score 温度 `8.884` 基于 100 个样本，建议对温度及指标做按来源组 bootstrap 区间，检查是否由少数题驱动。
- ECE 对分桶方式敏感；将 NLL、Brier、可靠性图、分题型指标与置信区间一起报告，不把单一 ECE 当结论。

## 6. 仍未解决的问题

1. **标签在表达什么？** 三轮同源 DeepSeek 投票频率目前不是人类意见分布、真实结果发生概率或模型可校准概率。这个问题是首要限制。
2. **为什么 reward 上升而 dev CE 变差？** 需要 reward 分量、方差、题型分布、逐题 logits 和人工标注集后才能判断；当前不能归因于某一个超参数。
3. **RLCD 比 SFT 带来什么独立价值？** 需要在人类金标的新 test 上，用同一 calibration 程序比较纯 CE、LoRA、RLCD 的判别质量与概率质量，并加入人工转接风险指标。
4. **温度是否可迁移？** 当前温度是在伪目标上拟合，每题型样本数有限；新来源、新语言或标签先验变化后是否仍有效未知。
5. **复跑是否稳定？** 当前单一 seed。需要多 seed 与按来源组 bootstrap，报告均值、离散程度和失败运行。
6. **与官方结果能否直接比？** 不能。模型参数量、数据集、标签形式、设备和数据管线都不同；上游 Notebook 是 421M / 2×T4 / typed-decisions，本地是 321.9M / 单 RTX 3090 / ShareGPT 中文对话决策数据。

## 7. 参考资料

1. Convai Innovations, [Laya 官方仓库](https://github.com/NandhaKishorM/laya)，特别是 [RLCD 微调 Notebook](https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb) 与 [`laya/common.py`](https://github.com/NandhaKishorM/laya/blob/main/laya/common.py)。用于确认 Laya 的代码实现、参数和模型接口。
2. Williams, R. J. (1992). [Simple Statistical Gradient-Following Algorithms for Connectionist Reinforcement Learning](https://doi.org/10.1007/BF00992696). *Machine Learning*, 8, 229–256。策略梯度 / REINFORCE 的经典来源。
3. Gneiting, T. & Raftery, A. E. (2007). [Strictly Proper Scoring Rules, Prediction, and Estimation](https://doi.org/10.1198/016214506000001437). *Journal of the American Statistical Association*, 102(477), 359–378。解释适当评分规则的概率预测含义。
4. Shao, Z. et al. (2024). [DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models](https://arxiv.org/abs/2402.03300)。arXiv 预印本，第 4 节及附录 A.1.6 介绍 GRPO；这里用于说明相邻方法及边界，不把 Laya RLCD 等同 GRPO。
5. Guo, C. et al. (2017). [On Calibration of Modern Neural Networks](https://arxiv.org/abs/1706.04599). ICML 2017。讨论神经网络校准与温度缩放。
