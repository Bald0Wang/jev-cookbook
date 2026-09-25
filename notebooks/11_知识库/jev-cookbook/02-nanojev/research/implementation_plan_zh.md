> 实施更新：已完成 V2 的 6,936 题与六次训练，以及 V3 的 9,000 道新增导航题、五组训练、完整游戏对照和旧任务回归。当前配方与命令见 [执行手册](pipeline_runbook_zh.md)，实际成绩见 [V3 报告](navigation_v3_report_zh.md)、[V2 报告](pipeline_v2_report_zh.md) 和 [回归报告](navigation_v3_regression_zh.md)。本文件保留逐项算法依据；下文首轮 toy 参数与尚未实现的后续阶段不冒充最终实验配置。

# OpenJev：可执行的模型、训练与基准方案

2026-09-17。本文取代此前方案中的默认 reranker 路线。用户目标是先实现最有辨识度的核心能力；最新授权按当前可用 API 额度 **$25** 执行（取代最初 $100 的本轮预算口径），训练另算，已授权 `capyubara-0` 的 8×A100 80GB。本文区分已核实的产品契约、我们选择的实现，以及尚未完成的能力验证。实际小试结果另见 `toy_experiment_report_zh.md`；不要用计划中的实验冒充已完成实验。

**结论：直接从 dense 通用 LLM 初始化，把它改造成一次前向输出多道题完整分布的决策器。先用有真值的 toy 与 Jev 分布把全链路跑通，再扩大任务分布；RLCD 作为需要验证的校准训练机制，而不是首版能否实现并行分布输出的前提。**

## 1. 先锁定我们到底复现什么

| 核心契约 | 已知证据 | 我们的实现与验收 |
|---|---|---|
| 给定 state，回答由调用方定义的问题 | 官方 state 与原语文档 | 输入显式包含 state、question、候选语义；问题不是一个固定类别 ID |
| Choice 对动态候选集合给完整分布 | 官方 Choice；本机真实 API | 任意本次 K 对应 K 个 logits，在本题内 softmax；参数规模不依赖 K |
| Noul/Boolean 是命题概率 | 官方 Noul | 单语义路径、单 logit，返回 sigmoid；不同题之间不归一化 |
| Score 给各等级的分布及期望 | 官方 Score：各等级独立按文字评估，序号不输入模型 | 等级分别评分，再组成类别分布；序号只在输出计算期望时使用 |
| 同 state 多题独立评估 | 官方 API；实测多题请求 | 不让不同 question 相互注意；共用 state 不等于假设答案事件独立 |
| 无 CoT、低延迟、适合大批量决策 | 官方 System 1；创始人 X 说明 | 不调用 generate、不输出推理文字、不逐题解码；候选路径组成张量 batch |
| 多个不同 state 在同 batch 并行 | 本项目明确需求；不能仅凭单 state API 宣称内部实现已知 | `[多个state × 各自questions × candidates]` 一起前向，按 question 分组读出；实测跨 state 隔离 |
| 概率有意义，而不只是选得对 | 官方校准定位；RLCD 公开名称 | 同时报独立真值上的 proper scores 与教师分布一致性 |

