# Laya 微调与数据构建方案

整理日期：2026-09-23。本文是基于当前工作区 Laya 推理代码、模型配置、已导入文章和 Jev Cookbook 训练资料形成的实施方案。**它不是 Laya 官方训练脚本，也没有产出可用的微调 checkpoint。**

## 1. 当前可复现到哪一步

工作区包含三个 checkpoint、`rl_agent_api.py`、`rl_common.py` 和模型配置。多语言配置为 mmBERT-base、两层决策头，`max_len=1024`、`head_max_len=256`。`rl_common.py` 包含输入编码、候选顺序随机化、episode 前缀目标和 `proper_reward`；当前目录没有完整训练入口、优化器循环、训练集或数据清单。因此可以复用模型和部分算法组件，但还不能直接运行“官方微调命令”。

### 本次方案冒烟验证

先用本地 multilingual tokenizer、真实 `encode_record()` / `collate_items()` / `DecisionModel`，以及 32 维带位置编码的随机 toy encoder 验证了三种题型。候选重排后硬标签和软分布仍对齐；50 步 soft cross-entropy 从 **0.836013** 降到 **0.278188**，`proper_reward` 有限。

随后对真实 multilingual checkpoint 做了单批次 CPU 训练冒烟：用 `strict=True` 成功加载 checkpoint；冻结真实 encoder，只训练 `head`、`type_emb`、`scorer`，并在一个包含 `choice`、`noul`、`score` 的合成 state 上完成一次前向、反向和 AdamW 更新。soft cross-entropy **2.413964**、`proper_reward` **-2.275527**、梯度范数 **19.872765** 均为有限值，可训练参数确实改变；encoder 无梯度。训练结果只留在进程内存，没有保存或覆盖 checkpoint。

这些检查证明本地权重结构、tokenizer、编码 / padding、候选目标对齐和真实决策头的一步更新可以接通。它们不证明收敛、业务准确率、泛化、校准或训练吞吐；合成标签没有业务意义。当前执行环境 `torch.backends.mps.is_available() == False`、CUDA 不可用，所以真实 checkpoint 仅在 CPU 验证，MPS / CUDA 尚未训练。JSONL 读写器、去重 / 分组切分、manifest 和正式 trainer 仍待实现。

《Laya 开源：比Jev快4倍！》称上游用人工标注的公开数据、RLCD、选项扰动和轨迹前缀训练；本地文章还描述了组采样 REINFORCE。模型配置记录了训练摘要，但没有数据版本、全部超参数和 trainer，无法据此复现论文/文章里的分数。下面把**可直接规划的业务微调**与**尝试复现上游 RLCD**分成两条实验路线。

## 2. 先定义一条训练样本

训练对象是一道完整的问题：同一 `state`、一条清楚的 `instructions`、题型和候选项，再加上已对齐的目标。多个问题可共享 state，但每题独立标注、独立归一化；不能把同一工单的未来处理结果放入当时的 state。

建议每行 JSONL 一个 state，可含一题或多题。示例与 `rl_common.py` 的 `encode_record()` 对齐：

```json
{
  "id": "ticket-00017",
  "split": "train",
  "source_group_id": "conversation-1042",
  "task_family": "support-routing-v1",
  "lang": "zh",
  "state": {
    "subject": "重复扣款",
    "body": "三月账单扣了两次，请退回多收的款项。"
  },
  "qs": [
    {
      "id": "department",
      "t": "choice",
      "ins": "这张工单应分配给哪个部门？",
      "crit": {
        "billing": "付款、账单、退款",
        "technical": "产品故障",
        "other": "其他问题"
      },
      "y": 0,
      "soft": [0.9, 0.05, 0.05]
    },
    {
      "id": "urgent",
      "t": "noul",
      "ins": "用户是否明确要求尽快处理？",
      "crit": {
        "false": "没有时间要求",
        "true": "明确要求立刻处理"
      },
      "y": 0
    },
    {
      "id": "severity",
      "t": "score",
      "ins": "评估问题紧急程度。",
      "crit": ["低：可等待", "中：近期处理", "高：阻塞或有明确期限"],
      "y": 2,
      "soft": [0.05, 0.2, 0.75]
    }
  ],
  "metadata": {
    "label_source": "human_adjudicated",
    "annotator_count": 3,
    "policy_version": "support-policy-2026-09"
  }
}
```

