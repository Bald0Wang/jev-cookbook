# RLCD-style 结果诊断：full-v2-20260924

RLCD 的方法原理、与 REINFORCE / GRPO 的区别、官方配方复跑的解读和下一轮实验优化建议见[RLCD 原理与实验优化](../../RLCD原理与实验优化.md)。

## 结论摘要

本次实验的 RLCD-style **不是准确率明显落后**：锁定测试集 argmax accuracy 是 82.6%，略高于 LoRA-SFT 的 82.4%。问题主要出在概率分布与目标软标签的匹配：RLCD-style test soft cross-entropy 为 1.945，LoRA-SFT 为 0.939，约高 2.07 倍。当前证据支持“argmax 接近，但概率质量较差”，还不足以断言是哪一个单独因素造成。

首要原因是本地入口只是一个简化的 RLCD-style policy-gradient 实验，和 Laya 官方仓库公开的 RLCD 微调 Notebook 配方差异较大；再叠加未审核的同一教师模型伪标签，训练信号本身不能代表真实结果概率。**不能据这次结果认定 RLCD 思路本身效果差，也不能把它说成复现了官方训练配方。**

## 已观察到的证据

| 指标 | LoRA-SFT | RLCD-style | 说明 |
|---|---:|---:|---|
| Test argmax accuracy | 82.4% | 82.6% | 相差 0.2 个百分点，实际含义有限 |
| Test soft cross-entropy | 0.939 | 1.945 | RLCD-style 对目标分布的惩罚明显更高 |
| 标签状态 | `needs_human_review` | `needs_human_review` | 不是人工金标结果 |

候选文件 1,900 条记录均使用 `deepseek_flash_independent_vote_proxy`。逐题统计其 `soft` 目标：

| 题型 | 题数 | 平均最大投票占比 | 最大占比为 1.0 的题数 |
|---|---:|---:|---:|
| choice | 3,800 | 0.979 | 3,564（93.8%） |
| noul | 3,800 | 0.996 | 3,750（98.7%） |
| score | 1,900 | 0.964 | 1,695（89.2%） |

这表示三轮同源模型投票几乎总是给出 one-hot 标签。它衡量的是该教师在当前提示规则下的投票一致性，不是独立标注者的一致性，也不是结果发生概率。它可能限制真实质量上限，并让概率训练变成对教师确定性的拟合。

## 对照官方公开配方

对照对象是 Laya 官方仓库 README 链接的 `laya_finetune_typed_decisions_2xT4_kaggle.ipynb`，其训练逻辑直接调用官方 `proper_reward`。对照当前仓库使用的 full-v2 参数：

| 环节 | 官方 Notebook | 本地 full-v2 RLCD-style | 可能影响 |
|---|---|---|---|
| 目标 | `LocalLLaMA/typed-decisions` 的 `gold.probabilities` 分布 | 三轮 DeepSeek 伪标签频率，绝大多数题是单一票型 | 目标来源与目标不确定性不同 |
| 探索噪声 | 沿有效选项维度投影为零均值；标准差每轮由 0.4 退火至 0.1 | 有效 logits 各自加独立噪声；固定 0.5 | 未去掉 softmax 不可见的共同平移分量；后期探索仍偏强，有限样本梯度方差可能更大 |
| Proper-score 权重 | `w_sph=0.75`，`w_rps=1.0` | `w_sph=0.5`，`w_rps=1.0` | reward 与官方目标的相对权重不同 |
| 优势归一化 | 对组内 reward 去均值，再用整个采样组的标准差归一化 | leave-one-out baseline 后，对每道题各自除以该题 4 个采样的标准差，并截断到 [-5, 5] | 单题只有 4 个样本，方差估计不稳；小方差题容易被放大到截断值，改变问题间权重 |
| CE 辅助项 | policy loss + `1.0 × soft CE` | policy loss + `0.1 × soft CE` | 已知软目标的 CE 是低方差直接监督；权重降低 10 倍会减弱稳定器，policy-gradient 噪声更容易主导更新 |
| 优化器 | Encoder LR `2.5e-5`、decision head LR `1e-4`，cosine scheduler | Encoder 与决策头共用 LR `2e-5`，无 LR scheduler | head 的学习速率比官方设置低 5 倍；参数组和训练动态不同 |
| 后处理 | 从训练样本池中留出最多 400 个 item，不进入梯度更新；在其上拟合按题型温度，并清除会覆盖新温度的 bucket 项 | 有独立来源组切分的 100 条 calibration 记录，但不拟合温度；holdout evaluator 只报 soft CE / argmax accuracy | 当前 calibration split 比训练内留出更独立，但未用于温度拟合；也没报告 Brier / ECE |

