# RLCD 公开技术讨论增量核查

访问日期：2026-09-17。本文补充 [原公开资料报告](jev_public_sources_zh.md)，聚焦创始人技术问答，不重复产品手册。事实、本人观点、社区猜测分别标记；“未公开”仅表示本次已检查的一手资料未提供该细节。

## 目前可以确认到哪一层

**RLCD 是 TypeSafe 的后训练路线名称，不是现成可下载的公开算法配方。** 官方全称为 Reinforcement Learning **for Calibrated Decisions**，强调输出决策概率的频率含义。官网把它画成从预训练语言模型出发的一条分支；这支持“利用预训练模型后训练”的方向，但没有公开底座、参数量、读取头或采样器实现。[官方 AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer)，未标日期。

RLCD 的重要性目前体现在目标和数据契约：输出须可用于决策，概率须与实际结果相符。**仅凭这个名称，不能决定 PPO、GRPO、REINFORCE、监督交叉熵或 Brier 中的任何一种就是 Jev 的真实训练法。** 同样，输出有效概率向量并不证明已经实现校准。

## 新发现：发布前官方会议中的技术问答

来源为会议主办方完整带时间戳转录：[Diogo Almeida — What's next after RLHF?](https://ai.engineer/talks/cJ0EOzey--o-whats-next-after-rlhf)。网站元数据：2026-07-31 上传，会议为 2026-06-29 至 07-02，具体演讲日未标。以下均属**本人技术观点/披露边界**，不是我们验证出的普遍定理。

| 时间与直接视频链接 | 短引与核查结果 |
|---|---|
| [14:08](https://www.youtube.com/watch?v=cJ0EOzey--o&t=848s) | 面对“分类头与预训练一起训练”的问题，他以复杂且时间不足为由，没有说明结构。 |
| [14:26](https://www.youtube.com/watch?v=cJ0EOzey--o&t=866s) | “I actually don't think that pre-training is the problem.” 他认为难点是引出已有能力，随后把偏好奖励导致自信表达的现象类比 GAN mode dropping。 |
| [15:43](https://www.youtube.com/watch?v=cJ0EOzey--o&t=943s) | “It is definitely not RLVR.” 明确否认只是另一种 RLVR。 |
| [16:19](https://www.youtube.com/watch?v=cJ0EOzey--o&t=979s) | “calibrated decision-making”：新目标是让预训练能力适用于软件决策。 |
| [16:41–16:53](https://www.youtube.com/watch?v=cJ0EOzey--o&t=1001s) | 观众追问奖励是否分散在过程而非末尾；他转而谈 API 形态，没有确认过程奖励或终局奖励。 |

因此，这段早期问答不能被转述成“创始人已经披露 dense reward”或“确认增加分类头”。

## X 发布链与回复：已核验和未核验分开

已核验项目通过 **X 官方 `publish.twitter.com/oembed`** 返回作者、正文及日期。发现链接的新闻/镜像只是入口，判断以原始 X 帖为准。长首帖的 oEmbed 正文会截断，不能把截断之外的镜像内容当成已独立核验。

| 一手链接 | 日期 | 证据性质和增量信息 |
|---|---|---|
| [发布首帖](https://x.com/CompleteSkeptic/status/2099925682726002904) | 2026-09-15 | **本人发布宣称**：约两年开发 RLCD 与 Jev。没有 reward/loss 细节。 |
| [发布链：并行对照](https://x.com/CompleteSkeptic/status/2099925684256899543) | 2026-09-15 | **本人解释**：“Jev can't generate text”；用并行替换顺序计算类比 Transformer 相对 RNN 的改变。类比不确定网络结构。 |
| [发布链：Doom](https://x.com/CompleteSkeptic/status/2099925687465570372) | 2026-09-15 | **本人演示/费用宣称**：约 10 次调用/秒、7 美元/小时；没有说明训练使用 Doom。 |
| [发布链：Wiki race](https://x.com/CompleteSkeptic/status/2099925688925184171) | 2026-09-15 | **本人演示**：高基数选择与不生成不存在选项的组合收益；没有证明长程规划或联合校准。 |
| [通用能力与微调回复](https://x.com/CompleteSkeptic/status/2100067328620896408) | 2026-09-16 | **本人观点**：“zero-shot + general == programmable”；大规模单一窄任务或可微调，共享能力核心可能有维护和泛化优势。没有给出微调 API 或数据配方。 |
| [回应 Chip Huyen 的推理问题](https://x.com/CompleteSkeptic/status/2099981459541143995) | 2026-09-15 | **本人明确披露**：“we actually don't allow latent reasoning (i.e. chain-of-thought)!”；目标是可靠的 System 1，System 2 由代码组合获得。已通过 Fable Chrome 原页与官方 oEmbed 双重核验。 |

发布链镜像呈现六条，我们核验了其中四条的原始 ID；剩余两条内容是成本与博客/Discord 引导，尚未取得各自原帖 ID。因此不声称已逐条完成六条一手核验。镜像只作发现入口：[Thread Navigator](https://threadnavigator.com/thread/2099925682726002904/)，镜像发布日期 2026-09-16。

**需要特别避免的来源误判：** [SFEIR 2026-09-16 文章](https://www.sfeir.com/articles/typesafe-jev-modele-decision-sans-texte/) 将“无 latent reasoning”“diffusion 提示”等具体回复都引用到发布首帖，脚注并没有对应回复 ID。它不能单独证明这些细节。我们已独立验证前者，后者仍未取得原始回复。

这句回复约束的是作者所称的 latent reasoning/CoT，不能外推成网络没有隐变量、没有多层计算、绝不迭代或不具备任何推断能力。直接可行的复现方向是保留快速决策接口，让代码组织跨步状态与推理；具体内部结构仍需独立选择。

### 本次 Chrome 核查范围与费用

用户授权本机 `claude-fable-5-1`、`xhigh`、最多 $2.50；实际总成本 **$0.77115775**，其中 Fable $0.76939775，CLI 的 Haiku 辅助 $0.00176000。终态成功，无 permission denial。Fable 自述的 $0.72 是结束前读数，结算以 CLI 结果为准。

工具审计仅有两次导航：[Chip 原帖](https://x.com/chipro/status/2099980710090248306) 和 [本人回复独立页](https://x.com/CompleteSkeptic/status/2099981459541143995)。没有导航到 replies 页、其它站点或 Discord；没有发送内容或修改设置，任务标签已关闭。没有读取回复下方的 14 条子回复。

X 页面显示本人回复为 2026-09-15 2:59 PM，未标时区；官方 oEmbed 再次确认作者和日期。由公开状态 ID 按 Snowflake 编码计算出的 UTC 为 `2026-09-15T21:59:30.380Z`，此精确时间是编码推导，不是页面直接显示。

本地私有审计文件：`private_x_latent_prompt_zh.md`、`private_x_latent_claude_stream.jsonl`、`private_x_latent_claude_stderr.log`。原始浏览日志仅本地保留，不作为公开数据集发布。

## HN：本人答了什么，哪些具体问题没有回答

下列日期从 HN 原始 HTML 的绝对时间属性读取，均为 UTC。旧报告里架构回复的相对日期已修正为 9 月 15 日。

| 一手链接与时间 | 分类 | 对复现有用的内容 |
|---|---|---|
| [49718824](https://news.ycombinator.com/item?id=49718824)，09-15 20:57:35 | 本人明确披露 | 架构暂保密，考虑写论文；认为数据更有意思。 |
| [49719101](https://news.ycombinator.com/item?id=49719101)，09-15 21:24:48 | 本人认可的高层类比 | 对“用动态候选替换固定词表、直接输出分布”的社区解释回复“very accurate!”；偏好称 zero-shot。不能升级为具体 attention/head 实现。 |
| [49718849](https://news.ycombinator.com/item?id=49718849)，09-15 20:59:20 | 本人观点 | 认为简单屏蔽不合法 logits 会掩盖模型困惑。没有给出对 constrained decoding 的受控消融。 |
| [49719245](https://news.ycombinator.com/item?id=49719245)，09-15 21:41:15 | 本人定位 | 通用任务无需用户逐任务训练；优先人类判断型任务。不能把这里的无需训练解释成模型未经过训练。 |
| [49719816](https://news.ycombinator.com/item?id=49719816)，09-15 22:37:18 | 本人披露的用途边界 | Astra/Fable 用于 eval；没有说用它们做训练 teacher。 |

最关键的是，社区已经直接提出了我们关心的问题，而当前原线程未见对应答复：

- [tidewave，09-15 20:42:51](https://news.ycombinator.com/item?id=49718646)：相对概率分类微调，RLCD 的目标究竟改了什么？收益是否与架构/并行分离验证？
- [tensegrist，09-15 21:24:37](https://news.ycombinator.com/item?id=49719097)：概率的认识论含义、世界知识先验和保证是什么？
- [Mentlo，09-15 21:50:57](https://news.ycombinator.com/item?id=49719359)：跨领域、跨结构如何维持校准？

这些是**社区问题，尚无一手答案**。另如 [porridgeraisin 09-17 的置信错答惩罚解释](https://news.ycombinator.com/item?id=49738448) 是**社区推测**，不是官方配方。

另有 [thduabmd，09-16 00:34:20](https://news.ycombinator.com/item?id=49720703) 指出单题校准不自动保证组合决策可靠。这条社区质疑适合作为 OpenJev 的 workflow 评测要求，不是厂商已经验证的能力。

## 对训练决策仍缺的信息

| 关键问题 | 已有证据允许的判断 | 仍未知，不能猜成事实 |
|---|---|---|
| 为什么是 RL 而非监督 proper scoring？ | 官方强调目标不同；已有直接社区追问 | 是否有不可微采样、在线环境、序列信用分配，或仅将某类目标命名为 RL |
| reward / loss | 概率要与结果频率对应 | log score、Brier、组合奖惩、KL、entropy、advantage 与优化器 |
| ground truth | 官方说训练数据自行制作，未披露制作方法 | 人工/可验证程序/teacher/混合比例，重复标注和歧义处理 |
| epistemic / aleatoric | 返回可供代码用的概率；单次答案不获保证 | 是否显式分解，两者各自的训练标签和估计器 |
| parallel sampler | 多输出可并行；不能生成任意顺序结构 | 一次前向或迭代、扩散与否、步数、共享 state KV、attention mask |
| 校准泛化 | 有目标宣称和集中度 confidence 接口 | 独立校准集、跨任务/OOD 曲线、组合决策校准、校准误差置信区间 |
| teacher | 公开提到 Astra/Fable 作为 eval 参考 | 训练 teacher 的身份、调用方式、软标签、轨迹与 logits 可得性 |

复现研究应先冻结上述未知边界，再比较我们自己明确写出的监督分布学习、结果校准与 RL 实验。只有同底座、同数据、同算力的消融证明额外 RL 有贡献时，才应把改进归因于 RL；这是一条研究设计建议，不是对 TypeSafe 实现的断言。