- `y` 是候选顺序中的零起始索引；Choice 字典插入顺序、Score 数组顺序、目标向量顺序必须一致。`noul` 固定为 `[false, true]`，因此 `y=0/1` 分别表示 false/true。
- `soft` 是可选目标分布，长度必须等于候选数，值有限且非负、总和为 1。没有软目标时，代码根据 `y` 构造 one-hot。若 `soft` 来自标注者投票，要保留票数与标注规范；“标注者分歧分布”不自动等于真实世界的事件发生概率。
- 线上请求里的 `type / instructions / criteria` 在训练编译器中分别映射为 `t / ins / crit`。来源 ID、语言、split、标注证据等只作审计元数据，不拼进模型文本。
- Score 是有序题，不能为做数据增强而打乱等级。choice/noul 可以在训练时重排候选，但必须同步重排 `y` 和 `soft`；现有 `encode_record()` 已实现这类训练期重排。

## 3. 数据构建流水线

1. **写任务规范。** 每个 `task_family` 定义决策时点、可见信息、题目措辞、候选定义、缺证据时怎么处理、标签来源和代价矩阵。先审查少量边界样本，再冻结规范版本。
2. **收集真实、合规的状态快照。** 优先来自真实工单、审核记录、已结案流程或经验证的业务事件；记录授权、许可、脱敏方式和源记录哈希。对话任务只保留预测时已经发生的轮次，结果标签或后续处置留在目标字段。
3. **双人独立标注，分歧裁决。** 规范性标签由至少两位标注者独立判断，争议交由裁决人并记录理由。保留原始标签、裁决标签和候选版本。对需要概率输出的题，额外保存真实重复结果或独立投票计数；不要让标注者凭直觉写“0.9 置信度”。
4. **LLM 只做辅助。** 可以用于候选草拟、预标注或队列排序，但所有进入 gold / 校准 / 锁定测试集的标签都由规则验证或人审确认。未经审核的合成问题和伪标签不能证明模型的概率已经校准。
5. **去重与分组后切分。** 先按对话、用户、文档、模板、原始业务事件和增强派生关系建立 `source_group_id`，再划分 train/dev/calibration/test。改写、翻译、同一对话的多问题、同一客户的重复工单不能跨分区。另设按 task family 留出的 OOD 集；“换个问法”不等于未见任务族。
6. **训练增强仅作用于 train。** 可重排 choice/noul 候选、对 instructions 做人工审核过的等义改写、在原始文本和 JSON state 表达间转换、加入易混淆负例。每个派生样本保存父样本 ID 和变换版本；不改变标签语义，也不把派生样本复制进 dev/test。
7. **生成 manifest 并做质量闸门。** 固定数据哈希、schema、标注规范版本、每 split 计数；校验标签索引、soft 分布、重复项、空 state、候选长度、语言和题型覆盖。按 task、language、K、长度、来源报告标签分布与缺失率；删除超长候选前先统计被删题的分层偏差。

建议首轮保留 train/dev/calibration/locked-test 四个互斥分区，并另做任务族 OOD 集。按来源组切分，时效变化明显的任务优先增加时间后切分。比例只是容量规划起点，最终以每个关键分层的置信区间为准；锁定 test 不参与训练、温度拟合或阈值挑选。

## 4. 微调路线

### 路线 A：先做可审计的监督微调

1. 冻结 test 前先跑基座模型，保存各 split 的原始 logits、概率、预测和模型哈希。
2. 在 multilingual checkpoint 上冻结 mmBERT 编码器，训练决策头、题型 embedding、候选 scorer；先验证输入模板和目标索引是否正确。Apple MPS 上从小 token batch 开始，按真实 token 数控显存。当前 MPS 只验证过推理，训练尚未验证。
3. 先做两个基线：硬标签 NLL / soft cross-entropy；以及用 `rl_common.proper_reward()` 的可微 proper-score 目标。后者的代码组合为 log score、0.5 倍 spherical score；有序 Score 题额外减 RPS。最小化负 reward。固定数据、分区和随机种子比较，而不是把其中一种损失的结果称作 RLCD。
4. 只有当 head-only 明确欠拟合且数据量足够时，才解冻部分或全部 encoder；encoder 用比 head 更小的学习率，并在 dev 上选 checkpoint。训练过程中同时监控旧任务回归，不按 locked-test 选步数。

