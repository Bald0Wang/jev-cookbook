# OpenJev：与 Fable 的两轮算法讨论及最终复核

更新：2026-09-17。已实际完成两轮 Claude Fable 5.1 xhigh 调用：第一轮独立审查 16 项设计，第二轮接收明确反例、公开仓库审计和本地数学验证，再逐项修订。本文记录经过复核的实施选择，不把模型意见当作证明，也不把我们的算法称为 TypeSafe 已公开的 RLCD。

**当前主线：通用 LLM 的独立候选表征，加 Choice 专用的轻量集合注意力残差；Score 保持等级文字独立，Noul 用单标量。先跑完整的展开布局训练与评测，再验证真实模型的共享树结构。教师拟合、独立真值和 RL 研究分别做受控实验。**

## 1. 讨论是否真实发生、花了多少钱

| 项目 | 第一轮 | 第二轮 | 合计 |
|---|---:|---:|---:|
| 实际主模型 | `claude-fable-5-1` | `claude-fable-5-1` | 两轮均核对 `modelUsage` |
| 指定推理级别 | xhigh | xhigh | — |
| Fable 标价 | $1.10338 | $2.01571 | $3.11909 |
| CLI 辅助 Haiku 标价 | $0.004668 | $0.01459 | $0.019258 |
| 总标价 | **$1.108048** | **$2.030300** | **$3.138348** |
| 耗时 | 327.6 秒 | 519.5 秒 | 约 14.1 分钟 |
| 完成状态 | success，1 轮 | success，1 轮 | 无工具权限拒绝 |

两次均使用显式中文 system prompt，禁用所有工具、Chrome 与 MCP，不读 `.env`，不发送私人频道记录，不执行训练。每次 CLI 预算参数为 $4；表中为最终返回的 `costBasis=list`，不将它未经核账直接计入 Vercel 扣款。原始输入、返回和中文全文留在本地私有审计文件。

## 2. 概率契约先于模型

- **Choice** 输出给定问题与候选集合内的选择分布 `p(y | state, question, C)`。缺信息、无匹配、均不合格需要明确的题意或候选定义；分布平坦不等于已识别出“没有正确选项”。多标签真值任务应改为多个 Noul。
- **Score** 输出文字等级的分布，程序计算 `Σ i·p_i`。叶输入只有当前等级描述，不加入等级索引、等级总数或其他等级文字。描述本身有意义的数字照常保留。
- **Noul** 输出命题为真的概率。一条叶同时包含题目及可选的 true/false 判据，用一个 logit 的 sigmoid；不对单个候选执行恒为 1 的 softmax。信息不足不自动标成 0.5。

三种任务共享表征和评分参数，但不能偷换成同一种真值语义。题间结构隔离也不意味着事件在统计上独立，不能因此把多个 Noul 概率直接相乘。

## 3. 学生结构：第二轮为何改变第一轮选择

第一轮 Fable 支持均值 DeepSets 集合头。主研究者要求比较集合计数、候选相对关系与初始化后，第二轮改投 **Set-Attention 残差**。我们采纳这个工程起点，但不采纳“某个有限宽度注意力头严格包含所有 DeepSets”或“DeepSets 不可能表达成对关系”的过强解释。

设叶表征为 `h_i = LLM(state, question, candidate_i)`，隐维 `d` 从实际 checkpoint config 读取：

```text
base_i = w0ᵀ LayerNorm(h_i)

Choice:
  Q,K,V = shared_projections(LayerNorm(h))       # 宽128，4个head
  a = attention(Q,K,V)                        # 同题候选内，无位置编码
  y_i = output_projection(a_i) + projection(h_i)
  g_i = FFN(concat(y_i, log(candidate_count))) # 逐候选非线性
  z_i = base_i + W_out g_i
  p = softmax(z，限本题候选)

Score: z_i = base_i；按本题归一化
Noul : p_true = sigmoid(base + b_noul)
```

