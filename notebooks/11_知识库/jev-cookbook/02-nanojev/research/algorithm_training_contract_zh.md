# OpenJev 训练执行契约：目标、损失、批处理与可推翻的默认选择

日期：2026-09-17。本文假设已有合法、按来源分组的 `(state, question, candidates)` 数据，只规定后续训练算法。没有运行训练、调用收费模型或读取凭证。它是我们可实现的方案，不是 TypeSafe 未公开的 RLCD 配方。

主线选择是：**直接学习每题的候选条件分布；每个样本只选一种含义明确的监督；使用稳定的 categorical cross-entropy；有完整教师分布时，它与 forward KL 具有相同参数梯度；先适配读出与 backbone，再用独立真值做后验校准。RL 是同 checkpoint 的对照实验，不是必须追加的一道工序。**

本文始终明确写出 `KL(teacher || student)` 的方向；生成任务的固定温度建议和标签混合比例不直接沿用于本任务。

## 1. 先固定训练对象：一条监督单位是一道完整问题

记 `x_j=(s_j,q_j,C_j)`，`C_j={c_j1,…,c_jK}`。模型产生 `K_j` 个标量 logits，得到 `pθ(k|x_j)`。主干可来自 base、instruct 或 reranker；这个损失契约不预先判定哪一种初始化胜出。