这条路线是本项目建议的第一条可实现路径，不等于 Laya 上游的原始优化算法。监督基线更容易排查标签问题，也能先回答“领域数据有没有带来增益”。

### 路线 B：独立实现并评估 RLCD

本地文章描述的上游做法是：对每题候选 logits 加零均值高斯噪声，组内采样 `G=8` 个概率向量，噪声标准差从约 1.0 衰减到 0.3；用严格适当评分作 reward，再按组均值计算 REINFORCE 优势。`rl_common.proper_reward()` 给出了可检查的 reward 组件。文章还描述了 `{act, escalate}` 成本敏感头：自动正确 `+1`、自动错误 `-3`、升级 `-0.5`。

当前权重目录没有完整 RLCD trainer、随机数/采样实现、训练 manifest 或原始标注数据。要做这一分支，先为组采样、log-prob、advantage、梯度裁剪和优化器状态写独立可复现的训练模块；用小合成单元例验证概率单纯形与梯度，再在同一 train/dev 上和路线 A 对照。业务成本矩阵必须来自实际漏判/误操作/人工成本，不能照搬上述示例阈值；校准也必须实测，proper reward 本身不是有限样本下的校准保证。

## 5. 评估、校准与发布

每个 checkpoint 在 dev、calibration、locked test、OOD 上分别出预测，按题型、任务族、语言、候选数 K、输入长度和来源分层：

| 题型 | 主指标 | 诊断指标 |
|---|---|---|
| Choice | accuracy、macro-F1 | NLL、Brier、ECE、risk-coverage、按 K 分层 |
| Noul | AUROC / PR-AUC 与业务阈值代价 | Brier、NLL、ECE、假阴性率 |
| Score | 等级准确率、期望分数 MAE | RPS、NLL、相邻级/跨级错误 |

冻结模型后，仅在 calibration 集拟合温度参数；当前配置支持按题型温度和 `temperature_by_options` 桶。样本不足时用一个全局温度作简单基线，并报告不确定性。阈值/act-escalate 策略也只用 calibration/dev 确定。最后一次性报告 locked-test 与 OOD，保留未校准和校准结果，采用 risk-coverage 说明自动处理比例对应的实际错误风险。

每次发布保存：base checkpoint 名与 SHA256、tokenizer/encoder/config 哈希、训练代码 commit、数据 manifest 哈希、规范版本、训练 seed、优化器与训练参数、最佳 checkpoint 选择规则、校准参数、逐分层指标和已知失效案例。出现关键任务退化或明显分布漂移时回滚到基座/上一版，并将失败样本送入下一批人工标注。

## 6. 按步骤实施与验收

以下顺序把“能跑通”与“有效果”分开验收。每一步的输入、产物和失败处置应记入同一个实验目录；不要把 toy 冒烟的数值当成正式模型指标。

### 步骤 0：固定实验边界

- 建独立实验目录，例如 `laya/runs/2026-09-23-domain-head-v1/`；基座权重保持只读，所有新权重、日志和预测写到实验目录。
- 记录 checkpoint 名称、`model.safetensors` 的 SHA256、config / tokenizer 哈希、训练代码版本、随机种子和设备。
- 先确定目标是领域准确率、概率质量、选择性升级，还是这些指标的组合；定义能接受的错误和回滚条件。

**验收：** 任何结果都能指回固定的基座、数据版本、代码版本和随机种子。

### 步骤 1：检查设备和模型文件

Mac 先运行：

```bash
laya/.venv/bin/python -c 'import torch; print(torch.__version__); print("MPS:", torch.backends.mps.is_available())'
```

Windows PowerShell 检查 CUDA：

```powershell
python -c "import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available())"
```

同时确认所选 checkpoint 目录包含 `model.safetensors`、`rl_agent_config.json`、`encoder/`、`tokenizer/`。先做一次基座单批次前向，再试 batch size 1 的前向 + 反向；量出峰值内存后才逐步增加 token budget。MPS 或 CUDA 不可用时，可以在 CPU 上调试数据编译和 toy trainer，不要据此估算完整 encoder 的训练时间。