选择一层、宽 128 的集合头，是为了以有限开销允许同题候选相互比较，打破独立评分器的 `p_i/p_j` 不随第三项改变的限制。它不能恢复已经被单向量表征丢掉的全部文字细节；若重要任务需要精细的跨候选文字比较，应比较保留多 token 表征的交互方式或候选集合条件化输入，不能只盲目加宽 head。

均值聚合和标准 softmax attention 都可能分不清整个集合被复制后的计数；所以计数作为显式特征进入逐候选的非线性层。给所有 logits 加相同的 `logK` 偏置会被 softmax 抵消，没有这个作用。

**零初始化要按计算图判断。** 当前使用 `w0` 小而非零随机初始化，集合分支只有最后的 `W_out=0`，其他层正常初始化。第一步 base head 和 `W_out` 一般可收到非零梯度，集合内部参数第一步梯度为零、随后打开。即使当前并联结构同时令 `w0=W_out=0`，两个末端投影各自对非零特征的梯度一般仍非零，并不会因此永久死锁；非零 `w0` 的作用，是骨干被允许训练时第一步也能收到 base 路径的梯度。第一轮真正有风险的是串联结构 `z=wᵀ MLP(h)` 同时把 `w` 与 MLP 末层置零，且没有其他有效梯度路径。Choice/Score 的公共标量偏置会在 softmax 中消掉；Noul 需要自己的可训练偏置。

代数上的置换等变来自：候选编码无兄弟位置、集合头无位置编码、所有候选使用相同变换。实际浮点结果只要求与所用 dtype 相称的误差；不能承诺任意 GPU kernel 的逐 bit 相同。首个 toy 里集合交互题不足时，集合头的实际收益仍需消融，不能预先宣传。

## 4. 共享计算：先证明，再决定是否值得用

正确性参照始终保留展开布局：

```text
input_ids, attention_mask : [N_leaf, T]
readout_index             : [N_leaf]
H                         : [N_leaf, d]
leaf_to_question          : [N_leaf]
question_type             : [N_question]
```

一次张量 forward 可以处理不同 state、同 state 多题与多候选；全部候选一起组成题级 softmax。内存不够时按完整问题拆微批，不在拆开的候选子集里分别归一化。

共享树的结构是 `state → question → candidate/readout`：state 只看自身因果前缀；question 只看 state 和自身；候选只看其祖先及本候选前缀。不同树互不可见。位置使用该 token 在独立路径里的深度，不能使用 packed 数组的全局索引；哨兵父节点不得作为 `-1` 下标读到最后一段。

同 token IDs、同 path positions、同注意力可见集合、同参数且 dropout=0 时，可以逐层归纳得到相同叶表征；共享节点的反向梯度为各路径梯度之和。因此共享图与展开图的参数梯度也一致，除浮点求和顺序差异。训练不能 detach 共享前缀。动态 RoPE 缩放、sliding window、GQA、padding、额外辅助损失和缓存实现都必须重新核对。

主工程已经运行的纯 Python toy 给出：两层 attention/RMSNorm/RoPE 下 logits 误差 0；12 个参数的有限差分目标导数误差 0；错误 global causal mask 产生约 0.304 误差，错误 packed-global position 产生约 0.215 误差。见 [结构验证脚本](../scripts/check_tree_attention.py)。这不是 Qwen、autograd 或 GPU 的验证。

真实模型的次序定为：**展开布局端到端 → 固定权重的 tree/flat 前向及全层梯度对照 → 真实 kernel 的吞吐和显存 profile → 决定是否采用共享训练。** Dense tree mask 的平方内存、稀疏 kernel 回退、小 state、小候选数和 padding 都可能抵消收益。HTTP 请求只是一层接口，不能拿一个 HTTP 请求冒充一次 forward 或真实 GPU batch。

测试必须分层：集合头之前 `h_i/base_i` 不受兄弟候选内容影响；Choice 最终 logits 可以受同题候选影响；其他题和其他 state 在整条路径上都不能泄漏。近零梯度用绝对误差，非零梯度再用相对误差，不能用一个相对阈值判断所有张量。

## 5. 现有开源实现：复用参照，补齐缺口