每个候选的输入必须包含 **state、question 和本候选的语义描述**。候选独立评分时，`z_jk=fθ(s_j,q_j,c_jk)`；Choice 的集合交互实验可换成 `fθ(s_j,q_j,C_j,c_jk)`。Score 首版保持等级描述独立评分，不把邻级或等级序号送进评分器。多个 state、问题和候选展平成一个批次进行前向，随后按问题归一化；没有逐题文本生成或隐含 CoT。单次前向是我们的首版实现要求，不是对 JeV 内部采样步数的断言。[官方 Score 语义](https://docs.typesafe.ai/primitives/score)、[创始人对 CoT 的说明](https://x.com/CompleteSkeptic/status/2099981459541143995)

同题的全部候选是损失计算的原子组：不能把一题拆成若干互不相见的候选小批，再分别 softmax；那会改变分母与学习目标。候选数量决定计算量，不决定该题自动获得更多训练权重。

## 2. 数据与目标 schema

建议原始 teacher 响应不可变存档，训练 manifest 保存明确的派生目标。下面是字段契约示例，不要求把所有 provenance 字段送进模型：

```json
{
  "schema_version": "openjev-train-v1",
  "sample_id": "doc17:state3:q2:variant0",
  "source_group_id": "doc17",
  "task_family_id": "refund_policy_v3",
  "split": "train",
  "state": {"text": "...", "snapshot_id": "state3"},
  "question": {
    "id": "q2",
    "type": "choice",
    "text": "依据给定政策，本次申请应该进入哪种处理流程？",
    "semantics_version": "refund_route_v3"
  },
  "candidates": [
    {"id": "approve", "text": "符合条件，直接批准", "ordinal_value": null},
    {"id": "review", "text": "缺少必需证据，转人工复核", "ordinal_value": null},
    {"id": "reject", "text": "违反明确条件，拒绝申请", "ordinal_value": null}
  ],
  "teacher": {
    "model": "provider/model@revision",
    "label_source": "teacher_native_distribution",
    "target_kind": "rounded_probabilities",
    "candidate_ids": ["approve", "review", "reject"],
    "raw_probabilities": [0.25, 0.60, 0.15],
    "rounding": {"probability_decimals": 2, "mode": "unknown"},
    "reported_value": "review",
    "reported_confidence": 0.4,
    "raw_response_ref": "responses/sha256.json"
  },
  "gold": null,
  "resolved_target": {
    "status": "diagnostic_only",
    "source": "teacher",
    "kind": "rounded_proxy_distribution",
    "probabilities": [0.25, 0.60, 0.15],
    "transform": "identity",
    "semantics": "teacher_choice_distribution"
  }
}
```

`reported_confidence` 和 `reported_value` 用于审计，不作分布头的训练标签。state 的存储可用共享引用减少磁盘重复；模型前向是否真正共享计算是另一个问题。序列化模板、问题文本、候选映射和 tokenizer 版本都进入数据哈希。

### 2.1 三种题型的精确定义

| 类型 | 训练空间 | 映射规则 |
|---|---|---|
| Boolean/Noul | `[false,true]` 两个互补结果 | 教师若只给 `p_true`，转换为 `[1-p_true,p_true]`，保留原字段及这一转换记录。不同 Boolean 问题之间不作 softmax。 |
| Choice | 当前问题内的 `K>=2` 个互斥输出选项 | 按稳定 candidate ID 对齐目标，不按名称排序猜测位置；softmax 学习在该题所列输出空间内的分布。 |
| Score | 有序等级的完整类别分布 | 兼容接口使用 `ordinal_value=0,…,K-1`，期望值为 `Σ_k ordinal_value_k*p_k`；序号不作为独立等级评分器的输入。 |

对 `K=1`，接口可以确定性返回 `[1]`，但它没有可学习的类别竞争信号：不计入训练有效题数或分母。`K=0` 为无效输入。候选 ID 重复、缺失或多余都必须拒绝；完全同义的重复选项另记数据质量问题，不能期待 softmax 自动恢复其业务意义。

Score 只能在 ID 与 `ordinal_value` 一起保留的情况下重排物理存储；改变等级的语义顺序是改题，需要重做标签。仅有一个平均分不能唯一还原等级分布，不能把均值四舍五入后伪装成完整分布标签；这种数据从本主线排除，留给明确的弱监督实验。

`none`、`unknown`、`需补证据` 必须是业务定义清楚的显式候选；它们彼此不等价。没有显式候选时，模型仍须在给定 Choice 空间归一化，不能自行附加一个“拒答概率”。Score 的缺失值 `null` 是缺标签，不是第 0 级。证据不足不自动意味着 Boolean=0.5，也不自动意味着 Choice 均匀分布。

### 2.2 gold 的来源与含义

```text
gold.kind ∈ {
  deterministic_verified_label,   # 可执行规则或已审定事实
  programmatic_conditional_distribution, # 已定义随机机制+可见信息推导的完整q
  observed_outcome,                # 一次真实结果，不代表条件发生率为0/1
  adjudicated_human_label,         # 规范明确且已裁决的标签
  human_annotation_distribution    # 独立标注的计数/分布，保留人数与规范
}

gold = {
  kind, candidate_id OR counts_by_candidate,
  provenance_ref, input_snapshot_id, semantics_version,
  verification_status
}
```

`observed_outcome` 的 one-hot 只是一条 proper-loss 观测。模型报 0.7、这次事件未发生，不应立刻标为“教师与 gold 冲突”；只有在很多结果上才能评价其概率。人工分布的目标含义是相应标注规范下的意见分布，不自动等于客观事件发生率。未审定的单次 LLM 输出属于伪标签，不归入 gold。

## 3. 教师概率校验，尤其是两位小数舍入

先验证类型、candidate ID 一一对应、有限数值和 `[0,1]` 范围；无法对应、NaN、负值等属于结构/数值无效。之后单独处理概率质量，不能把全部异常都归为格式错误。

### 3.1 明确的首轮主线

**正式语义训练优先使用独立 gold 与可取得的高精度教师分布；JeV 两位小数分布先作为精度诊断分支。** 对已声明完整概率且仅有数值舍入误差的高精度教师，可以在记录原始总和后修正到单纯形；该误差容限作为固定校验配置保存，首轮默认 `1e-6`，不是对供应商概率真实性的保证。

若当前只有 JeV 两位小数分布，没有更高精度的合法教师，不能写成“任意 K 的完整概率监督数据已准备好”。可先用 gold/已审阅硬伪标签适配语义读出，并完成下述精度审计，再决定是否启用舍入分支。LLM 生成的硬标签绝不升级为高精度 native probabilities。

舍入分支的保守小试规则：

1. 保留教师原向量、原总和、位数、舍入方式及完整候选集合。
2. 原向量非零且十进制概率和恰为 1 时，可作为 **rounded proxy**，标 `transform=identity`；不叫原始 logits 或未舍入真实分布。对声明保留 d 位的小数，可用十进制整数单位 `10^-d` 做总和检查，避免二进制浮点误判。
3. 和不为 1 的舍入向量先隔离，不默认用 `r/sum(r)`，不加 epsilon 补齐质量，不把全零补成均匀分布。
4. 隔离只针对这份 teacher target；若同题有可信 gold，该题仍可进入 gold 训练。

为何不用无条件归一化：例如 nearest-rounding 的 `[1.00,0.01]`，直接除以 1.01 后第一项约为 0.9901，已经低于第一项对应的约 0.995 下界。一个代数上合法的分布，可能与观测的舍入区间不相容。

### 3.2 全零不一定无效，也不代表完全没有信息

只有**确认**为四舍五入到 d 位时，才使用如下区间（端点 tie 规则若不明，先使用保守闭区间）：

```text
δ = 0.5 * 10^(-d)
l_k = max(0, r_k-δ)
u_k = min(1, r_k+δ)
Q(r) = {q: Σq=1, l_k<=q_k<=u_k}
```

`Σl<=1<=Σu` 是这些箱约束与单纯形交集非空的条件。若 mode 不明，只能报告“在 nearest-rounding 假设下的诊断”，不能宣称这就是真实误差界。

- 区间不可行：与该舍入模型不相容，隔离并核查映射/元数据。
- 区间可行而原始和为零：无法作普通 KL 的点目标，但可能是合法低精度观测。例如 K=255、每类真实概率为 1/255 时，两位小数都可能是 0。
- 此时仍有弱约束：在上述舍入假设下每类最多约 0.005。因此“无法还原一个唯一分布”不等于“完全无信息”。

### 3.3 严格筛选必须通过覆盖审计

不能拿筛后数据直接代表原任务分布。先按任务族、题型、K、长度、来源、语言及不确定性可观测指标报告：输入数、可用数、全零数、区间不可行数、总和异常数、保留率。对于总和为 1 的样本可计算报告分布熵；对于全零等样本，真实熵未知，必须单列，不能用其伪零熵把它归成“高确信”样本。

**启用门槛：** 目标工作负载的每个必需分层都必须有可评估覆盖；观察到明显随 K 或不确定性变化的筛选偏差，就不能仅靠扩大筛后样本数宣布通过。此时按顺序选择更高精度输出/其他可用监督，或下面的显式近似实验。所有汇总同时报告筛选前的工作负载权重，不能悄悄改成剩余数据的频率。

没有为保留率设一个凭空的通用百分比：应在已知 workload、可接受的缺失范围和预算后冻结具体门槛；在门槛未定义或关键分层全失的情况下，这条舍入数据路线只是诊断实验。

### 3.4 两条可推翻隔离策略的实验

**代表点重建实验：** 在确认的 `Q(r)` 中选 `argmin_q ||q-r||²`，即 box-simplex projection。解可写为 `q_k=clip(r_k+τ,l_k,u_k)`，以二分求 τ 使总和为 1。必须标 `target_kind=imputed_distribution`，保留变换版本；这只是有依据的代表点，不是找回教师真实 p。全零的对称投影可能得到均匀分布，但必须明确这是投影的选择，不是观测到的教师分布。

**区间目标实验：** 不固定补出的点，而直接优化：

```text
L_interval(z,r) = min_{q in Q(r)} KL(q || softmax(z))
q*_k = clip(c * p_k, l_k, u_k),  c>0, Σq*=1
∂L_interval/∂z_k = p_k - q*_k
```

对 `log c` 二分，并使用稳定的 log-probability 运算，可得到满足边界的 q*；梯度用包络定理，q* 在反向传播时 detach。报告真实 KL 值，不能把随 p 变化的 q* 的 cross-entropy 数值冒充这一目标。边界处使用相应梯度/次梯度。

上述公式是约束 KL 的直接 KKT 推导：内部坐标有 `log(q_k/p_k)+1+λ=0`，加上下界/上界即得截断形式。若 p 已在 Q 中，loss=0，所以它允许一片平坦最优集合，不能识别区间内的真实概率。

这两条仅在恢复了必需 K/任务覆盖、数值检验通过，且独立 gold 上的 proper score 与风险指标没有实质退化时替代隔离主线。舍入误差很大时，应承认监督精度不足，而不是靠损失命名掩盖它。

## 4. gold 与 teacher 同时存在时，先解析语义再选目标

主线不使用“每题都加 0.5 gold CE + 0.5 teacher KL”。对同一个 x，两个来源混合的最优分布通常是两目标的加权混合；它可能既不是事实概率，也不是教师分布。

| 数据情况 | 主线 resolved target | teacher 的用途 |
|---|---|---|
| 同一输入/题意，有可信 deterministic gold | gold one-hot | 保留冲突审计；不对该题追加 teacher KL |
| 已知随机机制与可见信息解析得到的条件分布 | 完整 soft gold q | 单独比较教师，不把 q 压成 argmax；非实际事件校准证明 |
| 一次真实 outcome | outcome one-hot 的 proper loss | 概率质量在总体上评价；不把一次未命中叫确定性冲突 |
| 经规范定义的人类分布 | gold 计数归一化后的分布 | 单独比较；不与 teacher 无条件平均 |
| 没有可信 gold，有合格完整 teacher 分布 | teacher 分布/明确代理目标 | 训练来源标 teacher，不能进入独立 gold 测试 |
| 只有 LLM 硬标签 | one-hot pseudo-label | 标记 hard-label imitation，不称分布监督 |
| gold 与 teacher 使用不同输入快照、题意或候选 | 不建立同题混合；分拆或复核 | 先修正数据匹配 |
| 人类标签未裁决且与 teacher 不同 | 暂不升级为 gold；复核或单列弱标签实验 | 不按教师 confidence 大小决定谁是真值 |

金标准优先不意味着原地删除教师响应。把两份证据与 resolved policy 版本一同保存，可以比较“不模仿老师的错误”究竟提高了多少独立能力。主观分布里每题等权是第一版选择，标注人数作为不确定性元数据；不因某题有更多标注就自动改成更高业务权重。

## 5. 主损失只选 categorical log loss

对每题解析得到目标 `t_j`，它可能是 gold one-hot、gold 分布或合法 teacher 分布。主损失：

```text
log p_j = log_softmax(z_j over valid candidates)
L_j = -Σ_k t_jk * log p_jk

teacher_KL_j = Σ_k t_jk * (log t_jk - log p_jk)
             = L_j - H(t_j)
∂L_j/∂z_jk = p_jk - t_jk
```

因此对固定 teacher target，soft CE 与 `KL(teacher || student)` 有完全相同的参数梯度；teacher KL 用于单独的 fidelity 指标。不能反写成 `KL(student || teacher)`，后者对教师零值还有不同的定义域问题。[软目标研究](https://arxiv.org/abs/1503.02531)

为什么三类题先统一 log loss：它直接学习完整类别分布，在同一框架下支持硬/软监督，不需要为每种任务额外调三组 loss 系数。分类正确率、Brier 和 Score 的有序误差先作为评测，而不是全部叠加到训练损失。Brier/CRPS 是独立替代目标的消融；若 Score 的远距离错误是明确业务成本，再在同数据上比较有序 proper loss。仅拟合 Score 均值的 MSE 会遗漏不同分布具有同均值的情况。[proper scoring 理论](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)

软目标训练温度首轮固定 `T=1`。我们没有教师 logits，尤其舍入分布的零值丢掉了信息；把 `log(rounded_p)` 除以温度不能恢复丢失的信息。后验校准温度另在独立数据上拟合，不与软目标训练超参混用。没有默认 label smoothing、confidence 加权或额外 entropy bonus；它们都会改变正在拟合的目标，需要单独说明和验证。

### 5.1 可直接转为代码的稳定实现

下例假设进入此函数之前已完成 CPU/离线目标校验和全部有效题选择。`z,t,mask` 为 `[N_questions,K_max]`；t 在无效位置为 0，且每行和为 1。

```python
def per_question_losses(z, target, valid):
    # 所有行至少两个有效候选；不包含空问题或无监督题。
    assert valid.dtype == torch.bool
    assert valid.sum(-1).min() >= 2
    z32 = z.float()
    t = target.detach().float()
    assert torch.isfinite(z32[valid]).all()
    assert torch.isfinite(t).all() and (t >= 0).all()
    assert (t[~valid] == 0).all()
    assert torch.allclose(t.sum(-1), torch.ones_like(t[:, 0]),
                          atol=1e-6, rtol=0)

    logp = torch.log_softmax(z32.masked_fill(~valid, -torch.inf), dim=-1)
    # 先去掉无效 logp，再相乘，避免 0 * -inf -> NaN。
    safe_logp = logp.masked_fill(~valid, 0.0)
    ce = -(t * safe_logp).sum(-1)

    # 数学约定 0*log(0)=0；clamp 只用于计算熵，没修改训练 target。
    tiny = torch.finfo(t.dtype).tiny
    t_log_t = torch.where(t > 0, t * t.clamp_min(tiny).log(), 0.0)
    forward_kl = ce + t_log_t.sum(-1)
    p = logp.exp()  # padding 正好为0。
    return ce, forward_kl, p
```

逐题 loss 在最后一个有效类别维度求和，再按定义的题权重聚合。不要直接对 padded `[N,Kmax]` 使用元素 `mean`，否则 Kmax 会改变损失尺度；也不要对 `[B,Q,K]` 直接 `batchmean` 后误以为已按题平均。PyTorch 的 `kl_div` 接受学生 log-probabilities，`mean` 与 `batchmean` 的分母不同；本方案直接写逐题公式避免歧义。[PyTorch KL API](https://docs.pytorch.org/docs/2.14/generated/torch.nn.functional.kl_div.html)

`forward_kl` 可能有浮点级微小负值，可在显示指标时报告容差，不要把训练梯度建立在粗暴 clamp 上。若有效 logit 已经 NaN/Inf，整个 logical batch 回滚诊断，不在 backward 途中偷偷丢题改变分母。

## 6. 先定义任务风险，再定义 sampler

设目标工作负载的任务族概率为 `ρ_f`。实际有部署频率时，以部署频率为主；没有时，首轮明确采用“任务族宏平均”目标，而不是声称符合真实流量。宏平均定义为：先等概率选 task family，再在其来源组、基础问题、改写版本内分层采样，避免改写数量多的来源自动获得更多权重。

```text
D*(j) = ρ_family(j)
        * P(source_group | family)
        * P(base_question | source_group,family)
        * P(variant | base_question)
R(θ) = E[j~D*] L_j(θ)
```

**首轮 sampler 直接实现 D***，因此被抽中的有效题权重为 1，logical batch loss 就是按题平均。不同 K、文本长度和同 state 的题数不额外加权。长度分桶只在已抽取的 logical batch 内重新安排计算，不能优先挑短题来“填满显存”后改变抽样分布。

若把难例或稀有任务过采样到 `P(j)`，必须选择并记录下面两者之一：

- 接受新的训练目标就是 P，并同时在固定 D* 上评测；这是 curriculum/重采样，不是假装无偏。
- 仍要估计 D* 风险：用 `w_j=D*(j)/P(j)`，无偏 Monte Carlo 估计为 `(1/N)Σ_j w_j L_j`。这里分母是抽样题数 N，**不是 `Σw`**。

`ΣwL/Σw` 则是自归一化重要性估计，有限样本一般有偏。另一种合理用途是：我们预先定义的有限批风险本来就是权重平均，那么分母当然为 `Σw`。两种目标不能混用。“每个任务算 mean 后相加”也意味着任务等权，而不是全题等权。

为了限制变量，首轮不使用重要性加权，不按 teacher confidence 采样，不采用 hard-negative mining。后续需要难例时，只在 train 内加入并保存新的抽样概率与分层覆盖；已锁定测试不参与选例。

## 7. variable K、token microbatch 与 DDP 的准确分母

第一版有效全局 logical batch 默认 **128 道完整问题**。这是可调整的试验默认，不是测得最优值。先抽取 128 题，解析目标并检查长度，然后分给各 rank；每个 rank 再按 token/attention 内存预算把完整题组装成 microbatch。

每个 microbatch 把所属的全部 `(state,question,candidate)` 行一起前向。不同 microbatch 的候选数量、题数与 token 数可以不同，但它们的损失不能各自 mean 后简单平均。模型一次 optimizer update 的目标是整个 logical batch 的同一个题级风险。

### 7.1 单机与默认 DDP 的公式

设 world size 为 W。用 `a_j` 表示损失分子权重，用 `D` 表示这次全局 logical batch 已确定的分母：

```text
主线 D*=sampler：        a_j=1，D=N_global_valid_questions
显式有限批权重平均：     a_j=w_j，D=Σ_global w_j
无偏重要性估计：         a_j=D*(j)/P(j)，D=N_global_draws

rank r, microbatch m 的 backward loss：
L_rm = (W / D) * Σ_{j in (r,m)} a_j * L_j
```

默认 DDP 把各 rank 梯度平均，所以最终：

```text
(1/W) * Σ_r Σ_m ∇L_rm = (1/D) * Σ_all j a_j * ∇L_j
```

单机取 W=1。已经使用这个公式后，**不能再除以 microbatch 数或 gradient_accumulation_steps**。分母可以在 forward 前从 CPU manifest 计算并 all-reduce；无监督、隔离、K=1 和补齐用的零权重 dummy 均不计入主线有效题数。真实尾批使用真实分母，不硬除以 128。

以下代码展示默认 DDP 梯度平均下的主线，pack 过程须在所有 rank 上协调同步次数：

```python
logical = draw_and_validate_global_questions(target_count=128)
rank_plans = assign_whole_questions_and_pack(logical, token_budget)
# 各rank相同microbatch次数；必要时补一个完整但权重为0的dummy题。
plan = rank_plans[rank]
D = all_reduce_sum(sum(j.objective_denominator_weight for j in plan.real_questions))
if D == 0:
    skip_update_on_every_rank()
else:
    optimizer.zero_grad(set_to_none=True)
    for m, mb in enumerate(plan.microbatches):
        sync = (m == len(plan.microbatches) - 1)
        ctx = nullcontext() if sync or W == 1 else ddp_model.no_sync()
        with ctx:                    # 必须同时包住forward和backward
            z = ddp_model(mb.inputs) # 候选行一次forward，随后scatter到题×候选
            ce, kl, p = per_question_losses(z, mb.targets, mb.candidate_mask)
            loss = (W / D) * (mb.numerator_weights * ce).sum()
            loss.backward()
    torch.nn.utils.clip_grad_norm_(trainable_parameters, 1.0)
    optimizer.step()
    scheduler.step()
```

这里 `objective_denominator_weight` 在主线为每题 1，在固定权重平均为 w，在无偏 IS 为每次抽样 1；dummy 始终为 0。需要 AMP scaler 时应在整个 logical batch 最后 unscale、clip、step，而不是每个 microbatch 单独更新。

上述公式假设没有改写 DDP reduction 的通信 hook。各 rank 应有相同同步计划；第一版不用 uneven-input join 改变有效 world size。`no_sync` 必须覆盖 forward 与 backward。这些行为以 PyTorch 文档为准，项目实现应固定安装版本，而不是无意跟随文档 latest。[DDP 官方说明](https://docs.pytorch.org/docs/2.14/generated/torch.nn.parallel.DistributedDataParallel.html)

### 7.2 大题与内存边界

首轮 profiler 起点：每个 rank 每 microbatch 约 8,192 个**实际序列化候选行 token**，最长单行先按 2,048 token 的实验桶测量。它们只是内存测量起点；attention 还受最长序列与 padding 影响，不把 token 数当成唯一显存公式。

若一题的完整候选集超出 microbatch 内存，先降低同批其他题数量；整题仍放不下时，走下一节的两遍梯度缓存。比如 K=32、每行约 2,048 token，单题已约 65k token，8k 的行 token 预算确实不能容纳完整图。不能悄悄截掉候选、问题或关键信息，也不能拿各块独立 softmax 代替。

训练的梯度累积可以有多次 forward；推理 batch 是否一次 forward 返回是另一个验收项。对一次完整 logical batch 与不同 microbatch 划分做梯度一致性校验时关闭 dropout，并控制随机性；正常浮点累加顺序差异用 dtype 对应容差处理。

### 7.3 超大候选组：两遍梯度缓存的准确链式法则

第一版选择支持这个路径，以免训练覆盖只剩小 K。将模型显式分为 `H=encoderθ(candidate_rows)` 和 `z=headφ(H)`；H 仅保存每个候选的 readout 向量，不保存全部 token 层激活。候选可独立编码，全部候选的耦合损失在 head/组内 softmax 阶段计算。这是梯度缓存/重算的思想，和把训练用 KV 永久 detach 后丢失前缀梯度不同。[Gradient Cache 原论文](https://aclanthology.org/2021.repl4nlp-1.31/)

对一题或一组完整题，执行：

1. 参数不变，dropout=0，按候选行 chunk 做 `no_grad` 编码；拼成全部候选的 H。
2. `H_leaf=H.detach().requires_grad_(True)`，运行完整 head 与全候选 loss；仅在此处应用一次全局损失权重/分母，backward 得到 head 的参数梯度和 `V=∂L_scaled/∂H_leaf`。
3. 原样逐 chunk 重算 encoder，令 `surrogate=Σ H_recomputed*V_detached`，对 surrogate backward；将梯度累积到 encoder 的 LoRA/可训练参数。
4. 全 logical batch 的正常组与超大组都完成后，统一同步梯度、clip、optimizer step 一次。

理由：`∇θ L = Σ_chunks (∂H_chunk/∂θ)ᵀ V_chunk`，同时 head 的 `∇φL` 已在第 2 步计算。V 已包含任务权重与全局分母，重算时**不要再次除以 D、K、chunk 数或累积步数**；不要再次运行 head backward；也不要在候选 chunk 之间 step/zero_grad。

```python
def cached_group_backward(encoder, head, group, numerator_weights, scale):
    # scale 的定义见下方；encoder/head 参数集合互不重叠。
    chunks = split_complete_candidate_rows(group.inputs, token_budget)
    with torch.no_grad():
        H = torch.cat([encoder(chunk) for chunk in chunks], dim=0)
    H_leaf = H.detach().requires_grad_(True)
    z = head(H_leaf, group.layout)  # 回填完整的题×候选
    ce, _, _ = per_question_losses(z, group.targets, group.valid)
    L_scaled = scale * (numerator_weights * ce).sum()
    L_scaled.backward()            # head参数梯度 + 叶子H梯度
    V = H_leaf.grad.detach()

    for chunk, row_slice in zip(chunks, group.chunk_slices):
        H_recomputed = encoder(chunk)
        (H_recomputed * V[row_slice]).sum().backward()
    # 这里没有optimizer.step，也没有第二次缩放。
```

两遍之间必须固定：参数、tokenization、position IDs、attention mask、候选顺序、计算精度与随机状态。本主线将 dropout 设为 0，因此无须为每个 chunk 回放 dropout RNG；以后启用随机层必须回放对应 RNG。带会更新统计量的模块也不能无说明地执行两次。头与 encoder 若共享可训练参数，需另行推导两条路径的合并；本主线使用独立拷贝的 scalar head，避免这一问题。

**分布式路径选择必须一致。** 首轮先在 W=1 验证上式。为避免 autograd 缓存头与默认 DDP hook 的交互，超大组训练的首个多卡实现采用一个独立、明确的同步模式：各 rank 使用参数一致的模型副本，关闭自动 DDP reduction，所有正常组/缓存组均用 `scale=1/D`，全部累积完成后对每个可训练参数梯度执行一次 `all_reduce(SUM)`，再 clip 和 step。不乘 W，也不再除以 W。不存在本 rank 梯度的参数以零张量参加相同顺序的归约。该模式与第 7.1 节的默认 DDP 模式二选一，不能叠加；所有 rank 通过同一 run 配置选择，禁止各自临时切换。

若之后要复用默认 DDP 的平均归约，必须把完整缓存流程接入一致的 no_sync/最终同步控制，并使用 `scale=W/D`；在通过单机梯度等价测试前不启用该优化。通信次数是优化项，梯度定义不能改变。

这一方法把 encoder 的激活显存限制到一个行 chunk，但全部 H、head 图和梯度仍须放得下。单个候选序列本身超过设备/模型长度能力时，也不能靠候选分块解决：需要另选长上下文实现或明确报告该输入范围暂不支持。它不承诺任意长度、任意 K 都能在任何设备上训练。

## 8. 可执行的初始化、warmup 与 backbone 适配

以下超参是 **0.6B 左右 dense backbone 的首轮试验默认**，不是 JeV 配方、最优值或对当前 Mac 算力的承诺。训练设备与实际模型选定后先用一个完整 logical batch 测峰值内存和吞吐，再冻结运行配置。

### 8.1 读出初始化

若 checkpoint 有合适的 yes/no 词表读出，且两者是模板中可用的单 token，可用 `w0=W_yes-W_no` 初始化新的可训练 scalar head；这是保留已有评分先验，不是把二分类概率直接当作 Choice 概率。若没有合适读出，则 `w~Normal(0,0.02)` 作为随机新头。两条初始化路线在比较 base/instruct/reranker 时明确记录，不能把读出初始化差异偷偷算作 backbone 胜出。

首版 shared scalar head 不设全局 bias：`z_k=wᵀh_k+b` 中对所有候选相同的 b 在组内 softmax 中抵消，训练它没有识别意义。头从指定 readout 隐状态取值，padding 后的位置必须正确；不计算整词表投影，也不生成文本。

### 8.2 两阶段优化

令 N 为通过目标校验、属于 train 的有效题数，B=128。一次“名义数据遍历”定义为 N 次按 D* 的抽样；不是保证每题恰好访问一次。

| 阶段 | 可训练参数 | 更新数与优化器默认 | 目的与推翻条件 |
|---|---|---|---|
| H：仅新头适配 | 新 scalar head；backbone、LoRA 冻结 | 只对随机头启用；`S_H=min(50,max(1,ceil(0.25*N/B)))`；AdamW，lr=1e-3 | 避免随机头初期把噪声传给主干。已有读出初始化时默认跳过；若该阶段稳定但阻碍后续收敛，与直接联合训练比较。 |
| A：主适配 | scalar head + 主干 LoRA；原主干权重冻结 | `S_A=ceil(3*N/B)`；LoRA lr=1e-4，head lr=3e-4；warmup 前5%更新，随后 cosine 到初始lr的10% | 三次名义遍历作为先导预算。训练与未见源 dev 均欠拟合时才增加容量/步数；训练改善而 dev 变差时修数据/正则，不直接加训练量。 |

共同默认：AdamW `betas=(0.9,0.95), eps=1e-8`；LoRA matrix weight decay=0.01，scalar head weight decay=0；全局 grad norm clip=1.0。使用设备实际支持的 bf16，否则先 fp32；概率、log-softmax 与 loss 总在 fp32。第一版不同时引入 4-bit 权重，以便先区分模型/目标问题与量化误差；确有内存需求时，量化另作一项对照。

LoRA 首轮 `r=16, alpha=32, dropout=0`，目标是全部 Transformer attention 与 MLP 的主要线性投影，排除 embedding、整词表 LM head 和独立 scalar head。对 Qwen 类命名，可显式匹配 `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj`；启动时枚举实际命中层与参数数目，空匹配立即报错。不同架构不能照搬层名。新头单独保存；PEFT 的 `modules_to_save` 或自定义 state dict 要验证重新加载后输出一致。[LoRA 原论文](https://arxiv.org/abs/2106.09685)、[PEFT 配置文档](https://huggingface.co/docs/peft/main/en/package_reference/lora)

这里的“backbone 适配”首先指 LoRA 更新主干计算，并非解冻所有原权重。如果 LoRA 在训练集都持续欠拟合，先比较 r=32 或扩大目标层；仍不足且 dev 支持时，才做一次 full-finetune 对照，主干初始 lr=1e-5、head lr=1e-4，其余目标与数据不变。不能因为模型 small 就默认全量训练更好。

阶段边界重建优化器与 scheduler 并记录，不把头阶段的动量无说明地混进不同参数组；比较初始化或算法时遵循相同规则。每约 `ceil(N/(4B))` 次更新评估一次 dev，至少间隔一次更新；固定预算内保存 gold dev NLL 最好的 checkpoint。没有独立 gold dev 就只能选 fidelity checkpoint，并明确尚无实际能力选模依据。

首轮固定 seed=0，用于实现比较；只有进入最终比较的方案再用至少其他独立 seed 检查结论是否稳定，而不是把单个幸运 seed 当成证据。更换数据分布、结构或监督策略时，重新生成 run manifest。

## 9. 后验校准、选模与最终评测必须分开

四份互不泄漏的数据用途：train 更新模型；dev 选择结构、超参与 checkpoint；calibration 只拟合最终模型的校准参数；locked test 只作最终比较。按原始来源/任务规则族分区，同源改写不得跨区。OOD test 另外保留未见任务族；不能用它反复调参后继续称未见。

### 9.1 后验校准的首轮实现

冻结学生，缓存 calibration 集的未校准 logits。只拟合一个全局正温度 `T=exp(τ)`：

```text
τ*=argmin_τ Σ_j a_j * CE(gold_j, softmax(z_j / exp(τ))) / D
```

首轮 `τ=0`，FP64 优化这一标量，最多 50 次 LBFGS 迭代；目标非有限或未降低时保留 T=1 并报告。该数字只是优化默认。拟合使用独立 gold 的相应 log-loss 定义，不使用 teacher confidence。题型专属温度、按 K 的温度函数等暂不引入；只有全局 T 在足够独立数据上呈现明确分层失配时，再将复杂校准器当作新的 dev/calibration 设计。[温度校准原论文](https://proceedings.mlr.press/v70/guo17a.html)

标量 T 不改变 Choice argmax，但可能改变 Score 期望、阈值策略和分布集中度。校准后由分布重新计算确定性 confidence 字段；这个字段本身不是校准证据。共享温度不能修复未学到的语义，也不保证 OOD 校准。

### 9.2 两套证据分开报告

| 证据面 | 数据 | 首要指标 |
|---|---|---|
| 教师 fidelity | 固定 teacher 响应，注明 full precision / rounded proxy / imputed / interval | `KL(t||p)`、TV、argmax 一致率；Score 另报期望差。舍入区间数据额外报可行性/区间目标，不把点目标误差当真实 teacher KL。 |
| 实际概率质量 | 未用于训练/校准的独立 gold | NLL、Brier、按业务定义的准确率/宏F1、Score 等级/期望误差、可靠性图与 risk–coverage；每项按任务族、K、语言、长度和 OOD 分层。 |

未校准与校准后的两套结果都保留。校准可能改善 gold NLL 同时远离 teacher；这不是记录冲突，而是两个目标确实不同。对 teacher 只有硬标签的样本只报告标签模仿指标，不伪造分布 fidelity。

提供基率/均匀等明确基线；校准误差低但分辨率低的模型不能过关。固定请求频率加权结果与任务宏平均并列，不用任一平均数隐藏关键任务失败。置信区间按来源组重采样，避免把同一文档的多个改写当成独立样本。代码组合工作流另外测最终成功率与阈值后错误成本，不能把边际概率默认独立后相乘。

## 10. RL 只作同 checkpoint 的严格对照

官方没有公布可直接照搬的 RLCD reward；以下是我们的实验。它只从同一问题的 categorical 分布中采样候选决策，不采文字、CoT 或隐藏思维步骤。

### 10.1 为什么不先用 RL

当前 p 是显式可微的 K 维分布，gold 或固定软目标也已经可用。CE/Brier 可以直接反传，梯度不需要离散采样估计。仅仅把负 loss 称为 reward 没有添加可学习信息；换成 policy gradient 反而增加采样方差。

若未来结构确实只提供不可枚举的随机输出、动作改变环境或需处理外部长期反馈，再讨论 RL 的独特需要。单条数据只有一个 outcome、标签迟到或教师黑盒，并不自动使监督 proper loss 不可用。

### 10.2 同一 checkpoint 的三个实验臂

在主线选定的**未做后验校准** checkpoint 上复制相同模型状态。对每个实验臂重置优化器，使用相同 gold 训练样本、抽样顺序、步数和参数范围，并另报告 wall-clock 与采样数：

1. 继续直接 gold CE。
2. 改用直接 categorical Brier：`L_B=Σ_k(p_k-1[Y=k])²`。
3. 使用下面的 pair-reward REINFORCE，预期优化与第 2 臂相同的 Brier 目标。

与第 2 臂比较才能隔离“采样梯度”与“目标从 CE 改为 Brier”的区别。不能从 CE 训练到 Brier，再 RL，最后把累计收益都算作 RL。三臂不使用额外 entropy、KL-to-reference、PPO clipping 或 advantage standardization；需要它们时另开明确目标的消融。

### 10.3 奖励与正确梯度

对同一 p 独立采样 A、B，真实标签为 Y：

```text
R(A,B,Y) = 1[A=Y] + 1[B=Y] - 1[A=B]
E[R | x,Y] = 2*p_Y - Σ_k p_k² = 1 - L_B(p,Y)
∇E[R] = E[R * (∇log p_A + ∇log p_B)]
```

两条采样路径都必须进入 score-function。若用 baseline `b(x,Y,θ)`，只要不依赖本次 A/B 且在 policy loss 中 detach，减去它不会改变期望梯度。首轮甚至可直接使用解析 baseline `b=2*p_Y-Σp²`；它恰好说明这里已有显式概率，直接反传 Brier 更简单。

```python
# p, logp 是同一次前向的完整题内分布；训练dropout在三臂均为0。
cat = torch.distributions.Categorical(probs=p)
A = cat.sample()                   # [N]
B = cat.sample()                   # 独立的第二次抽样
R = ((A == Y).float() + (B == Y).float() - (A == B).float())
p_y = p.gather(-1, Y[:, None]).squeeze(-1)
baseline = (2 * p_y - p.square().sum(-1)).detach()
logp_a = logp.gather(-1, A[:, None]).squeeze(-1)
logp_b = logp.gather(-1, B[:, None]).squeeze(-1)
loss_pg_per_question = -(R - baseline).detach() * (logp_a + logp_b)
# 后续沿用同一题级采样、分母、DDP与gradient accumulation规则。
```

这里 R 不反传，baseline 不反传；p 的梯度通过所取 logp 流动。更新后下批重新采样，不复用旧策略的样本做多 epoch 更新。采两次候选不要求再跑两次 backbone，也不允许把“同样本抽到两个不同候选”作为强制约束；强制去重会改变联合分布并破坏上式。

如果使用多组独立 `(A_m,B_m)`，可用其他**独立 pair** 的 reward 作 leave-one-pair-out baseline。不要把共享 A/B 的相关 pair 奖励随便当成独立 leave-one-out 样本。组内除以随机 reward 标准差一般会改变估计器，可能造成过度自信；首轮关闭这种归一化。相关论文提供了随机结果任务中的具体反例，不等于所有 GRPO 都必然失败。[Uncalibrated Reasoning](https://arxiv.org/abs/2508.11800)

### 10.4 什么结果才能支持保留 RL

先在有限类别上精确枚举 A、B，核对 policy-gradient 的期望与直接 Brier 梯度相等，再比较实际采样方差。之后才跑相同初始化的模型实验。若 RL 只提高采样 reward 却降低独立 gold NLL/Brier 或跨任务风险表现，不保留。

如果 pair-RL 与直接 Brier 同样好，没有理由只为名称采用更复杂的训练器。只有稳定的独立评测收益、适用的计算优势，或后来确实出现不可直接求梯度的结构约束，才支持增加 RL。即使它胜出，发布名称也应为我们的 pair-reward 方法，不声称得到了专有 RLCD 配方。

## 11. 训练前验收与决定推翻表

不建立只复述实现的庞大测试套件；保留会抓到真实算法错误的少量检查：

- 目标 ID 对齐、Boolean 互补、Score 序号和候选置换后的分布对应关系正确。
- 同一有效问题加 padding 不改变概率；同批增删另一问题/state 不改变当前输出，允许数值级浮点差异。
- 不同完整题 microbatch 划分、单机与默认 DDP 的全局梯度在关闭 dropout 后一致。
- 超大组梯度缓存与小规模可一次放入的完整图，对 encoder 和 head 的梯度都一致；分别检查 head 没有累积两次、V 没有二次除分母。手工 SUM 归约模式与默认 DDP 模式单独验证。
- 解析 CE 梯度符合 `p-t`；teacher forward KL 与 soft CE 梯度相同；零目标和 padded 槽没有 NaN。
- 舍入区间的可行/不可行、全零高 K、正常总和及 `[1.00,0.01]` 反例得到预期状态。
- pair reward 的枚举梯度等于直接 Brier 负梯度；采样不要求互异，不采思维链。

| 当前明确决定 | 什么证据会推翻它 | 推翻后的单一下一步 |
|---|---|---|
| 先统一 categorical log loss | 独立 Score 任务持续出现高代价跨级错误，且 ordinal proper-loss 对照稳定改善 | 替换 Score 目标做对照，不无条件叠加多个 loss |
| gold 优先，同题不混合 teacher | 某份 gold 的语义/可靠性经审查不成立 | 修正标签权威与定义，不用任意混合系数掩盖冲突 |
| 主线精确目标，低精度 teacher 先诊断 | 必需 K/不确定性分层被低精度严重破坏，且精度无法提高 | 比较显式 interval loss / projection；保留 imputation 与覆盖声明 |
| sampler 直接实现固定 D* | 部署流量变化，或稀有任务训练不足且困难采样有可重复收益 | 修改 D* 或显式记录 P/重要性目标 |
| 新头 warmup + LoRA | 同数据预算下联合训练、不同初始化或全量适配稳定更优 | 替换这一项，保留损失/数据/评测不变 |
| 首轮不把 RL 放进主线 | 同 checkpoint、同数据目标的受控对照证明额外收益，或结构确实无法直接反传 | 引入证据支持的 RL 机制，并记录新目标与梯度 |

最终 checkpoint 必须随附：base/tokenizer revision、序列化模板、candidate/Score 映射、LoRA 与头权重、训练目标策略、数据/分区哈希、D* 与 sampler、优化器/scheduler 状态及 RNG、全部超参、舍入处理与过滤统计、选模依据、校准 T，以及未校准/校准后的两套评测。只有这样，开源结果才是可复现的算法，而不是一个不知学了什么分布的权重文件。
