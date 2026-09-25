# OpenJev：小模型、数据与训练设计

> 更新入口：本文件保留早期调研语境。当前实现、已训练实验与最终决策见 [最新实施计划](implementation_plan_zh.md) 和 [真实实验报告](toy_experiment_report_zh.md)。

检索日期：2026-09-17。本文是工程方案和研究判断，不是 JeV 内部结构的披露；本子任务没有调用收费 API，也没有读取 `.env`。

**阅读顺序更新：** 本文保留早期模型候选与实现细节；涉及“默认”“首选”的建议均须服从后续 [核心特征核验](core_features_rlcd_zh.md) 和 [RLCD 专项研究](rlcd_theory_zh.md)。当前没有锁定学生基座，也没有开始训练。非自回归并行、概率质量和未见任务泛化共同决定最终选择。

## 直接结论

可以较快做出开源的「状态 + 自然语言问题 + 动态候选 → 条件概率」模型。首版应复用已有通用分类或重排序权重，完成 Boolean/Choice/Score 三种类型，围绕有限应用域证明泛化与概率质量，再扩展；100 美元的数据/API 预算不能支持“已经复现 JeV 全部能力”的结论。

**早期方案的默认路线是开放权重 teacher + 自有/开放数据，JeV 输出监督另列条件分支。** TypeSafe 的 MCA §2.3(b) 涉及使用服务/输出训练其他模型、模仿或开发竞争产品的限制，§2.3(f) 涉及公开 benchmark；JeV teacher 只保留为获得适用特别授权后的条件分支。[TypeSafe MCA](https://typesafe.ai/legal/mca)

首版可以保留兼容的输入输出理念，模型名称与发布声明应准确描述我们独立训练的能力。公开模型权重许可、云端托管服务条款、输入数据许可、输出数据使用权需要分别记录；Apache/MIT 模型经第三方 API 提供，不自动免除该服务的限制。

## 1. 最值得直接复用的起点

| 起点 | 已核实公开信息 | 在项目中的位置 | 关键限制 |
|---|---|---|---|
| `knowledgator/gliclass-modern-base-v3.0` | 约 151M 参数，Apache-2.0；已训练为动态标签分类器 | **最快英文 MVP 的默认起点**；直接利用其标签编码与评分结构 | 不能把现成分类能力直接等同于任意程序状态判断能力 |
| `knowledgator/gliclass-edge-v3.0` | 32.7M 参数，Apache-2.0 | 低延迟对照或后续软目标训练对象 | 官方零样本分类表显示部分细粒度领域较弱，不作为泛化主模型 |
| `jhu-clsp/mmBERT-small` | 140M 总参、42M 非 embedding 参数、8,192 上下文，MIT，多语言 encoder | **中文/双语和小体积优化路线**；加动态候选头 | 原始权重是 MLM，需补足 instruction-conditioned 分类训练；不能把 42M 当总参数 |
| `answerdotai/ModernBERT-base` | 149M、8,192 上下文，Apache-2.0，主要英语与代码 | 英文结构实验的干净 backbone | 需要从 MLM 补通用分类阶段；中文不是优势 |
| `Qwen/Qwen3-Reranker-0.6B` | 0.6B、32K、多语，Apache-2.0；官方直接读 yes/no logits | **中文/任意指令较重要时的首轮对照**；一遍前向评分，无须生成解释 | 检索相关性与条件事实判断不是同一个目标；每候选评分会重复处理 state |
| `Qwen/Qwen3-0.6B` | 0.6B、32,768、多语，Apache-2.0 | Reranker 在非检索任务迁移不好时，改造 decoder 的备选 | 相比 encoder 内存与前向计算更多；不把它训练成输出概率文本的聊天模型 |

来源：[GLiClass Modern Base](https://huggingface.co/knowledgator/gliclass-modern-base-v3.0)、[GLiClass Edge](https://huggingface.co/knowledgator/gliclass-edge-v3.0)、[mmBERT Small](https://huggingface.co/jhu-clsp/mmBERT-small)、[ModernBERT](https://huggingface.co/answerdotai/ModernBERT-base)、[Qwen3 Reranker](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)、[Qwen3 0.6B](https://huggingface.co/Qwen/Qwen3-0.6B)。

GLiClass 是重要的近邻工作：它把文本和临时标签放入单一模型，一次前向对动态标签评分；代码许可为 Apache-2.0。可借鉴其结构与实现，但“同一题的多个标签”不等于“多道题严格相互独立”。[GLiClass 代码](https://github.com/Knowledgator/GLiClass)、[GLiClass 论文](https://arxiv.org/abs/2508.07662)

**模型选型规则：** 中文回复要求本身不等于训练目标必须双语。若先做英文 SaaS/agent 场景，使用 GLiClass Modern Base，降低冷启动风险；若第一版承诺中文与英文，同一先导集上比较 Qwen3 Reranker 与 mmBERT Small，再按未见任务表现和本机延迟选一个主学生。不要在小预算内同时正式训练整个模型表。

## 2. 开放 teacher 与无 teacher 数据

默认 teacher 可用自托管 `Qwen/Qwen3-8B`，或资源较少时的 `Qwen/Qwen3-4B-Instruct-2507`；两者官方仓库均为 Apache-2.0。选择它们是为了有可下载、可固定版本的权重，并非断言它们与 JeV 同等准确。[Qwen3 8B](https://huggingface.co/Qwen/Qwen3-8B)、[Qwen3 4B Instruct](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)

最经济的标注顺序：

1. 对能执行的规则直接生成真值：JSON 字段条件、退款政策、日期/金额边界、工具是否允许、任务是否完成。确定性执行器比语言模型更可靠。
2. 对情绪、意图、语义相关性等题，使用已授权开放数据的原标签，保存原题意；不把原始 chosen/rejected 或情绪标签硬改成另外一种标注。
3. 对新问题/新 rubric，开放 teacher 判断并保留完整分布或投票统计；抽查错误和冲突。
4. 只在样本有价值且托管服务的相应使用权已确认时，用 API 做多样化改写、困难样本复核。代码及 teacher 版本固定后，API 教师可随时替换。

自托管 Qwen 获得软标签有两种办法，必须区分：

- **标签 logits：** 在完整题目和候选描述后，只允许输出单 token 的候选编号，读取这些编号的 logits，组内 softmax；Boolean 读 yes/no。先检查 tokenization、前导空格和候选顺序偏差，保存 logits。它是“该提示格式下的标签分布”，不是客观正确率。
- **多个判断样本：** 对难题使用候选顺序扰动或独立判定，统计结果；这是 ensemble/vote 分布，不能称为 teacher 原始 logits。生成的 `confidence: 0.97` 文本只是自报分数，不能当作已校准概率。

开放权重自托管的计算成本与 API 预算分开计；若使用本 Mac，需按实际内存及可用后端确定精度和并发。使用量化 teacher 时记录具体量化版本，并检查概率漂移。

## 3. 接口语义与第一版结构

官方资料确认的外部语义是：Choice 为候选分布，Score 为有序等级分布及连续位置，Noul 为 yes 概率；问题 ID 不进入模型，多题共享同一 state 但相互独立。Score 文档还明确，各等级单独对照 state 判断，模型不看等级序号或相邻等级。[TypeSafe Primitives](https://docs.typesafe.ai/primitives)、[Score](https://docs.typesafe.ai/primitives/score)

官方 `confidence` 页面确认它由分布统计得到；另在官方开放 adapter 中找到了具体公式。它们是可复用的后处理，不是需要学习的新 head，更不自动等于“答案正确率”。这些代码属于官方 LLM adapter，不能据此断言 JeV 内部实现相同。[Confidence](https://docs.typesafe.ai/confidence)、[官方 confidence 源码](https://github.com/typesafe-ai/system-one-adapter-python/blob/main/src/system_one_adapter/_utils/confidence_metrics.py)

我们独立实现的统一内部结构：

```text
JSON/state ──稳定序列化──┐
question ─────────────┼── 每个候选独立的条件编码器 ── 每个候选一个 logit
单个候选描述 + 类型 ───┘                         │
                       同一题内 softmax / Boolean sigmoid
                                               │
                              类型化后处理 + 独立校准参数
```

**默认先对 `(state, question, candidate_description)` 独立打分，再在题内归一化，多个候选和多题通过 batch 运行。** 这同时满足多题独立和 Score 单级独立的结构语义；GLiClass 以单候选标签模式作起点，Qwen Reranker 已有适合这种输入的 scorer。模型不依赖固定类别 ID，推理时可换候选名称与数量。

GLiClass 将一题全部候选一起编码的原生方式，保留为更快的对照结构；它减少 state 重复计算，但不自动满足“等级看不到邻级”的条件，应准确报告这个差异。选择逐候选默认结构，是工程取舍而非声称知道 JeV 的底层架构。

- Boolean：一个标量 `a`，`p_true = sigmoid(a)`；也可统一为 no/yes 两候选 softmax。返回概率而不是阈值化后的布尔值。
- Choice：`p = softmax(z_1, ..., z_K)`，只在当前题的候选组内归一化。输出完整分布与 argmax。
- Score：候选是 rubric 等级；模型只看单个描述，后处理按原数组顺序返回 `score = sum(p_k * k)`，从 0 到 K-1，保留 `legend`。这与公开 Score 文档一致。
- `confidence`：复用官方 adapter 的确定性算法。Choice 为 `(max(p)-1/K)/(1-1/K)`；Score 令 `m=argmax(p)`，为 `max(0, 1 - sum_i p_i*abs(i-m) / mean_i abs(i-(K-1)/2))`。K=1 时该函数返回 1；输入先正规化。它衡量分布集中度，不需要训练独立 confidence head。

必须保留完整候选定义：`refund` 只当机器 ID 远远不够，模型还需看到“返还已支付金额”之类语义。对多个 JSON 字段的判断保留路径、数组顺序、数据类型与原值，不把缺失字段静默当 false。

**不应做的结构简化：** 给每个已见任务固定一个分类头；用一个 sigmoid 代替 Choice 的组分布；只训练 Score 的均值；把全部问题拼成可互相注意的单序列；让 decoder 逐 token 生成 `0.873` 再 parse。逐候选 sigmoid 得到的“该描述成立概率”也不能直接当作最终 Choice 分布，必须用题内训练目标拟合候选 logits 后归一化。

多题共享 state 的后续结构可以是：state-only encoder + 每题 cross-attention，或严格分支 attention mask。state token 必须只能看 state，题分支只能看 state 和本题；否则即便直接屏蔽题间注意，信息仍能经 state 在多层中传播。任意 mask 可能影响高效 attention kernel，这一优化要以实际延迟和精度测量决定，首版不承诺 JeV 的多题成本曲线。

## 4. 数据设计：先让它学会“问题改变，答案也必须改变”

数据基本单位是 `(state, question, candidate_set, target_distribution)`，另存可用的独立真值。`state_id`、原数据样本 ID、生成模板族、题目族、语言版本、数据来源与许可证、teacher 版本、标注方法、cost 全部进 manifest。

第一轮可以从 **2,000 个 state / 约 8,000 个问题** 起步，只用于验证学生是否学到条件性；这是工程起始规模，是否扩至约 10,000–20,000 个 state 由学习曲线决定，不是充分性保证。用同一 state 下多题复用标注和文本，但训练和评测拆分都按 state/来源族进行。

应覆盖的任务族：

| 任务族 | 需要学习的变化 | 独立真值或来源 |
|---|---|---|
| 支持工单 | 请求退款、信息查询、催促、投诉；不同政策改变结论 | 自有合成规则、Banking77 |
| Agent 路由 | 调哪个工具、是否还缺参数、结果是否足够 | 可执行模拟状态机；未知工具定义也要出现 |
| 证据一致性 | 指定材料是否支持命题；否定、缺证据、冲突 | 自写规则及 NLI 数据的原始含义 |
| 文本意图与情绪 | 同文不同问题；描述性多标签与互斥 Choice 区别 | MASSIVE、Banking77，选择性引入其他开放集 |
| 有序 rubric | 清晰等级、边界样本、中间等级、尺度改写 | 自有生成器、人工审核；不是把偏好分数当普适真值 |
| 表示与指令鲁棒性 | JSON 路径、字段顺序、额外无关信息、文本里夹带“指令” | 自有对照变换；真值必须可证明保持或按规则改变 |

核心对照必须成组构造：同一 state 换 question；同一 question 改一个决定性字段；同一请求换 policy；Choice 候选改成新描述；选择集缺少合理答案并显式加入 `other`；相似但不等价的否定与条件句。无证据不自动赋值 0.5，只有题意/生成过程明确允许这种解释时才这样标注。

数据来源的默认选择：

| 数据 | 许可与作用 | 发布处理 |
|---|---|---|
| 自写模拟器 + 自写 rubric | 我们控制代码与原创样本；提供确定性标签 | 代码与生成参数开源，样本独立许可 |
| PolyAI/Banking77 | CC BY 4.0；77 个细粒度意图 | 保留作者、来源及改写标记 |
| Amazon MASSIVE | 数据 CC BY 4.0；多语意图和槽位 | 同一源句及翻译必须分到同一 split，避免跨语泄漏 |
| Anthropic HH-RLHF | MIT；人类 helpfulness/harmlessness 偏好对 | 只对原偏好任务使用，不将 rejected 全部当“有害” |
| SNLI | CC BY-SA 4.0；entailment/neutral/contradiction | 初版可不纳入可再分发训练包，单列归因与许可；neutral 不是 false |
| UltraFeedback / synthetic zeroshot 混合集 | 页面分别标 MIT / Apache-2.0，但内含其他来源文本或模型标注 | 不因顶层标签就默认全部底层文本可无条件重新发布；可先不纳入首版 |

来源：[Banking77](https://huggingface.co/datasets/PolyAI/banking77)、[MASSIVE NOTICE](https://github.com/alexa/massive/blob/main/NOTICE.md)、[HH-RLHF](https://github.com/anthropics/hh-rlhf)、[SNLI 官方](https://nlp.stanford.edu/projects/snli/)、[UltraFeedback](https://huggingface.co/datasets/HuggingFaceH4/ultrafeedback_binarized)、[Synthetic Zeroshot](https://huggingface.co/datasets/MoritzLaurer/synthetic_zeroshot_mixtral_v0.1)。

不能只做固定模板随机替换几个实体名，再对随机行切分后报告高分。要把问题族、rubric、候选语义、生成模板以及原始文档的未见泛化单独测出来。

## 5. 监督目标与训练算法

使用真正的概率匹配，不需要教师中间层、同 tokenizer 或自回归文本。记 teacher 分布为 `p_T`，student 为 `p_S`。

**Boolean：**

```text
L_soft = -p_T log(p_S) - (1-p_T) log(1-p_S)
```

用 `binary_cross_entropy_with_logits(student_logit, teacher_probability)`，避免先算 sigmoid 后的数值问题。

**Choice：**

```text
L_soft = KL(p_T || p_S)
       = sum_k p_T[k] * (log(p_T[k]) - log(p_S[k]))
```

训练时去掉与学生无关的 teacher entropy，就是软目标交叉熵 `-sum(p_T * log_softmax(student_logits))`。padding 候选屏蔽后按题归一化，不能让候选较多的题仅因项数多而获得更大权重。

**Score：** 用同一分布损失，再加小权重有序累计分布损失：

```text
L_score = KL(p_T || p_S) + lambda_ord * mean_j (CDF_T[j] - CDF_S[j])^2
```

这保留“错到相邻等级”和“错到另一端”的差异，也保留同均值但不同不确定性的分布。Score 必须按 rubric 语义顺序计算 CDF。

有独立真值时组合 `lambda_soft * L_soft + lambda_gold * L_gold`，冲突样本单独审阅；不要把教师 argmax 伪装成第二份真实标签，也不要按 teacher 高自信无条件加权。对 Choice 加候选顺序扰动，对语义等价题可以做一致性正则；对真实改变题意的变换则必须改变标签。

先使用温度 `T=1` 保留需要复现的概率。若教师过尖锐而训练不稳，再在验证集比较 `T>1`：从概率得到 `softmax(log(clip(p_T))/T)`，学生用同温度并配套 `T²`。温度不能恢复 API 已舍入为 0/1 后丢失的信息。

软标签学习可参照 [Hinton 等的概率目标研究](https://arxiv.org/abs/1503.02531)。本文明确采用 `KL(teacher || student)`；有限候选分类直接优化完整分布，不需要引入自回归文本生成算法。

训练默认：现成分类器做小学习率全参微调，先跑短序列 512/1,024，按长度分桶；是否提高到 2,048/8,192 由实际目标用例决定。候选学习率可从 encoder `2e-5`、新 scorer `1e-4` 起，AdamW、短 warmup、梯度裁剪；这些是试验起点，不是已测最佳参数。完整训练轮数由未见问题族的验证损失决定。0.6B decoder 路线可用 LoRA 降训练内存；不开 RL/PPO/DPO 作为首版核心。

## 6. 评测要分别回答三件事

**是否复制了 teacher 的分布？** 在未用过的 teacher 标注上测 KL、总变差距离、Boolean MAE、Choice agreement、Score 的分布/期望误差。这只证明模仿程度。

**是否判断正确？** 在执行器真值、人工审阅及独立开放测试集上，测 NLL、Brier、macro-F1/accuracy；Score 测等级 MAE、rank correlation 与分布误差。这组才是实际能力证据。学生模型可能接近老师又一起犯错，因此必须与上一组分开。

**概率是否可信？** 用与训练、模型选择都分开的校准集拟合标量 temperature，最终锁定后在测试集看可靠性图、ECE、Brier/NLL，以及“覆盖多少请求时错误率是多少”的 risk-coverage 曲线。分布集中度和 correctness calibration 不能混为一谈；很小的样本只支持很粗的概率判断。[On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html)

四份数据分工：train 训练参数、development 选模型/超参、calibration 拟合概率映射、test 最终报告；先按 state/来源族分组再切分。另设 task-family holdout，不用随机拆行代替零样本泛化。翻译对、同一文档的多题、同一模拟轨迹不得跨边界。

必须测的结构行为：

- 新问题、新领域、新 rubric、新候选词、新候选数量。
- 添加/删除/重排其他问题，当前题答案不变；修改问题 ID 不变。
- Choice 候选重排后概率按语义映射回去基本一致；加入重复/相近选项后不要求概率不变，因为候选空间真的变了。
- JSON 字段重排、无关字段、引用的路径改变、否定、数值边界、state 中夹带假指令。
- 双语承诺若存在，测中文源题、英文源题及未见翻译，分别报告。
- 冷启动/热启动、p50/p95、每 state 含不同题数与候选数、tokenization/网络/模型时间分别计；量化前后复测概率漂移。

基线至少保留未微调 GLiClass、未微调 Qwen Reranker、仅硬标签训练、软标签训练。公开报告当前只比较我们有适用使用权的开放系统；JeV 比较与公开发布需按适用授权处理。

放量依据是：先导学生在独立真值与未见题族上比基线好，软标签有增益，而且校准和延迟可接受。若只在同模板测试上涨，先修数据多样性；若老师本身错得多，修标注器；若任意指令泛化远低于简单分类，再升级学生容量。不要默认“多问 teacher 一百万次”就会解决。

## 7. 100 美元 API/数据预算与计算预算

依主任务最新口径，**100 美元限定 API/数据开销，训练计算另算**。以下是预算封顶建议，不是已产生费用：

| 阶段 | API/数据上限 | 交付 |
|---|---:|---|
| 先导、接口、少量 judge/改写 | $10 | 任务矩阵、成本/质量样本、可比较基线 |
| 覆盖领域与表达差异 | $45 | 第一批开放 teacher 数据；优先用本地开放 teacher 降 API 支出 |
| 困难样本/分歧复核 | $20 | 主动补标；不是仅采不确定样本导致分布偏斜 |
| 独立审核与评测所需数据 | $10 | 锁定校准/测试集，独立真值抽查 |
| 失败重试与余量 | $15 | 账本和硬停止阈值 |
| 合计 | **$100** | 不要求花完 |

样本数必须由先导实测决定：`cost = input_tokens * input_rate + output_tokens * output_rate + other_billable_usage`。共享 state 多题时，应从 API usage 验证是否真的只计一次 state，不能凭 HTTP 一次请求推断。缓存重试、并发在途预留和输出上限都纳入预算；只看本地已完成请求计费会超支。

训练可先估一个 24GB GPU 的短期任务，再按实际吞吐外推；此处不承诺未经运行的训练时长。检索时 Runpod 正式定价页的 Secure Cloud RTX 4090 为 $0.74/小时；例如 10 小时纯 GPU 为 $7.40，另计存储/环境准备，最终以启动时价格为准。[Runpod 定价](https://www.runpod.io/pricing) 本 Mac 运行的小模型基线可以先避免租机，但 FlashAttention 的 CUDA 表现不能套到 Metal/CPU。

条件分支：若使用 JeV 输出训练另获适用特别授权，主任务保存的公开 Gateway 模型元数据为输入 `$0.000000042/token`，即 **$0.042/百万 token**，输出标价 0。数学上 1 亿输入 token 是 $4.20，但这只是公开 token 标价乘法，既不是当前任务的实付记录，也不证明数量/限流/计费语义或使用输出训练的许可。很低的 teacher token 单价说明真正瓶颈更可能是数据设计、覆盖、验证和学生训练，而非买不到足够标签。[Gateway 公开模型目录](https://ai-gateway.vercel.sh/v1/models)

## 8. 最小交付链

```text
固定任务与可发布范围
  → schema + 稳定序列化 + 类型后处理
  → 开放模型基线
  → 确定性模拟器 + 授权开放语料 + 开放 teacher
  → 样本 provenance/成本/许可 manifest
  → 按 state 与任务族拆分
  → 软目标分类训练
  → 独立真值评测与概率校准
  → 本机/云端性能剖析
  → 必要时量化
  → 权重 + 训练脚本 + 数据构建脚本 + 评测报告 + 模型卡
```

首个能用的 demo 应展示：同一工单同时做请求类型、是否缺参数、明确 rubric 下的紧急度；另一页改变政策或单个字段，观察概率和下游路由如何改变。模型服务只是返回判断，demo 的实际动作由普通代码组合。先把这条链做实，再追加更大 teacher、更多任务或共享 state 的结构优化。
