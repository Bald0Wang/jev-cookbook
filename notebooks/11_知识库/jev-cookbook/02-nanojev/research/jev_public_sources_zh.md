# Jev 公开资料核验（中文）

核验日：2026-09-17。范围：TypeSafe 官方网站、文档、官方 GitHub、创始人公开发言、官方演示及评测。本文件未使用 API、未读取 `.env`，未发生模型调用费用。链接与价格是本次观察，不作为未来版本的保证。

## 结论

Jev 最值得复现的是“用自然语言定义、面向任意候选集合的概率决策接口”，以及共享输入、多问题并行、校准和确定性代码组合的完整系统。公开证据不足以还原其专有网络和 RLCD 训练算法；可以实现相同接口和类似能力，再用公开、可重复的任务评测比较。

不能把 Jev 当成只有固定标签的传统分类器：任务指令、候选描述都来自每次请求。也不能把它当成聊天模型：它不输出新文本、代码或解释。准确率、概率校准、有效输出率、延迟是四个不同指标。

## 公开可确认的接口与实现信息

| 项目 | 核验结果 | 直接来源 | 资料日期 |
|---|---|---|---|
| 输入 | `state` 可为文本、JSON 对象、文本数组；当前不支持图像、音频、视频 | [System One](https://docs.typesafe.ai/concepts/system-one) | 未标注；访问 2026-09-17 |
| 任务定义 | 每次传入 `questions`，含题型、自然语言 instructions、必要的 criteria | [Primitives](https://docs.typesafe.ai/primitives) | 未标注；访问 2026-09-17 |
| Choice | 返回候选、完整概率分布、confidence；最多 255 个选项；选项名称和描述会进入模型，question id 不会 | [Choice](https://docs.typesafe.ai/primitives/choice) | 未标注；访问 2026-09-17 |
| Score | 2–10 个有描述的有序 level；返回完整分布和 `score=Σ i·p_i`；level 数字和相邻 level 不给模型，每个 level 单独判断 | [Score](https://docs.typesafe.ai/primitives/score) | 未标注；访问 2026-09-17 |
| Noul | 返回“是”的概率 0–1；不返回独立 confidence；可附加 true/false 的说明 | [Noul](https://docs.typesafe.ai/primitives/noul) | 未标注；访问 2026-09-17 |
| 问题隔离 | 多个问题针对同一 state 并行、独立计算；一个问题不能读取另一个问题的结果 | [Introduction](https://docs.typesafe.ai/introduction) | 未标注；访问 2026-09-17 |
| confidence 的含义 | 从概率分布确定性计算出的集中度统计量；不是另一份独立的“正确率预测” | [Confidence](https://docs.typesafe.ai/confidence) | 未标注；访问 2026-09-17 |
| 当前模型 | `jev-1.13.0`；`jev-latest` 和 `jev-preview` 此时都指向它 | [Models](https://docs.typesafe.ai/models.md) | 未标注；访问 2026-09-17 |
| 输入价格 | 官方 $0.042 / 百万输入 token，输出免费；官方列出动态限流 250,000 token/s、1,200 请求/min | [Models](https://docs.typesafe.ai/models.md) | 未标注；访问 2026-09-17 |
| 上下文 | state+全部 questions 共 64k token；state+最长单 question 为 32k token | [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md) | 最后复核 2026-09-16 |

“每个问题独立”是接口语义和官方性能叙述；公开材料没有给出 attention mask、共享 KV、encoder/decoder 层数或实际 GPU kernel，不能由接口唯一反推网络结构。

### 可直接参考的 confidence 公式

官方 MIT 开源 LLM adapter 里存在完整公式，见 [confidence_metrics.py](https://github.com/typesafe-ai/system-one-adapter-python/blob/main/src/system_one_adapter/_utils/confidence_metrics.py)（仓库本次观察更新至 2026-09-17）。这是官方 adapter 的公开实现，不是 Jev 服务端源码的公开证明。

设归一化概率为 `p`，候选数为 `K`：

```text
choice_confidence = (max(p) - 1/K) / (1 - 1/K)

m = argmax(p)
d = Σ p_i * |i - m|
d_uniform = (1/K) * Σ |i - (K-1)/2|
score_confidence = max(0, 1 - d/d_uniform)
```

K=1 时返回 1；总概率为零时源码先使用均匀分布。OpenJev 可以采用这些公开公式保持可理解的兼容行为，并保留 MIT 许可。应另外做校准评测，不能把这个统计量当作校准训练本身。

## 尚未披露的核心技术

| 问题 | 证据边界 | 来源与日期 |
|---|---|---|
| 网络结构是否公开 | 创始人明确表示架构目前保密，团队讨论过写论文；其认为数据更值得关注 | [创始人 HN 回复](https://news.ycombinator.com/item?id=49718824)，2026-09-15 20:57:35 UTC，访问 2026-09-17 |
| 参数量 / 基座 | 官方仅称 Jev 并非“小模型或 LLM”；未披露参数量、基座名称、dense/MoE、encoder/decoder 结构 | [发布博文 FAQ](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，页标日期 2026-09-14 |
| RLCD | 公布名称及目标：针对决策与概率校准进行后训练；未公布 reward、loss、采样算法、优化器、数据量或算力 | [AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer)，未标注，访问 2026-09-17 |
| 训练数据 | FAQ 自称主要是数据研究团队，自己制作所有数据，未给出数据清单及生成/标注配方 | [发布博文 FAQ](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，页标日期 2026-09-14 |
| 训练及推理代码 | 官方公开 SDK、agent skills 和 LLM adapter；在本次查看的组织公开仓库中未发现 Jev 权重/训练源码 | [官方 GitHub](https://github.com/typesafe-ai)，访问 2026-09-17 |

FAQ 折叠内容在普通搜索正文中未完整显示，本次通过官方 HTML 的页面数据读取核验。官方组织存在 LLaDA、vLLM 的 fork，但“fork 过某项目”不能证明 Jev 使用该架构。

## 性能宣称怎样理解

官网的 193.6× 更快、444.6× 更便宜来自自家的工作流比较。发布文也承认这是现实收益区间的较高一端、短输入演示对 Jev 有利、测试通常从美国西海岸发起。所谓“零幻觉”的数值来自输出 schema 的构造性保证，而非对所有语义错误的统计。来源：[发布博文](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，页标 2026-09-14；[官网](https://typesafe.ai/)，访问 2026-09-17。

官方评测的四个场景是安全事件、Agent trace 监控、发票处理、客服。每个模型使用同一工作流；参考标签由 GPT-6 Astra 与 Claude Fable 5.1 的高推理设置答案取平均产生，其余模型按 provider 默认推理设置运行，最终四任务等权聚合。它测的是对参考模型共识和工作流决策的一致性，并非人工真值证明。来源：[评测总览](https://evals.typesafe.ai/)，访问 2026-09-17。

| 可复核程度 | 发现 | 直接来源 |
|---|---|---|
| 方法和部分轨迹可审阅 | 有业务规则、流程图、挑选的分歧样例，以及模型读到的 state 和每个问题答案的交互入口 | [安全事件](https://evals.typesafe.ai/security_incidents)、[发票处理](https://evals.typesafe.ai/invoice_processing)，访问 2026-09-17 |
| 通用对照适配器已开源 | 支持 probabilities/discrete 两种答题方式、结构化输出、重试、token/latency 统计 | [system-one-adapter-python](https://github.com/typesafe-ai/system-one-adapter-python)，MIT，访问 2026-09-17 |
| 全量端到端复现尚未确认 | 此次未获得四个评测的完整可下载数据集、单命令执行脚本、所有逐样本输出及确切模型快照；因此不能声称独立复现了倍率 | [评测总览](https://evals.typesafe.ai/)，访问 2026-09-17 |
| 公共 benchmark | FAQ 明确表示故意不公布常见公共 benchmark，主张用户按自己的场景测试 | [发布博文 FAQ](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，页标 2026-09-14 |

创始人也直接承认模型可能自信地答错：[HN 回复](https://news.ycombinator.com/item?id=49718780)，访问 2026-09-17。因此 OpenJev 的合理目标必须同时包含实际标签正确率、Brier/NLL、校准和错误时的自动执行风险。

## Demo 与可用场景

以下区分“演示实际做过什么”与“官方建议可能适合什么”，不把应用目录当成生产效果证明。

| 场景 | 实际公开内容 | 对 OpenJev 的启发 | 来源、日期 |
|---|---|---|---|
| Doom | 结构化文字游戏状态输入，非图像视觉；约 10 次决策/s，官方估算约 $7/h；演示指令条件下行动 | 可以用程序提供 state，再并行预测移动/射击等动作；不需先复现 VLM | [发布博文 Doom](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，2026-09-14 |
| Wikiracing | 从可见 Wikipedia 链接中选下一跳；超过 255 个候选时先打分再选择 | 验证动态候选、高基数分类和排序，比聊天 demo 更贴合能力 | [发布博文 Wikiracing](https://typesafe.ai/blog/introducing-system-one-models-and-jev)，2026-09-14 |
| 智能家居 | 一次预测请求类型、房间、设备、动作；代码只使用相关字段；复合请求拆解/聊天由 LLM 处理 | 第一个本地演示可用文字指令→类型化控制；包含模型路由 | [Smart home demo](https://docs.typesafe.ai/demos/smart-home)，未标注，访问 2026-09-17 |
| 一文多问 | GDPR 文章，13 个问题、5 次重复；官方结果批处理 0.27s/$0.000497，逐题总计 2.71s/$0.006090；使用 jev-1.12 | 最直接测试共享 state 的成本与延迟收益；原对照为串行，必须再加并发对照 | [Parallel questions cookbook](https://docs.typesafe.ai/cookbooks/parallel_questions)，2026-09 的实验，访问 2026-09-17 |
| 检索重排 | CLERC 的 40 条 query、3,565 passages，BM25 每次先取 30；官方例子 top-1 从 5% 到 18%，top-10 从 38% 到 62% | 这是小规模可运行示例，不能当完整领域 benchmark；适合先做 rerank baseline | [Re-ranking cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe)，未标注，访问 2026-09-17 |
| 值提取 | 先用 regex 找邮件、电话、金额候选，再让模型选择，代码还原原文值 | “不能生成字符串”仍能做抽取：span/candidate 选择即可 | [Pre-parsed value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)，未标注，访问 2026-09-17 |
| 应用目录 | 还包括客服分类、模型路由、RAG 过滤、引用核查、guardrail、特征提取、实体对齐、层级分类 | 这些是任务分布的候选，不是已证实的统一准确率 | [Use-case map](https://docs.typesafe.ai/concepts/use-case-map)，未标注，访问 2026-09-17 |

批处理 cookbook 的大多数答案重复一致，但两项 Noul 有波动；应报告重复请求的实际概率差，而非宣传绝对确定性。其“无批处理影响”来自这个小例子，不能代替跨领域不变性测试。

## Twitter / X 核验

X 普通网页在本环境返回 403。本次经 X 官方 `publish.twitter.com/oembed` 公共接口成功核验以下帖子的作者、日期和可嵌入文本；没有把第三方线程镜像当成额外技术证据。

| 账号 / 帖子 | 核验到的内容 | 日期 | 链接 |
|---|---|---|---|
| 官方账号 | 官网页脚指向 `@typesafeai` | 访问 2026-09-17 | [官方 X](https://x.com/typesafeai)、[官网](https://typesafe.ai/) |
| 创始人发布帖 | Diogo Almeida 宣布 Jev、RLCD，提出 20–200× 速度、40–400× 成本方面的宣称；属于厂商发布 | 2026-09-15 | [发布帖](https://x.com/CompleteSkeptic/status/2099925682726002904) |
| 创始人技术回复 | 强调 zero-shot 加通用性带来的可编程性，认为共享能力核心可能利于维护和泛化；未给出具体网络结构 | 2026-09-16 | [技术回复](https://x.com/CompleteSkeptic/status/2100067328620896408) |

oEmbed 的首发帖正文有截断，因此完整线程中的每一句话没有都得到 X 一手全文核验。线程里涉及的速度、并行、Doom 和 Wikiracing 已在官网博文交叉确认。

## 官方已知局限与必测边界

官方 Jev 1.13 局限页（最后复核 2026-09-16）列出：过度按字面理解、计数和精确数值弱、日期比较不可靠、复杂间接指代弱、无关长上下文降低准确率、state 内恶意指令会影响答案、指令与 criteria 冲突、不能高效做文本生成。来源：[Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md)。

OpenJev 的测试应该独立覆盖：中英文、长短 state、候选数变化、候选重排/重命名、多个问题同批与拆批、否定与反事实、缺少关键信息、多个正确/全部错误候选、注入内容、数据域外输入。抽样评估应有真实标签，不把 teacher 的自信程度当作标注真值。

## 面向复现的推断（非 Jev 架构事实）

1. **共享 state 表征 + 对 question/候选的条件打分**是合理实现候选。它能解释可编程题目、类型约束、各问题隔离、减少重复 prefill。具体用 cross-encoder、分支 attention、共享 KV 或 query cross-attention，应由准确率和吞吐实测决定。
2. **先训练概率分布，再做类型确定的转换**可覆盖三个 primitives：Choice 取 argmax，Score 取 level 期望，Noul 输出 Bernoulli 概率；无需为了这个接口生成 JSON token。
3. **不应把现成 LLM 的 masked-logit softmax 叫作 RLCD。** 它可以成为便宜 baseline，但输出有效、输出概率和概率已校准不是同一个结论。RLCD 专有算法尚未公开；有真实标签的适当评分损失与教师监督训练可以构成独立开源路线。
4. **数据是最大未知数。** 固定标签分类集只能覆盖一部分能力；可编程分类需要任务/规则/候选表述变化及未见任务测试。公开材料支持这一目标，但不揭示达到 Jev 能力的所需数据规模。

本文件只完成公开资料核验与能力边界分析；API 可用性、付费试测、条款和具体训练预算由主任务分别核查。