以上官方设置见[官方训练 Notebook](https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb)；奖励实现见[官方 `laya/common.py`](https://github.com/NandhaKishorM/laya/blob/main/laya/common.py)。本地实现的对应逻辑在 [`finetune_variant_jsonl.py`](../../finetune_variant_jsonl.py) 与 [`rl_common.py`](../../models/rl_common.py)。两边使用同类 log + spherical + ordinal RPS proper-score；重点差异在软目标来源、采样/优势估计、CE 权重、学习率和校准，而不是把两套 reward 名字混为一谈。

奖励函数还把 log probability floor 在 `-9.21`（约等于 `log(1e-4)`）；官方共享实现和本地副本都有这一截断，所以它不是本地与官方的版本差异。不过极端低概率区的惩罚会变平，结合 4 个采样可能让尾部梯度信息不足；需要记录采样概率落入该区间的频率后再判断，不应未经消融就归咎于这一项。

### 优先级判断

1. **伪标签并不等于校准目标。** 多数 soft target 是 one-hot，同一教师的多数票不能说明现实中的正确概率。所有方法共享这份数据，因此它尤其限制“概率是否可信”的结论。
2. **本地 policy-gradient 方差与目标项配比最值得先查。** 固定较大噪声、每题独立的 4 样本标准化，以及仅 0.1 权重的 CE 辅助项，与官方配方差异最大。若错误类概率被推到很低，soft CE 会重罚这些错误；accuracy 却只看 top-1，所以会出现准确率相近但 CE 高很多。
3. **未做温度拟合是可修复的概率问题，但不能修正标签错误或 argmax 错误。** 先在独立 calibration split 上拟合，再在未触碰的 test 上报告结果。
4. **其他混杂因素。** 本次三种训练同时共享一张 RTX 3090，RLCD 更新完整 encoder；资源争用主要会影响时长和可控性，不能单独解释概率指标差距。RLCD 使用全 encoder 与 LoRA 的可训练参数量不同，也影响收敛动态。

本次报告未保存逐题的 RLCD logits、平均最大概率、按题型 Brier/ECE、优势截断率或 reward/advantage 方差。因此，暂时不能确认 RLCD 是否主要过度自信、是否由某一种题型拖累，或每个实现差异各自贡献多少。严格 proper scoring rule 讨论的是 target 正确且采样足够时的期望奖励；它不自动保证小样本 policy-gradient 方差、伪标签正确性和最终校准。

## 下一轮排查顺序

1. **固定数据与基线。** 保持同一来源组切分、基座、tokenization、seed 和 optimizer-update 数；先串行运行，分别保存逐题预测。现有测试集已被查看，不能再用于选超参；最终确认应另留一份新 test。
2. **先查真实标签。** 对代表性的中文对话决策样本进行人工审核，记录多位标注者的标签和分歧，尤其覆盖 5 个题型/决策字段的正例、边界例与稀有类。用该标签子集单独评估，不把 DeepSeek 投票分布描述成人类概率。
3. **做单因素消融。** 一次改一项：CE 权重 0.1 → 1.0；噪声改为有效类别零均值投影并从 0.4 退火到 0.1；优势改为官方组中心化及统一标准差；再单独比较 reward 权重和参数组学习率。每项至少使用多个 seed，避免从同一个 run 得出强结论。
4. **补齐概率指标。** 在 untouched test 同时报 accuracy、soft CE/NLL、Brier、ECE、平均最大概率、预测熵与按题型指标；画 reliability diagram。先用 calibration 拟合温度，不对 test 调参。

官方 Notebook 的 2×T4 DDP、batch 与梯度累积设置不必原样照搬到 RTX 3090；要迁移的是可复核的目标、探索、loss 配比、优化器分组与独立校准流程。先完成上述受控复现实验，再决定是否把官方风格 RLCD 配方设为新默认；当前已跑出的 checkpoint 和报告保持为原始基线。

## 官方配方适配复跑（2026-09-25）

已按上述建议，在完整 v2 数据上执行一次官方配方适配复跑。复跑使用 4 个采样、0.4→0.1 噪声退火、`w_sph=0.75`、CE 权重 1.0、分组学习率和 cosine scheduler；best checkpoint 为第 1 轮。raw test soft CE 从旧 RLCD-style 的 1.945 降到 1.633，accuracy 为 81.95%；独立 calibration 拟温度后 test CE 为 0.570、accuracy 不变。训练轮次、参数、分题型 Brier/ECE、复跑边界和 AutoDL 持久路径详见[官方配方复跑报告](../rlcd-official-recipe-20260925/README.md)。

温度缩放明显改善当前伪标签上的概率指标，但拟合温度较大，不能据此声称真实标签校准良好。该 test split 已在旧报告里检查过；新结果只用于固定参数的探索性比较，不能用于继续选超参数。下一步应校准同一个 LoRA 基线并在人审标签、多 seed、新测试集上比较。