**验收：** 设备探测结果与日志一致；模型文件哈希记录完成；正式设备上前向、反向都能完成且无 NaN / OOM。

### 步骤 2：冻结标签规范

为每个 `task_family` 写一份短规范：预测时点、允许看见的 state 字段、题目说明、候选定义及顺序、缺证据处理、裁决流程和业务错误代价。先人工审查正例、反例、边界例各一批，再冻结 `policy_version`。规范变更后产生新版本，不能静默混在旧数据里。

**验收：** 两位标注者面对相同样本能独立标注；分歧能按规范裁决并留痕。

### 步骤 3：构建和审定 JSONL

- 一行一个 state，可在 `qs` 中放多道独立问题。字段按第 2 节样例；训练器只把 `state` 与 `qs` 编码给模型，`id`、来源、语言、split、审计信息留作元数据。
- 每条样本都带 `id`、`source_group_id`、`task_family`、`lang`、`split`、`policy_version`、标注来源和派生关系。敏感业务字段先按数据授权要求脱敏。
- `y` 使用当前候选顺序中的零起始索引；`soft` 长度等于候选数、有限非负且总和为 1。保存原始票数与裁决标签，不能把标注者主观置信度直接伪装成概率标签。
- 由规则或脚本检查 JSONL 每行可解析、ID 唯一、字段类型正确、空 state、候选数、标签范围和分布；至少人工抽查每个 task / language / qtype 分层。

**验收：** 数据校验报告为零个结构错误；所有标签都可追溯到标注或规则，未经审核的 LLM 伪标签不进入 gold、校准或测试集。

### 步骤 4：先分组，再冻结数据分区

按 `source_group_id` 分 train / dev / calibration / locked-test；同一对话、用户、文档、模板、源事件以及其改写和翻译必须留在同一 split。另建未参与训练的 task-family OOD 集。样本较少时，优先保证每个关键分层可报告区间，不要机械追求固定比例。锁定 test 后记录数据文件哈希，禁止用它选超参数或拟合温度。

**验收：** split 间无重复源组、无派生样本泄漏；各 split 的题型、语言、候选数和标签分布有报告。

### 步骤 5：tokenize 与数据编译预检

复用 `rl_common.encode_record()`；当前函数已在本次 smoke 中用真实 multilingual tokenizer 覆盖三种题型。正式数据预处理还要补一个可重复的 JSONL 编译入口，将编码索引、样本数、跳过数和错误原因写入 manifest。

重点检查：`choice` / `noul` 候选重排时同步重排 `target`；`score` 保持等级顺序；marker 数必须等于候选数；超出 `head_max_len` / `max_len` 的样本必须计数并人工审查，不能静默丢弃；同一 split 编译结果应可由数据哈希和配置重建。

**验收：** 每题 marker / label / target 对齐；target 合法归一化；编码跳过率有解释且关键分层没有系统性丢失。

### 步骤 6：先跑基座并保存基线

对 train / dev / calibration 生成并保存未校准 logits、概率、预测、耗时和失败样本；训练前只在 train 上训练，dev 用来选 checkpoint，calibration 留给温度和动作阈值，locked-test 最后才用。按 task、language、qtype、K、长度和来源分层报告指标。

**验收：** 基座报告、预测和权重哈希落盘；确认测试划分没有进入调参流程。先记录基线，再启动优化器。

### 步骤 7：实现 head-only 监督 trainer

1. 加载本地完整决策模型和权重；冻结 `model.encoder`，只训练 `head`、`type_emb`、`scorer`。调用 `model.train()` 后再显式执行 `model.encoder.eval()`，避免冻结 encoder 的 dropout 仍处于训练态。没有独立的 `act / escalate` 标签和真实成本时，先冻结 `act_head`。
2. 第一基线使用 hard-label NLL / soft-target cross-entropy：`loss = -(target * log_softmax(logits)).sum(-1).mean()`。候选 mask 后再做 softmax，padding 候选不能进入损失。
3. 将 `-proper_reward(softmax(logits), target, qtype, marker_mask).mean()` 作为独立对照实验，不能与交叉熵结果混称为上游 RLCD。分开保存 loss 配置和 checkpoint。
4. 固定 seed、按真实 token 数组 batch、裁剪梯度；先从小 token budget 开始。head 学习率可从 `1e-4` 作为试点，再用 dev 比较小范围候选；不要照抄模型卡中的训练时长或 epoch 数。
5. 每隔固定 updates 在 dev 计算主指标和旧任务回归；early stop / 选 checkpoint 只依据预注册的 dev 指标。