| 仓库与固定版本 | 可直接借鉴的东西 | 不能据此宣称完成的东西 |
|---|---|---|
| [TheoLeeCJ/openjev，b4782a6](https://github.com/TheoLeeCJ/openjev/tree/b4782a6c953f05c6255706d7a219f4e032af5b58) | frozen direct-option baseline；state prefill 后复制原生 KV 到题批次；完整 prompt 与 prefix token、padding、position 的验证 | 可训练零拷贝树、跨 state 调度、校准训练、任意数量候选 |
| [vinnylarouge/jevlike，94f5fd1](https://github.com/vinnylarouge/jevlike/tree/94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452) | context 编码一次，候选 query cross-attend context 的共享结构思路；现成训练/数据流程可作对照 | 完整 question schema、Noul/Score、多题隔离、软目标训练和独立校准 |

第一个仓库的 Direct 基线使用全词表投影后选 A–P，当前范围 2–16 项；它是真实可用的零训练对照，不是接口壳。第二个仓库默认 byteencoder 的 exact-badge matching 与 Wikispeedia human next-click 是不同任务，不能当通用概率决策能力证明。实际复制代码前核对并保留相应许可；schema、typed head、概率目标与评测契约需要我们明确实现。

**第二轮发出之后的主工程复核，未伪称已被 Fable 讨论：** Theo 的 Qwen3.5-4B 包含 linear/full attention 混合层。因果 attention mask 本身约束不了 recurrent state，因此不能直接移植本文对 dense Qwen3 的树证明。其公开预测重新计算得到 serial 5/777、parallel 6/777 argmax 漂移，最大概率差约 0.09339/0.06242；不能像 Fable 第二轮所建议的那样，仅凭“BF16”把它当作可接受容差。其 authored 样本也不能升级为独立人工裁决的 gold。

## 6. 舍入概率：数据合法性与信息不足必须区分

两位小数全零不必是错误：255 个约 0.0039 的概率都可以显示成 0。不能把它改成 uniform 真值，也不能直接删掉所有和不恰为 1 的记录，使高 K、较平坦的目标系统性消失。

若明确采用 nearest-to-0.01 的工作假设，可定义：

```text
l_i = max(0, r_i - 0.005)
u_i = min(1, r_i + 0.005)
P(r) = { t : sum(t)=1, l <= t <= u }
可行性：sum(l) <= 1 <= sum(u)
```

元数据目前只有 decimals，没有确定 mode，所以这是需要标注的训练假设，不是已经核实的供应商行为。仅比较 nearest/truncate 哪个可行，无法证明实际采用哪种模式。尤其不能“nearest 不可行却仍用 nearest 训练”。应保留原记录、标出待核实的约定或不适用的 teacher loss，gold 仍可用。仅凭题目的真实发生率接近某个小数边界，也无法知道模型内部未舍入输出，不能据此识别舍入方式。

**两个明确分开的阶段：**

1. 首个受限 smoke pilot 可声明使用和为 1 的 rounded-proxy，teacher CE 与独立 gold CE 分开运行。主工程目前选择这条最简路径。所有记录仍保留，按题型、K、原始总和、零项数量及可用的集中度代理报告 teacher loss 的覆盖；这不是长期数据筛选政策。若两条训练分支的有效题集不同，要补同题集对照或明确披露。
2. 随后的舍入感知实验采用区间目标，并与 proxy 在可比较题集上对照：

```text
L_interval(p) = min_{t in P(r)} KL(t || p)
t*_i = clip(c*p_i, l_i, u_i)，选 c 使 sum(t*)=1
对 student logits 的梯度 = p - t*
```

KKT 与 envelope/Danskin 推导支持此式。实现优先在 log probability 空间求缩放，避免给 student 概率任意加 floor 后仍声称优化原目标。`stopgrad(t*)` 的 soft CE 提供相同梯度，但**前向 CE 数值不是 interval-KL**；报告、早停需计算含 `Σt*logt*` 的完整 KL。

本执行代理另做了无模型的纯 Python 数值检验：四维例子中该梯度与有限差分最大误差约 `4.06e-12`；`r=(0.50,0.49,0)` 的直接归一化首项为 `0.5050505`，确实越过 `0.505` 上界；K=255 全零对过度集中的 student 有正损失，对均匀及非均匀但均在合法集合内的 student 都为零。它只学习可识别的信息，没有替教师补造精确分布。

区间内多个分布无法区分是信息边界，不能因为 proxy KL 不再下降就加入偏爱低熵的项、声称恢复了教师真值。是否需要额外先验、独立 gold 或更高精度数据，应作为另一个有明确目标的实验。

## 7. 损失、平均方式与初始化比较

首个 transformer pilot 用相同新 head、相同数据、顺序 seed 和更新预算，顺序比较同尺寸 Base 与通用后训练 checkpoint。原生 reranker 和 frozen letter-logit 只是对照，不因接入方便成为默认学生。相同样本/步数与相同 wall time 是不同比较口径；都记录，不混称公平算力比较。结果值得继续时才复跑种子、增加容量或消融，避免一次展开全部家族×尺寸×学习率。

首轮分开两种训练：

```text
teacher 分支：mean_q teacher_CE_or_interval_gradient(q)
gold 分支   ：mean_q independent_gold_CE_or_BCE(q)
```

每个分母只数该项真正可用的题，完整问题是单位，不是候选、token 或微批。Noul 的 BCE 与二类 CE 一致，与 KL 差目标熵项。Choice/Score 与 Noul 默认共用题级平均；若分别平均后相加，就隐式改变了类型权重，必须显式声明。

后续才评估 soft-target training、gold CE 与有序 CDF 的组合。Score 当前索引就是 `0…K−1`，不要凭空增加所谓官方任意 `level_values`。CDF 求和或除以 `K−1` 都保留有序信息，区别是题间尺度和权重，不是其中一种“抹掉了语义”。

另一个要避免的错误：若 `t*` 是随 student 变化的 KL 投影，再额外加 `CDF(stopgrad(t*),p)`，这不自动成为某个联合区间目标的精确梯度。首版不需要这项组合；可先在固定 gold/固定 soft target 上消融 CDF，或之后明确求解联合目标。

梯度累积应累加题损失之和，再使用整个 optimizer update 的总有效题数。未来 DDP 默认对 rank 梯度取平均时，本地按全局分母算损失后乘 `world_size`；不能把微批均值再平均，也不能叠加框架自动除以累积步数而不补偿。

## 8. 单卡可执行起点与 OOM 后备

主工程已确认可用 8×A100-SXM4-80GB；第一轮使用一张，不因空闲 GPU 多就提前加入分布式复杂性。以下是第二轮讨论的工程起点，**实际执行参数以 run manifest 为准，不是已经达到效果的配置**：

| 参数 | 初值/选择 |
|---|---|
| 初始化比较 | Qwen3-0.6B-Base 与同尺寸通用后训练版本，共用 typed head |
| 训练布局 | flat、完整问题、全部候选一起归一化 |
| 新头阶段 | 冻结骨干，head LR 1e-3；约 100 update 的预算上限，检查 dev 曲线 |
| 全参阶段 | 骨干 LR 1e-5、head LR 1e-4；AdamW，clip 1.0；norm/bias 不加 weight decay |
| 批次 | 每 optimizer update 约 16 题；微批另设约 24k padded-token 上限，按实际显存调整 |
| 精度 | bf16 autocast、FP32 softmax/loss；显式检查参数、梯度和 optimizer state 的真实 dtype |
| 训练长度 | smoke 后至多约 400 update 的观察预算，每约 25 update 看 dev；保留 best-dev，不宣称这些步数是质量下限 |
| 选择标准 | dev 与独立真值表现、未见 family 行为、实际成本共同判断，不仅看训练 loss |

0.6B 全参采用约 16 byte/parameter 的常见 mixed-precision Adam 记账时，参数与优化器量级约 9.6 GB，但具体实现可能不同，激活、mask、临时缓存和 kernel workspace 另算。不能把 autocast 自动等同于存在 FP32 master weights。先用实际一批 profile，再调整长度、完整题批次和 activation checkpointing。

只有真实 OOM 才启用两遍 gradient cache：第一遍 `no_grad` 分 chunk 得到全部叶 `H`，将其作为叶张量跑完整 head/loss，取得 head 梯度与 `dL/dH`；第二遍在相同参数、token、dtype/kernel、dropout=0 下重新计算各 chunk，以 `sum(H_chunk * stopgrad(dH_chunk))` 反传骨干。两遍间不更新参数，第二遍不再次除分母。它是两遍重算，必须与小批直接反传比较梯度，不能用“BF16”跳过明显不一致。

## 9. 必须交付的验证，不用一个 toy 代替全部结论

**概率机制 toy** 使用已知 Bernoulli/categorical 条件分布，先验证解析期望与完整采样梯度，再比较直接 CE/Brier、无偏 pair-sampling reward 及组内标准化的反例。采样 `A,B` 必须条件独立，梯度包含两条 log-prob 路径，baseline 不能依赖正在求 score-function 的随机动作。若做组标准化，应明确有多少独立 reward 样本；一组只有一个 joint reward 时标准差没有这个意义。

`E|p−q|` 和 `KL(q||p)` 是条件概率估计误差，不是“精确校准误差”；一个恒报基率的模型可能整体校准却没有分辨力。校准、分辨力和 proper score 分别报告。该研究分支不需要生成 CoT，也不宣称就是 TypeSafe 的 RLCD。

**自然语言端到端 toy** 使用自有可执行规则与状态，保存 teacher 完整输入、原始响应、版本、精度和 gold 来源。主工程的首批小数据为 144 state / 432 question；这个数量用于跑通和找错误，不足以保证广泛任务泛化。分区必须继承 state、源样本、模板/生成族的关联，另留未见 generator family；不能只随机拆行。同题改变候选集合、规则或可见事实后重新标注，纯置换才同步置换目标。

报告分开五组内容：

1. Jev fidelity：点分布或区间目标下的 KL/TV、argmax/期望误差，注明目标精度及覆盖。
2. 独立 gold：NLL、Brier、accuracy、ECE/可靠性图及 risk-coverage；confidence=1 不能漏出分箱。
3. 泛化：已见与未见 state/template/generator family 分开，错误样例追溯来源。
4. 效率：同硬件、同题型/K/长度的 tokenization、模型前向、端到端时延、吞吐与峰值显存；明确是否包含完整词表投影、几次 forward。
5. 执行状态：哪些已跑、未跑或失败，实际配置与费用，不以计划充当结果。

同 state 多题相关，置信区间至少按 state/源 family 聚类重采样，不能把所有问题当独立样本。family 太少时，区间不能代表跨任意领域的不确定性。预先留出的 calibration 集可用于另行拟合温度，但与未调整输出分开报告，最终 test 不参与选择。

## 10. 实现边界与交付接口

文件名可以按现有工程调整，职责必须明确：

```text
schema / generators     → 原始来源、state、question、candidate、gold、split
teacher adapter         → 原始响应、解析分布、精度、版本、usage/cost
target validation       → 合法性/舍入假设/可用信号mask/覆盖表
batch builder           → 完整问题的叶展开、readout索引、题映射
backbone + typed heads  → Choice分布 / Score分布 / Noul真值概率
loss + train loop       → 按有效题计数、保存真实配置及best checkpoint
evaluation + profile   → fidelity / gold / family / latency / memory
tree correctness       → 独立于训练目标的mask、位置与梯度检验
```

必要测试覆盖：题/状态隔离、集合前后正确层级的候选影响、置换等变、padding/readout、舍入可行性与投影梯度、全零 K=255、拆微批等价、checkpoint 独立副本、ECE 两端点；共享树与 gradient cache 只有启用时才增加相应的真实模型梯度对照。无需为每段胶水代码镜像写测试。

当前仍需实验决定的是 Base/Instruct 的优劣、集合头在目标任务上的收益、舍入约定、真实 tree kernel 的收益，以及更大容量是否解决已定位的能力瓶颈。没有公开证据能决定 Jev 的专有 reward、底座和训练配方；我们能交付的是有证据、能复跑的同类系统，而不是给猜测套上“官方复现”的名称。