来源：[官网](https://typesafe.ai/)、[State](https://docs.typesafe.ai/concepts/state)、[Choice](https://docs.typesafe.ai/primitives/choice)、[Score](https://docs.typesafe.ai/primitives/score)、[Noul](https://docs.typesafe.ai/primitives/noul)、[创始人关于 CoT 的原帖](https://x.com/CompleteSkeptic/status/2099981459541143995)。完整来源核查与 Discord/X 证据边界见 [核心特征](core_features_rlcd_zh.md) 和 [公开讨论记录](rlcd_public_discussion_zh.md)。

RLCD 的公开展开是 **Reinforcement Learning for Calibrated Decisions**。尚未取得 Jev 的真实 reward、优化器、训练集、模型参数量或注意力实现。下面不是对这些内部细节的断言。“因果 Transformer”也不意味着我们的服务必须逐 token 生成：对已经给定的输入序列，一次 forward 就能读取所有需要的表示。

> **训练后的新增证据：** 大 K/歧义探针与直接硬币对照发现，在相同50%随机事件下，Jev Choice给heads约0.89–0.95，而Noul约0.48–0.49；70%事件时分别约0.99–1和0.69。见 [原语概率语义诊断](probability_semantics_zh.md)。因此后续数据必须分开teacher行为模仿和独立概率真值，新增已知条件分布及跨原语一致性测试。这些追加题未用于重训或选择本次checkpoint。

## 2. 每项主要决定，以及什么证据会让我们改

| 决定 | 为什么先这样做 | 对照与改动条件 |
|---|---|---|
| Qwen3-0.6B-Base 与 Qwen3-0.6B 作为同家族小试 | 直接检验 Base / 通用后训练初始化；dense attention 便于严格验证共享树；0.6B 便于迅速闭环 | 同输入、同头、同训练预算比较；0.6B 容量不足才扩大 1.7B/4B。不是已认定 Base 胜出 |
| 不默认 reranker | 检索相关性训练不自动覆盖任意规则决策，也没有当前证据表明它更适合 | 相同 backbone/head 的 reranker 初始化消融；若同预算在新规则与校准上稳定占优，采用它 |
| 用共享标量头读取候选表示 | 动态 K 不需要新增固定 K 类参数；候选语义而非类别编号决定得分 | 原生选项 token logits 是强冻结基线，不能只和随机头比较 |
| Choice 加小型无位置集合注意力残差 | 候选的意义可能取决于集合，独立打分有固定 log-odds/IIA 限制；集合头保持置换等变 | 同 checkpoint 做 `set-head=none` 消融；若无收益且延迟更高，去掉；若不足，扩展集合交互而非固定分类头 |
| Score 绕过集合交互 | 对齐官方“等级文字独立评分”契约，避免等级序号捷径 | 改成其他产品语义时才放宽；不能为提高 toy 分数默默改契约 |
| flat 完整路径先训练，tree 后优化 | flat 是容易审计的数值参照；错误共享会改变模型而非只改变速度 | tree 的输出/梯度/隔离测试通过且实测省资源，才替换默认后端 |
| 首轮 teacher CE 与 gold CE 分开 | 模仿教师分布与预测程序真值是不同目标，固定混合会模糊两者 | 有明确部署目标、冲突审计与消融证据才混合，权重不能凭习惯取 0.5 |
| 校准温度在独立 calibration 集拟合 | 防止在 test 上调概率；小样本先用一个共享参数 | 校准集足够且类型差异稳定时才用 per-type/vector calibration |
| 首轮不追加正确性奖励 RL | 单纯奖励正确会鼓励过度集中，不能保证校准；完整分布监督已经可微 | 对比精确 proper loss 与同目标的 RL 估计，只有实际改善才保留 RL |
| 小试单卡全参，多个实验占不同卡 | 0.6B 在 80GB 上不必引入分布式复杂度；并行跑对照比拆一小模型更实用 | 大模型/长 state/高 K 需要时再启用 DDP、FSDP 或 LoRA，按显存与吞吐实测决定 |

[Qwen Base 模型卡](https://huggingface.co/Qwen/Qwen3-0.6B-Base)、[通用后训练模型卡](https://huggingface.co/Qwen/Qwen3-0.6B)。两轮真实 Fable 5.1 xhigh 讨论及逐条纠错见 [裁决纪要](algorithm_fable_decisions_zh.md)。Fable 的建议经过复核；没有把模型意见当成证据。

## 3. 精确的模型计算图

一条问题记作 `x=(s,q,C)`。先固定 tokenizer 与分段序列化，不把 teacher、gold、split、candidate 数字序号或来源元数据泄漏进输入。

```text
state 段:      State: <state>
question 段:   Question type: <type>  Question: <instructions>
candidate 段:  Candidate: <候选语义>  Decision: <已有 EOS 读出 token>
```

分段先 tokenize，再拼接 token ID。这避免 tree 与 flat 因字符串边界 BPE 不同而输入不等价。EOS 在这里是已有词表中的读出位置，不是实际生成的输出。也可学习专用 token，但首版不同时增加这一变量。

对 Choice 的候选 `c_i`：

```text
h_i = LLMθ(tokens(s) + tokens(q) + tokens(c_i) + readout)[readout]
b_i = wᵀ LayerNorm(h_i) + b
u_i = Linear([LayerNorm(h_i), log K])               # width 128
m_1:K = SelfAttention(u_1:K)                       # 4 heads, no positions
z_i = b_i + w_outᵀ tanh(u_i + m_i) + b_out
p_i = softmax(z_1:K)_i
```

同一个 `w` 对所有候选共享，`w_out` 的尺寸也不随 K 改变。集合头不加候选位置编码，padding 候选不得成为 attention key；将候选重排会同步重排输出。`log K` 进入非线性分支，不能只给所有 logits 加同一个偏置，因为共同偏置会被 softmax 消掉。`w` 小随机非零、集合残差仅末输出层置零，使初始读出接近独立评分且解冻后 backbone 能收到梯度。即使末层全零，它自身通常仍可先学起来；不能把第一步上游梯度为零误称永久死锁。

这不是“把每个候选独立做 yes/no 分类”。模型直接对整道题的分布训练，梯度含所有竞争候选；有集合交互时，某候选的 logit 也会随其他候选语义改变。K=20 时得到 20 个表示与 20 个标量，按同一规则输出 20 维分布。 已用训练后的 Instruct checkpoint 实测 K=2/5/20/64/255 在同一次 backbone forward 输出对应维度的分布，详见 [动态候选检查](dynamic_candidates_check.json)；这只证明结构可变，不证明未训练过的大 K 上质量。

对 Score：`z_i=wᵀLN(h_i)+b`，不加集合残差；每条路径只含当前等级描述。输出 `p=softmax(z)`、`expected_score=Σ_i i*p_i`。物理存储重排时 ordinal 映射随之保留。只回归均值的 MSE 无法辨别同均值、不同不确定性的分布，因此不作为主损失。

对 Boolean：只编码命题路径，可选的 false/true 判据以固定顺序加入 question 段，得 `z=wᵀLN(h)+b`，`p_true=sigmoid(z)`；统一评测时视为 logits `[0,z]`。没有让 false/true 两条几乎重复路径占两次 backbone 计算。

实际脚本 [train_toy_decisions.py](../scripts/train_toy_decisions.py) 一次 backbone forward 处理批内所有叶路径；head 随后按 question 聚合。训练中对同题 K 个候选一起算 loss。独立 GPU 流、HTTP 并发和“无自回归计算图”是三件不同的事，不能互相冒充。

## 4. 并行、共享前缀与真实成本

首版 flat batch 展开完整路径，优点是标准 SDPA 可用、多个不同 state 能直接并行；缺点是 state/question 前缀重复算。它已经满足无逐题生成，但不是 Jev 级吞吐已经复现的证据。

优化版建立森林：每个 state 是独立根，下面分 question，再分 candidate。一个 token 只能注意到：本节点中不晚于它的 token、以及路径上的祖先；不能看到兄弟候选、别的问题或别的 state。RoPE `position_ids` 必须按根到当前节点的路径长度计算；不能直接使用整棵树展开后的全局位置。

```text
state A ─┬─ question A1 ─┬─ candidate 1 → h_A11
         │               └─ candidate 2 → h_A12
         └─ question A2 ─── proposition → h_A2
state B ─── question B1 ─┬─ candidate 1 → h_B11
                         └─ candidate 2 → h_B12
```

每个最终候选 loss 的梯度都应沿共享前缀相加，不能为了省显存把 state prefix detach。先用 additive 4D mask 验证正确性；如果把整棵树塞进 dense `N×N` attention，反而可能更慢。效率阶段用块稀疏 kernel/FlexAttention，或者推理时使用经过隔离检验的共享 KV；真实显存与时间报告决定是否上线。

假设一个 state 有 J 道题，题 j 的候选数 K_j，state 长 S，题长 Q_j，候选长 C_ji：flat 的 token 数约为 `Σ_ji(S+Q_j+C_ji)`；树的唯一 token 数约 `S+Σ_j Q_j+Σ_ji C_ji`。这是 token/projection/MLP 复用空间，不是 attention 总耗时按这个比例下降的承诺。

已有检查分两层：[纯 Python 树检查](tree_attention_check.json) 只证明小数学模型；[真实 Qwen 检查](qwen_tree_check.json) 使用 tiny 随机 Qwen 权重，检验真正的 forward 与 autograd。后者也不替代完整 pretrained 权重或生产 kernel 性能验证。mask、position、异题隔离、跨 state 隔离、重排与梯度缺一不可。

大 K/长 state 时仍以完整问题为 loss 单位。超显存可使用两遍梯度缓存：先无梯度分块得所有 `h_i`，在完整集合上求 head loss 与 `∂L/∂h_i`，再固定参数、关闭 dropout，逐块重算 backbone 并回传这些梯度，最后只执行一次 optimizer step。不能把一题拆成若干小 softmax。DDP 的有效题分母也要按全局题数处理；详见 [训练执行契约](algorithm_training_contract_zh.md)。

## 5. 查询分布从哪里来，以及如何防止自证

教师只提供 `p_teacher(y|s,q,C)`，不会自动提供我们的输入分布 `D(s,q,C)`。本项目第一版明确覆盖“短状态上的规则判断、路由、证据与等级评估”，先不承诺任意领域通用决策。

当前可执行 toy 使用自写程序事实：支持团队主诉、退款申请/批准/到账的区分、功能影响等级；OOD 使用新的权限与证据规则。每条 state 同时问 Choice、Boolean、Score。gold 来自生成时的事实与规则，Jev 对相同输入额外提供分布。数据先按事实组合和表述模板分区，再送教师，所有衍生改写继承源分区。

当前固定规模：64 train、16 dev、16 calibration、32 test、16 OOD states，每个 state 3 题，共 432 题。候选 K=2…5，中英文各半。这是通路试验，不能凭 32 个 test state 证明现实校准；同规则和模板仍会导致相关性。

扩大时使用以下输入源，而非只把当前模板改写几万次：

1. 任务目录：Tasksource、PromptSource、Natural Instructions 中有明确有限候选语义的任务。抽取任务定义、原材料与 answer choices，逐源保留许可和归因。
2. 开放真实语言材料：Banking77、适用 NLI/多选数据等。原标签只对原题有效；改规则后不能沿用旧 gold。
3. 程序规则族：退款政策、权限、证据完整性、工具状态机。程序先生成语义事实和真值，LLM 可负责自然语言表达；表达后再核对事实没有变。
4. 语义 rubric 与工作流快照：自有材料、真实可执行状态、明确等级定义。教师软标签可用于训练，但独立审核/程序结果用于评估，不能让生成器、标注器和判卷器互相循环背书。

概率数据另增加 `programmatic_conditional_distribution`：由生成器的随机机制与可见信息解析出完整 q；它不同于一次 observed outcome 的 one-hot，也不同于模型自报概率。对应 soft CE 可直接接入相同分布损失，适配器需保留分布型 gold，不能强制压成单个 gold_index。

每条查询 manifest 至少记录 `source_group/task_family/rule_version/state_id/question_version/candidate_mapping/language/length/K/split/gold_kind/teacher_kind`。按任务族取样后再生成它的合法 state、q 和 C；不能把无关问题随机拼上文本。

主动采样从新规则、新候选语义、学生/教师分歧、稀缺长度/K 分层选训练查询；另保留随机采样池用于估计目标工作负载表现。不能用主动挑出的困难集拟合生产校准，却不说明分布发生变化。候选增删或题意改变要重标；只有纯物理顺序置换才可同步置换原目标。

完整来源和转换例子见 [查询分布设计](query_distribution_zh.md)。正式扩展先做学习曲线：增加规则族数量与增加同规则实例数量分别测试，确定缺的是语义覆盖还是数据量。

## 6. 教师数据与舍入：不能把输出当 logits

保留每次请求的完整原输入、候选 ID、native probabilities、rounding、费用和模型标识。Jev 当前返回两位小数概率；这是 rounded probabilities，不是 raw logits。普通 LLM 的 JSON 标签仅是 hard pseudo-label，自报百分比不升级为原生概率。

当前 toy 审计：432 个向量全部非零且和为 1，每个 type/K/split 保留率 100%，teacher argmax 全部符合程序 gold。主教师监督分支原样使用这些数值，明确叫 **identity rounded proxy**。不温度软化零值、不补 epsilon、不无条件重新归一化。若后续原始和不为 1，先隔离该 teacher target，保留原题及可用 gold，并报告各分层丢失情况。

舍入并非小问题：K=255、真实均匀时，两位小数可能全为 0；这个观测不代表无效，也不能直接补成“教师均匀分布”。若 nearest-rounding 模式得到确认，可定义 `Q={q∈simplex: max(0,r−δ)≤q≤min(1,r+δ)}`，`δ=.5×10^-d`，再试验：

```text
L_interval = min_{q∈Q} KL(q || p_student)
q*_i = clip(c*p_i, lower_i, upper_i),   Σq*=1
gradient wrt student logits = p - stopgrad(q*)
```

使用 log-space 二分解 c，报告真正的 interval-KL 数值。若用 `CE(stopgrad(q*),p)` 做反传，它给相同梯度，但前向数值不是 interval-KL；不能拿它做区间误差报告。rounding mode 未公开时，这只能是带假设的实验，不是假装恢复了教师真实分布。高 K 监督精度不足时，优先寻找高精度 teacher 或独立标签，而非悄悄删除所有高熵任务。

## 7. 训练的确切算法

对一题完整候选 logits `z`，`p=softmax(z)`：

```text
teacher 分支: L = -Σ_i p_teacher_i log p_i
gold 分支:    L = -log p_gold
forward KL:   KL(p_teacher || p) = L_teacher - H(p_teacher)
梯度:         ∂L/∂z = p - target
```

teacher CE 与 forward KL 对固定 target 梯度完全相同；采用稳定 log-softmax，在乘目标前排除无效项或将其 log-prob 置零，避免 `0×(-inf)`。Boolean 的 `[0,z]` 两类 CE 等价于 BCE。每道题等权，不让高 K 题或某个类型因为实现中的分组均值获得额外权重。

当前三条主对照：Base→teacher、Instruct→teacher、Base→gold；各 checkpoint 自带的原生 A/B/C 单 token 概率另做不训练基线。在 teacher 分支不把 gold 混进训练目标；gold 仅用于独立评测和独立 calibration。这能在当前 toy 内比较两种监督和 Base/Instruct 初始化。本次 train 的 Choice/Score 教师目标全部等于 gold one-hot，teacher/gold 的直接标签差异仅来自 64 道 Boolean 软目标；不能据此概括教师监督训练在通用任务上的优劣。首轮一个 seed 是通路检查；规模化决策需多个 seed，并避免所有超参全排列。

小试工程默认：FP32 参数与 Adam 状态、BF16 autocast；12 步只训练头（lr=1e-3），120 步全参训练（backbone lr=2e-5，head lr=2e-4），每步 12 道完整问题，AdamW weight decay=.01，梯度 norm clip=1，dropout=0。每 24 个全参步只在 dev 上选择 checkpoint。数字是冻结的小试配置，不是已证明最优配方；变化要作为新实验记录。

为什么先训头再解冻：新读出开始随机，先让它有非随机监督方向；但固定 backbone 是否足够也要通过 head-only 基线测量。为什么不默认 QLoRA：当前 0.6B 与 80GB 资源没有该需要；量化会增加新的数值因素。扩大模型后，LoRA rank、投影位置与全参训练同样由精度/成本对照决定。

测试集完全不用于 early stopping、头选择、学习率选择或温度拟合。模型版本、实际 resolved revision、依赖版本、数据 hash、参数量、seed、训练日志、筛选审计和 checkpoint 一起保存。任何失败都要保留日志，不能重跑到某次好看结果却不报告选择过程。

## 8. RLCD 应该怎样研究，而不是只加一个 RL 标签

单样本正确性奖励 `r=1[a=y]` 的期望是 `p_y`，它倾向把概率推到最大，不是一个要求恢复真实事件概率的目标。只看到“RL”不能推断 Jev 用的是这个奖励，更不能直接把 GRPO 接上就宣称复现 RLCD。

可证明的候选是 categorical Brier：`Brier(p,y)=Σ_i(p_i−1[i=y])²`。最小化它的条件期望可恢复条件类别分布。我们输出全部 p，**可直接精确求 loss 和梯度**，应先把它作为 log-loss 的替代目标对照。

若要检验 RL 形式，采样 `a,b iid~p`，用对称奖励：

```text
r(a,b,y) = 1[a=y] + 1[b=y] - 1[a=b]
E[r] = 2*p_y - Σ_i p_i² = 1 - Brier(p,y)

policy gradient estimator:
  r * (grad log p(a) + grad log p(b))
```

两次采样都依赖策略，不能只回传一次 log-prob。baseline 需不引入动作相关偏差。若监督是完整 teacher q，可用 `r=q_a+q_b−1[a=b]`，期望为 `||q||²−||p−q||²`。这些是我们的可验证构造，不是已知 Jev 配方。

实验从同一个预训练学生 checkpoint 出发，在相同数据、步数/计算预算下比较 log-loss、精确 Brier、上述 Monte Carlo policy gradient。先通过小维度枚举/有限差分核对期望与梯度，再跑真实训练。关注 heldout Brier/NLL、分布一致性、样本效率和方差；若精确 Brier 更好且更快，首版保留精确优化。GRPO 组归一化、KL anchor、entropy bonus、clipping 都会改变目标或估计，不能在未推导时当作无害默认项。

数学与已做的代数检查见 [RLCD 分析](rlcd_theory_zh.md)。真正值得投入的是“概率目标是否 proper、数据如何覆盖不确定性、推理结构是否高效”，算法名字本身不能替代这些条件。

## 9. Benchmark：教师一致性、真实校准、结构正确性、速度分别测

| 维度 | 具体指标 | 回答什么，不能回答什么 |
|---|---|---|
| Teacher fidelity | forward KL、TV=`.5Σ|pS−pT|`、soft CE、argmax agreement | 是否像 Jev；对舍入 proxy 的一致不等于真实概率正确 |
| 真实标签质量 | Accuracy、NLL、Brier（类维求和）、Score MAE/归一化 MAE | 正确性与 proper score；Brier/NLL也受辨别力影响，不能全部叫“纯校准误差” |
| 校准 | 10-bin top-label ECE、bin统计/可靠性、校准前后 NLL/Brier | 概率与频率的关系；ECE只作辅助，小样本/分箱会影响它 |
| Selective prediction | coverage-risk 曲线/拒答阈值 | 低置信时是否可靠地降低自动化覆盖；阈值在 dev 定，不在 test 定 |
| 结构 | 候选置换、同state题重排、增删无关题、跨state混批、改变被隔离state | mask/映射/隔离是否正确；浮点误差与语义泄漏分开记录 |
| 扩展 | 新规则族、未见候选描述、跨语言、K外推、长state、否定/缺证据 | 是否超出固定模板记忆；当前toy只覆盖其中很小一部分 |
| 系统 | warm p50/p95、questions/s、states/s、peak memory、按S/J/K/长度分层 | 多state同批是否有吞吐收益；不能用HTTP并发当模型并行证据 |

分区用途严格固定：train 学参数；dev 选 checkpoint/架构；calibration 只拟合温度；test 一次最终报告；OOD 独立显示新规则族。当前 evaluator 在 calibration 上搜索单一 T∈[.25,4]，按 gold NLL 选择，若最优在边界明确报告。校准前 teacher fidelity 是主要模仿指标；校准可能降低 gold NLL 同时降低 teacher 一致性，这个 tradeoff 应保留而不是隐藏。

同 state 三题相关，置信区间至少按 state 聚类 bootstrap；今后多个模板/来源需进一步按 source group/family 抽样。不要把 432 题当 432 个独立真实任务。teacher 出现 0 真值概率时，计算 NLL 所用的概率 floor（对应 NLL 截断上限）需写入报告，并计数零概率事件。

大 K 单独建立 K=2/4/8/16/32 与 heldout 64/128/255 测试。只有正确候选始终被强制保留的子集任务，会改变目标分布，必须说明；缺少正确项时要有明确 `none` 或另行定义题目，不能偷用旧标签。延迟固定硬件、精度、warmup 和同步方法，分别报告 tokenization、GPU 前向、head、网络与序列化；当前 toy timing 仅包含张量整理+GPU前向+head，排除 tokenizer/网络，并明确不共享前缀。

## 10. GitHub 仓库怎样帮助我们

**TheoLeeCJ/openjev**，审计固定 `b4782a6c953f05c6255706d7a219f4e032af5b58`：确有 frozen Qwen3.5-4B 的单步选项 logits 和同 state prefix cache 复用，多题 suffix 一批计算。值得借鉴其 native baseline、token-prefix 一致性检查与结果清单。它目前没有本项目所需的分布训练、RLCD 或跨 state 调度；A–P 读出只支持 2–16 个选项，其 Qwen3.5 hybrid linear-attention/recurrent cache 不能直接套用 dense-tree mask 证明。公开预测中 shared 路径有 6/777 次 argmax 翻转，需要定位；不能直接当作无害 BF16 误差。见 [代码与结果审计](openjev_repo_audit_zh.md)、[仓库](https://github.com/TheoLeeCJ/openjev)。

**vinnylarouge/jevlike**，审计固定 `94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452`：有 frozen Transformer 表征加候选 cross-attention 头、简单 hard-CE 训练和环境 PPO 示例。可作 head-only 效率基线；现有 toy 任务与 PPO 不等于通用校准决策教师监督训练。已发现 checkpoint clone、ECE端点和随机集合顺序等需要修复的问题，未执行其代码或加载外部 checkpoint。见 [审计](jevlike_repo_audit_zh.md)、[仓库](https://github.com/vinnylarouge/jevlike)。

因此采用其可检验的部件与基线，不把任一仓库整体视为已经复现 Jev。也不能因为它们尚未训练就忽略其推理实现价值。

## 11. 实施顺序、产物与升级条件

| 阶段 | 实际产物 | 进入下一阶段的依据 |
|---|---|---|
| 0 契约/调研 | 本文、来源表、两轮Fable裁决、两个仓库审计 | 输入/输出/概率/独立性定义无歧义；未知内部机制保留为未知 |
| 1 数据闭环 | builder、五个split、manifest、原始teacher响应、费用账本 | schema/分区/label映射/舍入覆盖审计通过 |
| 2 训练闭环 | native baseline、Base teacher、Instruct teacher、Base gold、best checkpoint | loss有限、梯度有效、只dev选模型，完整predictions可被独立评估器读取 |
| 3 基准闭环 | test/OOD metrics、calibration、cluster CI、batch timing、结构检查 | 公开报告成功与失败；不以toy胜出认定通用能力 |
| 4 结构优化 | flat/tree相同权重对比、GPU kernel profile、batch推理入口 | 输出/梯度/隔离一致，且真实吞吐或显存改善 |
| 5 数据和容量扩展 | 更多规则族/真实文本任务、learning curves、K与长度外推 | 明确识别主要误差来源，新增数据/容量对应实际缺口 |
| 6 校准算法对照 | log-loss / exact Brier / policy-gradient 同起点实验 | proper scores与可靠性实证获益，匹配计算成本后仍合理 |
| 7 开源打包 | 可复现构建器、训练/推理/评测脚本、configs、模型卡、可发布权重与来源记录 | 结果可复跑、artifact来源清楚；API密钥和私有聊天/原始teacher日志不进入公开仓库 |

8 张卡优先用于独立对照、随后候选seed，不自动启动 8 卡同步训练。不要一次做“所有初始化×所有头×所有loss×所有学习率×所有seed”的全排列；先淘汰明显无效结构，再给领先方案等额调参预算。

当前授权 API 额度 $25，可用于必要的覆盖与算法实验。本批 teacher 标注约 $0.00322；新增额度优先用于高 K、歧义、规则变化及独立评估。每批记录调用与费用上限、落盘去重、失败无隐式无限重试。训练资源与本机 Claude 订阅/CLI标价单独记录，不能混为 Vercel 扣费。

追加40题冻结学生测试的平均解析分布TV为0.3521，K=255分层为0.6846；最长路径1699 tokens。K、长度、题族和标签风格同时变化，不能单独归因于K，但已足够说明下一轮应先补多类软分布与规则覆盖，而非把动态255维输出当作质量验收。见 [冻结学生诊断](student_distribution_probe_brief_zh.md)。

当前状态以 `toy_experiment_report_zh.md` 和机器可读结果为准；本文件中规模化、RL 和生产共享 kernel 是已明确算法与验收条件的后续工作，不表示已训练出完整 Jev 替代模型。