**验收：** loss 与梯度为有限值、encoder 权重完全不变、至少一个训练步确实改变可训练参数；同一实验重跑结果在预设容差内可复现；训练目标相对基座在 dev 上达到预设阈值。

### 步骤 8：条件满足后再解冻 encoder

只有在 head-only 结果稳定、数据量足够且 dev 显示欠拟合时，才做部分 encoder 解冻。head 与 encoder 分参数组使用不同学习率，encoder 更低；梯度检查点和混合精度逐项启用。每次只改一个因素，和同 seed 的 frozen-head 版本做对照。

**验收：** 相对 head-only 有可重复的 dev 改善，且 OOD、旧任务与概率质量没有超出预注册回归界限；否则回到 head-only。

### 步骤 9：拟合校准、只测一次 locked-test

冻结选定权重后，在 calibration split 拟合全局或按题型 / K 分桶 temperature；动作阈值也只在 dev / calibration 决定。最后一次性跑 locked-test 和 OOD，报告校准前后结果、置信区间、分层错误与 risk-coverage。不要根据测试表现再修改模型后继续称它为 locked-test。

**验收：** 原始与校准后预测并存；准确率、NLL、Brier、ECE、AUROC / PR-AUC、RPS、risk-coverage 等按适用题型报告；所有决策阈值可追溯到 calibration。

### 步骤 10：封装可回滚的产物

保存 base 与 tuned checkpoint 哈希、训练代码版本、数据 manifest 哈希、规范版本、seed、设备 / dtype、优化器配置、训练日志、校准参数、分层指标和失败样本。把 tuned 模型接入现有 API 后，用相同请求跑基座 / tuned 对照，并验证回滚路径。

**验收：** 能从产物重建同一预测；上线前能切回原始 checkpoint；API schema 与候选标签顺序保持一致。

### RLCD 后续分支

完成并审查步骤 0–10 后，才开始复现 RLCD：另写组采样 / log-prob / baseline / advantage / update 模块，先用合成概率问题验证梯度方向，再用相同 split 与监督基线比较。至少保留多随机种子、噪声退火配置、组内 reward 方差和成本矩阵来源；该分支不能替代监督基线，也不能使用 locked-test 做 reward 调参。

## 7. 资源与当前限制

- **Mac MPS：** MPS 适合尝试冻结 encoder 的决策头训练，但必须先通过本机探测和真实模型单批次反向验证。本次环境 MPS 不可用，所以没有声称已验证 Laya 权重的 MPS 训练。
- **Windows：** CUDA 训练需匹配驱动的 CUDA 版 PyTorch；CPU 可做小数据调试，完整 encoder 微调会慢很多。建议先在 PowerShell 检查 `torch.cuda.is_available()`，再从 batch size 1 开始。
- **当前缺项：** 正式 trainer、JSONL 读写与分组切分器、manifest / 数据校验脚本、训练数据和 MPS/CUDA 实测。下一步按步骤 1–6 落实数据和基线，再开发步骤 7 trainer；RLCD 放在最后。

## 8. 参考

- [本地 Laya 推理 / 编码代码](models/rl_common.py) — `encode_record()`、候选重排、proper reward 和 episode targets。
- [Laya 架构文章归档](../wx_articles4/19-wechat-laya-architecture/article.md) — 上游公开的 RLCD、数据类型和结果主张；文章所述数据与训练实现需以可复现资产为准。
- [NanoJev / OpenJev 训练契约](../dist/jev-cookbook/02-nanojev/research/algorithm_training_contract_zh.md) — 可借鉴的数据审计、标签语义、分组切分与独立校准规范；其中算法是该项目提出的方案，不是 Laya 官方配方。
