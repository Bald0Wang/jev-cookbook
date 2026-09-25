# OpenJev 复现方案与本轮验证

> 更新入口：本文件保留早期调研语境。当前实现、已训练实验与最终决策见 [最新实施计划](implementation_plan_zh.md) 和 [真实实验报告](toy_experiment_report_zh.md)。

更新：2026-09-17。目标：先复现 Jev 最有辨识度的核心能力，形成可运行、可训练、可独立评测的开源原型。100 美元用于 API 调研与数据，训练资源另算。本文是本轮整合决策，详细来源和其他候选见文末附件。

**最新执行方向：训练前的核心特征调查已补充官网、X 原帖、创始人会议问答及 Discord 部分讨论。主结论见 [核心特征与技术重点](core_features_rlcd_zh.md)。RLCD、非自回归并行、动态候选泛化和代码组合共同决定路线；基座选择仍待同条件评测，当前没有开始学生训练。**

## 结论与优先决策

可以做出同类开源系统。应把目标定为「由自然语言定义的概率决策模型」，不承诺还原 Jev 的专有网络或完整能力。最快的路线是复用已学会语义判断的开放权重，以问题和候选描述为条件，训练直接输出类别概率的判别模型。

本轮已确定的实施重点：

1. **先冻结概率任务和并行契约。** 直接输出动态候选分布，不生成答案文本；跨 state 真实 batch 与同 state 多题隔离分别验收。创始人明确不允许其所称的 latent reasoning/CoT，复杂推理通过代码组合。[原始回复](https://x.com/CompleteSkeptic/status/2099981459541143995)
2. **概率学习与高效结构同步研究。** 独立 CE/Brier、完整分布监督作为基线；多样本适当评分奖励作为 RL 研究假说。RLCD 的目标已明确，具体算法未知，不能把某个现成优化器当成配方。[专项理论](rlcd_theory_zh.md)
3. **直接 LLM 初始化作为主线，具体 checkpoint 待测。** 同家族 Base 与通用后训练 LLM 加动态候选读出；Qwen3-Reranker-0.6B 降为任务迁移对照，GLiClass 为效率对照。此前优先 reranker 主要依据接入方便，没有证据证明其更适合通用决策。先构建查询分布，再比较未见任务、概率质量与真实负载。[初始化与查询分布补充](query_distribution_zh.md)
4. **教师可替换，独立真值保留。** Jev、开放 Qwen、可执行规则转换到同一记录，但完整分布、硬标签、投票与真实结果不能混成一种信号。当前只跑了 Jev 小演示，没有批量采集训练集；训练教师后定。
5. **展平 batch 建立正确性对照，共享 state 分支追求效率。** 两者都纳入设计；共享缓存/表征须通过题间隔离和概率一致性验证。不会把客户端异步请求数当成模型吞吐。

两项起点权重均标 Apache-2.0，但尚未有本项目训练结果支持其中任何一个最优。[Qwen3 Reranker](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)、[GLiClass](https://huggingface.co/knowledgator/gliclass-modern-base-v3.0)

## Jev 已确认是什么

官方接口输入 state 和任意自然语言 questions，输出 Choice、Score、Noul；Vercel 把 Noul 表示为 Boolean 概率。问题和候选在每次请求中定义，不是只支持训练时见过的固定类别。多题针对同一 state 独立计算。[官方介绍](https://docs.typesafe.ai/introduction)

| 原语 | 模型需要给出的信号 | 程序负责的后处理 |
|---|---|---|
| Boolean / Noul | 命题为真的概率 | 按应用阈值分支；原响应保留连续概率 |
| Choice | 给定候选集合内的完整分布 | argmax、候选名映射、集中度统计 |
| Score | rubric 每个等级的分布 | `sum(i * p_i)`、legend 和集中度统计 |

Score 的等级由文字描述，数字位置是后处理。官方文档明确每级单独判断，不看相邻等级。[Score](https://docs.typesafe.ai/primitives/score)

confidence 是分布的统计量，不是独立推理链或一份已验证的正确率。官方 MIT 开源 adapter 已有可参考公式，故无需额外训练一个 confidence head；但不能据此宣称掌握 Jev 服务端的精确实现。Choice 公式为 `(max(p)-1/K)/(1-1/K)`；Score 公式见来源附件。[Confidence 文档](https://docs.typesafe.ai/confidence)、[官方 adapter 源码](https://github.com/typesafe-ai/system-one-adapter-python/blob/main/src/system_one_adapter/_utils/confidence_metrics.py)

官方产品案例包括 Doom 的结构化文字状态决策、Wikiracing 链接选择、智能家居、Agent 路由、RAG 重排/过滤、引用核查，以及 regex 找候选后做值提取。这说明“不生成新字符串”仍可覆盖很多自动化环节。[官方演示](https://docs.typesafe.ai/demos)、[智能家居](https://docs.typesafe.ai/demos/smart-home)、[用例目录](https://docs.typesafe.ai/concepts/use-case-map)

官方宣称新架构、parallel sampler、RLCD；参数量、训练配方和数据集没有公开。193.6 倍速度、444.6 倍成本来自厂商自己的工作流测试，不是本轮已复现的指标。schema 有效不能推出语义无错误。[发布文](https://typesafe.ai/blog/introducing-system-one-models-and-jev)、[官方评测](https://evals.typesafe.ai/)

创始人的 X 发布及技术回复也强调可编程、零样本、通用性。本轮通过 X 官方 oEmbed 核验了作者和可嵌入正文，没有读取完整线程所有内容。[发布帖](https://x.com/CompleteSkeptic/status/2099925682726002904)、[技术回复](https://x.com/CompleteSkeptic/status/2100067328620896408)

## 本轮真实调用结果

首次请求返回免费层 403，随后用户给网关充值 25 美元。完成 15 次探测后，又完成教师适配器的 1 次 Jev 验证。最新余额读取与累计用量相符：

| 项目 | 实际记录 |
|---|---:|
| 成功请求 | 16（15 次探测 + 1 次适配器验证） |
| 总问题数 | 137 |
| 输入 tokens | 9,756 |
| 网关返回费用合计 | $0.000409752 |
| 余额接口返回 balance | $24.999590248 |
| 余额接口返回 totalUsed | $0.000409752 |
| 人工预先定义的简单判断检查 | 17/17 符合预期 |
| 前 15 次探测客户端时延中位数 | 约 277 ms |

这只是很小的接口/功能演示，不能作为准确率、校准或稳定延迟的估计。第一请求约 1.52 秒；不同题数每种仅测两次，没有足够样本估计 p95，也不能将差异归因于内部架构。批题实验使用相同问题的重复副本，只检验这一简单形态，不等于复杂多任务负载。

具体示例：中文「同一订单扣了两次钱，请退款；客服尚未办理」得到请求退款概率 0.97、已退款概率 0.02、billing 路由。中文「不要求退款，只是忘记密码」得到请求退款概率 0.03 和 technical 路由。缺少具体信息的例子选 unknown。

影响教师监督训练的实现事实：

- 当前返回 `rounding.probabilityDecimals=2`，`scoreDecimals=2`。拿到的是舍入概率，不是原始 logits。简单 Choice 经常接近 0/1，能提供的软标签信息有限。
- SDK 的 `answers` 中没有 confidence；它在 `providerMetadata.typesafe.confidence[question_id]`。不能因普通答案对象缺字段就认定模型未返回它。
- 每次返回了 gateway cost；余额累计用量与调用账本一致。
- 原始响应、路由信息和请求记录留在被忽略的 private 文件。本轮没有将这些变成训练集或向外发布。

演示可复跑：`npm run demo` 只做离线计划；`npm run demo -- --live` 执行探测。每轮最多 15 请求，预算估算阈值 $0.10，关闭自动重试、首次失败即停。此阈值是本地保守估算，不是供应商提供的账户硬扣费上限。

## 我们对结构和算法的判断

从公开语义推测，合理实现是共享 state 表征，加 question/候选条件化的打分分支，再做组内归一化。它可以由 encoder、causal decoder 或 cross-attention 结构实现。接口不足以决定它到底是 dense、MoE 或哪种采样器；本方案不把这些猜测当事实。

首版统一输入为：

```text
(state 的稳定序列化, question/instructions, 一个 candidate 的完整描述)
    → 共享参数的语义骨干
    → 一个标量 logit
    → 同题候选归一化
    → Boolean / Choice / Score 类型化结果
```

对 Qwen Reranker，可用已有 yes/no 读出初始化候选兼容性分数 `z_yes-z_no`，随后用目标任务分布训练。检索相关性分数本身并不等于命题真值，不能未训练就宣称成为 Jev。推理只计算判别读出，避免全词表投影和自回归 decode 的不必要开销。

模型必须看到 instructions 和候选语义：同一 state 换 policy/question 应改变答案。问题 ID 只用于输出映射，真正的问题是 `instructions`；候选的语义名称和描述都进入模型，另行分配的纯机器索引不作为标签语义。不能靠记住 `billing=0` 完成任务。Score 的序号在后处理阶段使用。

### 问题在哪里，yes/no 如何变成动态候选分布

对一个问题，训练单位是完整候选集合 `C={c_1,...,c_K}`。每行评分输入都显式包含 `state, question, candidate_name_and_description`。例如沿用 Qwen 模板时，`Instruct` 指定当前问题及判分要求，`Query` 放 state，`Document` 放当前候选；问题必须在分词后的模型输入中，不能只留在调用函数的元数据中。

```text
z_i = logit_yes(state, question, c_i) - logit_no(state, question, c_i)
p_i = exp(z_i) / sum_j exp(z_j)
L_question = -sum_i target_probability_i * log(p_i)
```

这里有两个不同归一化空间：原 reranker 在 yes/no 之间计算二分类相关性；学生在当前题的 K 个候选分数之间归一化。yes/no 读出只提供标量评分的初始化，最终输出长度由 K 决定。必须对整个候选集合计算 CE/KL 并反传，不能把多个二分类调用直接称为已训练的多选模型，也不能将各自的 sigmoid 分数直接视为互斥类别概率。[Qwen 官方评分代码](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)

所有候选评分行可同时进入张量 batch；这种实现不需要按候选顺序生成答案，但仍重复编码 state/question。共享前缀是另一个需要实现和测量的优化。

逐候选评分的代价是重复处理 state，且它存在候选集合交互限制：加一个候选后原两项的相对概率比不会改变。对“最接近本组平均值”之类集合依赖规则，这不是理想结构。此类问题要由代码处理，或在后续版本比较集合条件化结构；不能偷换为首版已支持任意复杂推理。

更精确地说，上述独立打分结构满足 `p_i/p_j = exp(z_i-z_j)`，其他候选不能改变这两个候选的相对赔率。Choice 的结构对照可改为 `z_i=g(state,question,C,c_i)`，在同一题内读取完整候选集合，仍不读取其他题或生成答案。Score 则依公开语义保留独立等级评分，不将 Choice 的集合交互机制默认套到 Score。

GLiClass 的原生多候选联合编码有较好的效率潜力，但应明确它与逐级隔离的语义差别。使用单候选模式时必须读取原始标量打分，再在当前题归一化；不能把单候选 softmax 恒为 1 的结果当学习信号。

第二阶段再做 state-only encoder + question/candidate cross-attention，或因果共享前缀/严格分支 mask。state 自身不得读到任一问题后再把信息传给别题。共享缓存版须与独立版在相同权重下做数值和行为对照；高效 CUDA attention 的收益也不能直接套到 Mac 后端。

## 数据：先导集与扩展路径

**先有查询分布，才有教师监督标签。** 当前没有 Jev 原始训练集或真实客户查询分布，也尚未准备好大规模 OpenJev 查询集。输入将来自开放判别任务及其指令模板、自写政策/状态机、语义 rubric 和工作流状态；教师对这些完整输入进行标注。具体来源、任务登记字段和生成过程见 [查询分布设计](query_distribution_zh.md)。不能只让教师生成大量普通问答就称为通用 Jev 输出监督数据。

首轮目标约 **2,000 个 state、8,000 个问题**，不是最低充分规模或效果保证。先把未见任务学习曲线跑出来，再考虑扩展至约 10,000–20,000 state。预算充裕不构成自动放量理由。

| 首轮任务 | 数据构造 | 关键对照 |
|---|---|---|
| 支持工单 | Banking77 原标签、自写工单/政策模拟器、语义改写 | 请求退款/已退款、规则变更、否定、信息缺失 |
| Agent 决策 | 自写工具定义与可执行状态机 | 新工具、缺参数、任务结束、重试条件、同状态换目标 |
| 证据核查 | 自写有真值的短材料、许可清晰的蕴含数据 | 支持/矛盾/未说明、引用错误、干扰信息 |
| 有序评分 | 明确可区分的 rubric 和边界样本 | 同均值不同分布、相邻等级、不同尺度 |

扩展到多语意图时可加入 MASSIVE，必须把同源翻译留在同一数据分区。Banking77、MASSIVE 为 CC BY 4.0，保留归因和修改记录；不同数据不要随意统一改成 Apache。[Banking77](https://huggingface.co/datasets/PolyAI/banking77)、[MASSIVE NOTICE](https://github.com/alexa/massive/blob/main/NOTICE.md)

样本记录至少包含：`state_id, family_id, source, license, state, question, candidates, target_kind, target, gold_if_available, teacher/model_revision, rounding, usage, cost, split`。教师原始输出与训练归一化结果分别保存。

四类信号分开：

1. **程序真值**：执行器算出，不需要买标签。
2. **已有人工标签**：只用于原本标注的语义，不把 neutral 当 false。
3. **教师概率**：Jev 为舍入分布；开放自托管 LLM 可读取限定标签 logits。
4. **LLM 生成标签**：属于硬标签；文本里自报的 0.95 不等于原始概率或校准正确率。

为避免词面捷径，要成组生成：同状态换问题、同问题改关键字段、同请求换规则、候选改名/换序、增加相近选项、注入干扰、缺乏答案。保留自然分布中的容易样本，也补充边界和分歧样本，不能只保留教师最自信的预测。

先按 state、源文档、翻译族、生成模板族划分 train/development/calibration/test，再进行衍生和标注。另设完全未见问题/任务族测试；随机拆 JSONL 行会严重泄漏。

## 训练与校准

首版目标：

```text
L = λ_soft · KL(p_teacher || p_student)
  + λ_gold · CE(y_independent_gold, p_student)
  + λ_order · mean((CDF_teacher - CDF_student)^2)    # 仅 Score
```

Boolean 使用同等意义的软目标 BCE。没有独立 gold 就不加该项；teacher argmax 不是第二份独立真值。有序 CDF 项保留等级距离，能表示双峰分布；不能只回归 Score 均值。

先以温度 1 学返回概率，之后用 development 集消融权重。教师舍入为 0/1 的丢失信息无法由升温恢复。保存原分布及和，依据已声明精度处理归一化，不悄悄截掉候选；学生用 log-softmax 保持数值稳定。

Qwen 原型先用短序列和 LoRA + 可训练判别读出减少实验成本；encoder 对照可做小学习率全参微调。按长度及候选数分桶、梯度累积，具体 batch/序列上限由实际显存决定。优先申请单张 24GB 级 GPU 做先导，但当前未租机，也未确认训练吞吐。

预测 token 工作量约为 `epochs × 问题数 × 平均候选数 × 平均输入长度`，逐候选路线应把重复 state 算进去。用先导实际吞吐估全程时间，不预先承诺几美元必然训练完。

训练后在单独 calibration 集拟合温度，最后在 test 集测 NLL、Brier、可靠性图和 risk-coverage。confidence 集中度只是接口字段，不能替代概率校准。[软目标研究](https://arxiv.org/abs/1503.02531)、[温度校准](https://proceedings.mlr.press/v70/guo17a.html)

## 判定原型是否成立

- **接口成立**：动态候选、合法类型、全量分布、Score 期望正确；问题 ID 和其他问题的存在不改变当前题含义。
- **语义成立**：未见任务/规则/候选上比未训练基线更好；同状态不同问题能区分；错误分析不只看整体 accuracy。
- **教师监督训练有用**：完整分布相对只用教师硬标签有可测收益；模仿教师与独立正确率分别报告。
- **概率有用**：独立测试上 NLL/Brier 与风险覆盖结果支持阈值决策；不能以少量命中宣称 calibrated。
- **效率有用**：同硬件、同 state 长度、题数/选项数下测 tokenization、模型前向和端到端时延；量化前后复测概率漂移。

第一轮学习对照：未微调学生、仅独立硬标签、加入教师硬标签、加入教师分布。概率目标与采样 RL 先在已知结果分布的环境下独立比较，避免同时更换结构、数据和优化器。若进步只出现在相同模板，修数据；若教师错，修标签；若跨域仍明显受容量限制，再升级骨干。

## 预算与执行里程碑

当前 Vercel 账户实际充值 25 美元；项目总 API/数据上限仍为用户给定的 100 美元，不自动追加充值。官方 Jev 精确价格是输入 $0.042/M token、输出 0；本轮 usage/cost 和这一价格一致。[网关模型目录](https://ai-gateway.vercel.sh/v1/models)

理论上 100M Jev 输入 token 为 $4.20，1B 为 $42。此乘法不包含未来价格变动、限流/失败或其他模型输出费，也不决定数据使用权。以本轮极简单样本推算通用训练量不可靠；接下来的约束首先是样本覆盖和标签质量。

预算封顶建议：先导/API 对照 $10，数据多样化 $45，难例复核 $20，独立评测数据 $10，余量 $15。当前仅充值的 $25 足够启动先导；不要为凑预算采重复标签。

本机 Fable 架构讨论及三次社交浏览的 CLI 标价累计 $6.60748725，主要模型为 `claude-fable-5-1`、xhigh，另有少量 CLI 辅助模型用量；它不在这次 Vercel 余额扣款里。是否由订阅覆盖以 Claude 账单为准。与网关费用合计的保守记账约 $6.608，实际支出仍应按两个账户分别核对。

| 阶段 | 交付与转入下一步的条件 |
|---|---|
| 已完成的调研与接口探测 | 公开证据、Fable 审阅、Jev 类型输出/精度/计费核验 |
| 原型与基线 | 已有可替换 teacher；待完成学生的非自回归 batch、Qwen/GLiClass 同集基线和问题条件性验证 |
| 先导训练 | 约 2,000 state，独立分区；硬标签与软分布消融 |
| 校准与错误修复 | 独立正确率、校准、泛化和时延有可审阅结果 |
| 定向扩数据 | 学习曲线支持继续扩展，费用账本有余量 |
| 首版发布准备 | 一个选定学生的权重、训练脚本、数据构建脚本、评测报告、模型卡与本地 demo |

经验性目标是 3–7 天形成能审阅的研究原型，前提是训练资源可用且先导有增益；本轮完成的是调研与 API 探测，尚未训练或发布 OpenJev 学生权重。

## 数据来源与发布边界

TypeSafe MCA §2.3(b) 明文涉及训练其他模型、模仿与竞争用途限制，§2.3(f) 涉及公开 benchmark。已向用户说明，用户决定先跑通少量演示，批量教师来源后定。本方案保留 Jev 与开放教师两条技术路径；批量训练和权重/数据公开之前，需要解决所选来源的适用授权。开源权重许可、托管服务条款、数据许可、输出使用权分别记录，不能由 API 可调用推导可公开训练。[MCA](https://typesafe.ai/legal/mca)

代码建议 Apache-2.0；权重保留基座条件；自有数据与外部数据分开许可。公开发布前保留源文件归因，剔除凭证、私有调用记录、未经许可的第三方聊天内容。不用开源发布来暗示与 TypeSafe 官方有关联。

## 附件

- [公开资料与来源审计](jev_public_sources_zh.md)
- [核心特征与技术优先级](core_features_rlcd_zh.md)
- [X、HN 与创始人会议技术讨论](rlcd_public_discussion_zh.md)
- [RLCD 理论与待验证实验](rlcd_theory_zh.md)
- [LLM 初始化与训练查询分布](query_distribution_zh.md)
- [模型、数据、损失与预算详案](training_design_zh.md)
- [Fable 5.1 xhigh 讨论及独立纠错](claude_review_zh.md)
- [Jev 演示脚本](../scripts/jev_probe.mjs)

Discord 已通过用户授权的本机 Fable Chrome 读取相关讨论并检索 RLCD、calibration、reward。覆盖为部分分页，未取得可核实的官方训练配方；私有摘要保留具体范围与原始记录。X 的 no-CoT 回复已核验到创始人原帖。
