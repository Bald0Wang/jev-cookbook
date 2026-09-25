# 第二轮实验：训练前固定的协议

本轮在查看新学生 test/OOD 预测前固定以下选择。它扩展可运行原型，不声称恢复 Jev 的专有网络或 RLCD 配方。

## 目标与结构

输入是多个 `{state, questions}`；每道题包含 instruction 和可变候选集合。直接从 Qwen3-0.6B Instruct 的预训练 Transformer 初始化，移除生成用途的词表输出投影，增加共享标量读出和无位置编码的候选集合 attention 残差。Choice 在本题有效候选上 softmax；Boolean 使用 `[0,z]`；Score 对等级分布取期望。多个状态、题目和候选在一次 backbone forward 中评分，不生成答案 token。

这采用因果 Transformer 的一次 prefill 计算，不等于声称 backbone 是非因果网络。参考实现重复 state/question 前缀；共享树 attention 已有独立结构验证，但没有把其可能节省算力的效果写成已实现吞吐。

## 查询数据从哪里来

所有输入由自写任务生成器产生，Jev 只负责给定输入的教师标签：

| 来源 | 状态 / 题目 | 独立参考目标 |
|---|---:|---|
| 原客服与权限 toy | 144 / 432 | 程序确定标签 |
| 智能家居、商品属性匹配、随机抽样 | 1,008 / 3,024 | 确定标签或解析条件分布 |
| 井字棋、网格导航 | 1,160 / 3,480 | minimax/BFS 最优动作集合及明确规则标签 |
| 合计 | 2,312 / 6,936 | 不使用模型自报 confidence 充当真值 |

train/dev/calibration/test/OOD 分别有 4,152 / 552 / 552 / 1,104 / 576 道题。原 toy 的分区不改变。井字棋对称棋盘归为同源组，网格的障碍布局与目标归为同源组；改变起点或旋转地图不能跨分区。工作流的随机 bag 按完整条件分布去重。

网格包含不可达状态，用于 Boolean 与 Score 检查；不可达时所有合法移动在动作目标中并列，不把动作集合命中解释成成功导航。游戏 rollout 另外预先限定为可达导航地图。

这些输入仍是有限的合成任务。工作流 OOD 只改变为中文记录头，主要字段与规则仍是英文；游戏 OOD 是早盘井字棋与更大地图。不能把这些成绩解释成对任意现实请求的零样本泛化。

## 两个独立训练臂

两臂都从 `Qwen/Qwen3-0.6B`、revision `c1899de289a04d12100db370d81485cdf75e47ca` 新初始化。启动前追加固定 seed 17/18/19 三次重复，以检查单次训练偶然性；主展示固定 seed 17，其余仅用于稳定性统计，不按 test 成绩挑展示模型。每个 seed 的两个训练臂设置一致。

1. **teacher**：最小化 `-Σ p_Jev(i) log p_student(i)`。教师舍入值和为 1 时作为显式 rounded proxy；不合法/非单位和分布隔离，不悄悄重归一化。没有教师标签的题也隔离。
2. **gold_distribution**：最小化 `-Σ q(i) log p_student(i)`。确定任务 q 为 one-hot；抽样任务 q 是解析条件分布；游戏动作 q 在最优集合上均匀。最后一种是专家策略，不能叫事件概率校准。

两臂不混合教师和 gold，避免无法归因。每题先对完整候选集合归一化，再等权平均题目损失；候选数较多不会因此获得更多训练权重。microbatch 累积统一除以本次 optimizer update 的题数。

固定 12 步仅训练新 head，之后 600 步全参数训练。有效 batch=12 道完整题；microbatch 最多 4 题、6,000 个 padding 后候选路径 token；max_length=512，超长报错而非截断。backbone/head 学习率与 CLI 默认值记录到各运行 config；BF16 forward、FP32 参数。每 50 个 full steps 仅评 dev，以本训练目标的 dev CE 选择 best。

测试不参与 checkpoint、步数、温度或任务比例选择。calibration 分区保留，此轮默认温度 1，不为提高 test 指标事后拟合温度。每臂先运行固定预算，再一次性生成选定 checkpoint 的各分区预测。

## 基准与读者演示

- 模仿：对可用 Jev proxy 的 TV、KL、soft CE、argmax 一致率；同时报告教师覆盖率。
- 确定事实：accuracy、NLL/Brier、10-bin ECE，按任务族与题型报告。
- 已知随机机制：与解析 q 的 TV/KL、期望 NLL/Brier、期望分箱校准误差。这些不是从真实世界事件采样得到的经验校准分数。
- 游戏动作：最优集合命中率与分配给最优集合的概率质量，不要求复制某一个并列动作。
- 实际游戏：每个 test/OOD、每种游戏预先选择前 20 局；导航可达性筛选在模型推理之前完成。保留完整轨迹和失败；比较学生、随机、最优策略。井字棋三臂都面对完美 minimax 对手，并按起始局面价值解释胜负。
- 并行：回放附带实际批次的输入状态、所有问题输出和 `forward_passes=1 / autoregressive_decode_steps=0` 证据；不能将不同 step 拼图伪装成一个 batch。

学生运行时没有教师调用或 oracle 动作回退。只有一个合法动作时明确记为 forced action，模型决策数另计。井字棋推进后可能进入训练棋盘同源组，所以轨迹报告该重叠；网格整图隔离在整条轨迹上保持。

## RLCD 在这里的位置

公开材料只披露 Reinforcement Learning for Calibrated Decisions 的名称和目标，没有公开 reward、训练数据和优化细节。这里实现可验证的输出分布训练：有完整 q 时，适当评分规则的监督梯度可直接计算，先用它避免引入无必要的采样方差。只有未来主要得到交互奖励而没有完整目标分布时，才需要增加策略优化；游戏通关奖励自身并不保证概率校准。

这是一条独立开源实现路线，不把标准 soft CE 重命名成已破解 RLCD。完整技术依据与 Fable 的原始意见纠正见 `implementation_plan_zh.md`、`algorithm_fable_decisions_zh.md` 和 `game_fable_review_zh.md`。
