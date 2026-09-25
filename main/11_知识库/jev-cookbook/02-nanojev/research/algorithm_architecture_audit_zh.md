# OpenJev 算法与架构实现审计

核验日期：2026-09-17。本文件假设已有 `state / question / candidates / target`，只解决怎样前向、训练和共享计算。方案是独立开源设计，不是对 Jev 内部网络的断言。本机 Python 3.14.6 未安装 torch、transformers、numpy；本轮没有安装依赖、下载权重或训练，因此下列 HF/PyTorch 代码为源码核验后的实现规格，尚非真实模型实测。

## 1. 主推路线与明确取舍

**主推：dense Qwen3 的 `Qwen3Model` 骨干 + 共享标量读出头 + 按题归一化，训练采用共享前缀树的整张计算图。** 先用同权重的独立路径 forward 做数值裁判，再用树形 eager/SDPA 掩码核对正确性；CUDA 上通过验证后改成 FlexAttention BlockMask。推理可先用分阶段 prefix KV 实现实用的共享计算，训练不套用生成式 DynamicCache。

Base 与 Instruct 都可去掉生成出口使用，不需生成思维链。选同规模做对照，不由作者反对 RLHF 的观点预设 Base 必胜，也不把参数量锁死为 0.6B。0.6B 配置仅用于下面的具体形状示例。先只支持 dense、无滑窗、固定 RoPE 配置，避免把 MoE 调度、动态 RoPE 变化带入首个等价性测试。

`AutoModel`/`Qwen3Model` 返回 hidden states，`Qwen3ForCausalLM` 才额外做词表投影；调用骨干可避免构造 `[B,N,V]` 输出。**删除 LM head 不会抹掉所有词表参数**：输入 embedding 仍保留，且官方 0.6B Base 将 input embedding 和 LM head 权重绑定。随机初始化的 scalar head 也不是现成的语义分类器，仍需要已有目标数据训练。[HF v5.17.0 Qwen3 源码](https://github.com/huggingface/transformers/blob/v5.17.0/src/transformers/models/qwen3/modeling_qwen3.py)、[Qwen 官方配置](https://huggingface.co/Qwen/Qwen3-0.6B-Base/blob/main/config.json)

备选仅两条：若树 kernel 尚不可靠，使用独立路径真正的张量 batch，接受重复 state 的成本；若 Choice 的集合依赖能力不足，在共同骨干之上加入仅用于 Choice 的置换等变集合头。不要为共享计算先改成双向 encoder——那会改变函数，失去与原 causal forward 的严格对照。

## 2. 定义网络函数、张量与读出

对状态 `b`、问题 `j`、候选 `k`，定义 token 路径：

```text
S_b → Q_bj → C_bjk + R
h_bjk = 最后一层、R 最后一个 token 的 hidden state
z_bjk = wᵀ h_bjk
```

`S` 包含固定全局格式前缀和 state；`Q` 包含类型、instructions、criteria，但不带其它题或当前题的其它候选；`C` 包含当前候选的语义描述。`R` 是固定读出后缀，例如预先分词的 `\nScore:`；取哪个 token 由索引明确记录，不靠“最后一个非 pad”猜。可以训练新的特殊 readout token，但需要扩 embedding 并训练该行，首版没有必要。

**分词必须先锁定。** `tokenize(S)+tokenize(Q)+tokenize(C)` 未必等于 `tokenize(S+Q+C)`，边界 BPE 合并会破坏共同前缀。先分别分词固定分隔格式的各段，关闭自动加特殊 token，显式拼接 token IDs；独立版与树版使用完全相同的段 token。BOS 只出现于 state 根节点。

| 张量 | 形状 |
|---|---|
| 树中 token IDs、path position、node ID、local offset、valid | `[B, Nmax]`；一批多个独立 state |
| 全层 hidden states 中的当前层 | `[B, Nmax, d_model]` |
| 每层 Q | `[B, Hq, Nmax, d_head]` |
| 每层 K、V | `[B, Hkv, Nmax, d_head]` |
| dense allow mask | `[B, 1, Nmax, Nmax]`，head 维广播 |
| 所有叶子 hidden / logits | `[M,d_model]` / `[M]`，`M=Σ_bj K_bj` |
| 每题分布 | ragged `K_bj`；也可 padding 成 `[B,Jmax,Kmax]` 并掩蔽无效项 |

Qwen3-0.6B-Base 官方配置为 `d_model=1024, Hq=16, Hkv=8, d_head=128, layers=28`。不能假设 `Hq*d_head == d_model`，本例为 2048 与 1024；复用官方 Q/K 归一化、投影和 GQA 实现，不自己按常见简化形状重写。[官方配置](https://huggingface.co/Qwen/Qwen3-0.6B-Base/blob/main/config.json)

类型后处理为：

```text
Choice: p_j = softmax(z_j)
Noul:   用 true/false 两个候选，p_true = sigmoid(z_true - z_false)
Score:  p_j = softmax(z_j); score_j = Σ_k k * p_jk
```

每个题的 softmax 独立；不跨题、跨 state 归一化。Score 序号只在后处理及 ordinal loss 中出现，不加进该级文本输入；同题概率经过归一化会相互影响，这与“每级语义独立读出”并不矛盾。

## 3. 树掩码与位置：实现的硬条件

每个 state 一棵树，`S` 为根，各 `Q_j` 为其子节点，各 `C_jk+R` 为相应问题的子节点。每个节点是一段 token；按前序把节点排进张量。token `i` 能读取 token `t` 当且仅当：

```text
same_state(i,t) AND valid(i) AND valid(t) AND
[
  node(t) 是 node(i) 的严格祖先
  OR (node(t)==node(i) AND local_pos(t)<=local_pos(i))
]
```

因此 state 只看 state 前缀；问题看完整 state 和自己的问题前缀；候选看完整 state、自己的问题和自己的候选前缀。**没有其它问题、其它候选、其它 state 的 token 边。** 用一条普通下三角掩码处理整棵树会泄漏较早排入的兄弟分支。

祖先关系无需储存 token 级 `N²` 布尔表：给树节点做 DFS 编号 `tin,tout`，严格祖先测试为 `tin[t] < tin[i] < tout[t]`。给每个 token 保存所属节点的编号，供 Flex mask 函数直接读取。节点内仍使用 local offset 的因果关系，不能只比较位置编号。

位置是**从根到当前 token 的路径深度**，不是在 packed tensor 里的列号：

```text
S:       0 ... s-1
Q_j:     s ... s+q_j-1             # 每个问题从 s 起
C_jk+R:  s+q_j ... s+q_j+c_jk-1    # 每个候选从自己的共同前缀末端起
```

这不是每个节点都从 0 起，也不是给所有 token 用递增全局位置。不同分支可以拥有相同 position ID，因为它们被 attention mask 隔离。保留官方 RoPE 参数，在相同 token/位置上应用同一个旋转。使用 dynamic NTK/其它依赖整批最大长度的缩放时，共享树和独立短路径可能得到不同旋转；第一版禁用此变量或强制两边使用完全相同的固定 RoPE 频率。

padding 的 key 不应被真实 token 读取。对完全空的 padding query 行，给它一个只用于数值稳定的自环、随后丢弃输出，避免全 `-inf` softmax；该自环不连向任何真实读出。

**重要 HF 陷阱：** v5.17.0 在 `attention_mask=None` 时会根据 position ID 跳变推断 packed sequences。树的兄弟分支会触发这种推断并切断应存在的祖先连接，所以必须显式传 tree mask。该版本 `masking_utils` 对 4D tensor/BlockMask 有原样返回路径，Qwen3 层再消费该结果。不要仅设置 position IDs 就期望自动实现树注意力。[固定版本 masking 源码](https://github.com/huggingface/transformers/blob/v5.17.0/src/transformers/masking_utils.py)

## 4. 可直接实现的 dense 参考 forward

以下内核接收 packer 已生成的元数据；不依赖任何生成 API。`ancestor[b,u,v]` 表示节点 `u` 是节点 `v` 的严格祖先；生产版改成 DFS 区间，下面只作清晰的正确性实现。

```python
# 输入：ids,pos,node,offset,valid 均 [B,N]；ancestor 为 [B,Vnode,Vnode]
# 叶子索引 leaf_b,leaf_t 均 [M]；每题候选分组 ptr 为 [Jtotal+1]
B, N = ids.shape
b = torch.arange(B, device=ids.device)[:, None, None]
ni, nt = node[:, :, None], node[:, None, :]
same_node = ni == nt
is_ancestor = ancestor[b, nt, ni]
within_node = same_node & (offset[:, None, :] <= offset[:, :, None])
allow = (is_ancestor | within_node) & valid[:, :, None] & valid[:, None, :]
# pad query 自环；真实 query 仍不能读 pad key
eye = torch.eye(N, dtype=torch.bool, device=ids.device)[None]
allow = allow | ((~valid)[:, :, None] & eye)

# eager 使用加性 mask；SDPA 也可直接用 allow[:,None] 布尔 mask。
mask = torch.zeros((B, 1, N, N), dtype=backbone.dtype, device=ids.device)
mask.masked_fill_(~allow[:, None], float('-inf'))
hidden = backbone(
    input_ids=ids,
    position_ids=pos,
    attention_mask=mask,
    use_cache=False,
).last_hidden_state
z = head(hidden[leaf_b, leaf_t]).squeeze(-1).float()  # head=Linear(d,1,bias=False)
p = [z[ptr[j]:ptr[j+1]].softmax(-1) for j in range(len(ptr)-1)]
loss = sum(question_loss(p[j], target[j]) * weight[j] for j in range(len(p)))
loss.backward()
```

pad 的 `node` 使用合法占位节点编号，避免在 apply valid mask 前越界 gather。首轮使用 `attn_implementation="eager"`、FP32、所有 dropout=0；通过独立路径等价检查后换 SDPA。网络用 `AutoModel.from_pretrained(...)` 或 `Qwen3Model.from_pretrained(...)`，另注册 `Linear(config.hidden_size,1,bias=False)`。不要调用 `generate()`；不要给 `AutoModelForCausalLM` 跑完整词表投影后才截取 hidden state。

HF 的布尔 SDPA mask 为 True=允许；浮点 mask 为 0=允许、`-inf`=禁止。eager 是加法，所以用浮点 mask。2D padding mask 的 0/1 浮点约定不能照搬到 4D。若手动调用 `scaled_dot_product_attention`，显式自定义完整 mask 时设 `is_causal=False`，避免再叠加另一套因果规则；在 HF 内应检查实际 backend 的转发逻辑。[HF attention 文档](https://huggingface.co/docs/transformers/en/attention_interface)

## 5. 训练梯度为什么能共享，什么时候不能

在固定 token、相同位置/可见祖先、同一参数、关闭随机性时，树只是将独立路径里重复的共同前缀合并成同一个计算节点。逐层归纳可得每个叶子的 hidden state 与独立路径相同，任何相同叶子损失的参数梯度也相同。

共享 state 的反向信号是所有后代贡献之和：`∂L/∂h_S = Σ_descendants ∂L_descendant/∂h_S`。正常 autograd 会汇总，不能为了“避免重复训练 state”再除以候选数。归一化应在两版共同的 loss 定义中完成，例如按题平均；候选数多的题不应因为 flatten 行数而被偷偷加权。

训练时整树 forward 使用 `use_cache=False`，保留 state 到后代的完整计算图。对 state 做 `detach()`、将旧 optimizer step 的 KV 重用、分别更新每个候选后仍保留旧缓存，都会破坏等价训练。HF 官方将生成缓存定位为 inference；不能把 DynamicCache 当成保证支持梯度和分支的训练容器。[HF 固定版本缓存说明](https://github.com/huggingface/transformers/blob/v5.17.0/docs/source/en/cache_explanation.md)

注意以下严格等价条件：关闭 attention、MLP、LoRA 等所有 dropout，或显式复用同一随机掩码；使用相同 loss 归一化；没有跨 token 的 batch statistics；没有依赖 batch 容量的 MoE 路由；RoPE 不因两种 packing 改变。低精度、不同 kernel 的归约顺序会产生数值误差，不能承诺逐 bit 一样。

## 6. 推理 prefix KV：可行，但默认 cache 不会自动做树

最直接的分阶段执行：

1. 对各 state 做一次 prefill，得到每层 `KV(S_b)`。
2. 同一 state 的所有问题作为 batch，以各自逻辑前缀 `KV(S_b)` 处理完整 `Q_bj`，得到 `KV(S_b+Q_bj)`。
3. 同一问题所有 `C_bjk+R` 作为 batch，一次处理每条完整候选后缀；取 readout hidden、统一归一化。

这是少数几个依赖阶段，不是逐个生成答案，也不是每个候选一个串行请求。不同长度应分桶/正确 padding。KV 的逻辑形状为每层 `[Bbranch,Hkv,Lprefix,d_head]`；同时传入正确的后缀位置、past+new key 长度掩码。

**默认 DynamicCache 是可变容器，不提供自动 fork/copy-on-write 语义。** 第一个子分支会追加 KV；不能把已追加的同一对象再给第二个兄弟，否则发生污染。最保守可实现版本是克隆父缓存并按 batch 复制：它节省 prefill 计算，但仍复制 prefix 显存。真正共享物理存储需要只读前缀加分支增量的自定义容器/层，或经过验证的分页注意力；不把 `expand()` 一个视图就宣传为安全零拷贝，因为追加/原地写入及 kernel 连续性要求需要另外处理。

读出一次性返回所有候选的 logits，不能让运行时“为了只返回一个 next-token”而把它们丢掉。HF 当前普通 cache API 足够做保守分阶段原型，但无法由一个参数获得完整树 scheduler。[Cache strategies](https://huggingface.co/docs/transformers/en/kv_cache)

## 7. FlexAttention：加速阶段的接口与成熟度

本轮查验 **Transformers v5.17.0、PyTorch v2.14.0** 的官方 tagged 源码；历史 v4.57.1/v2.8.0 也有相关机制，但不能把不同版本文档片段拼成一段保证可运行的代码。应把实际运行组合、GPU、driver、CUDA 和模型 revision 写进 lockfile/报告。

```python
from torch.nn.attention.flex_attention import create_block_mask

def mask_mod(b, h, qi, ki):
    # 读取预先放在同设备上的 token→node/localpos/tin/tout/valid 元数据
    # 返回第3节的布尔允许条件；处理块尾越界和padding query。
    ...

bm = create_block_mask(mask_mod, B=B, H=None, Q_LEN=N, KV_LEN=N, device='cuda')
# Qwen3Model 在已核验版本可将 BlockMask 传给层；实际集成仍须数值/反向检查。
out = flex_backbone(input_ids=ids, position_ids=pos,
                    attention_mask=bm, use_cache=False).last_hidden_state
```

选 `attn_implementation="flex_attention"` 只解决 backend 选择，不会替我们构造 tree mask、位置和分组读出。默认无 mask 路径仍可能生成错误的 packed causal mask。自定义 backend 名称时还要注册配套 mask formatter；否则 Transformers 可传入 `None`，静默丢失约束。训练 mask 在各层相同可复用，布局改变须重建；可以按 shape 分桶降低编译与 mask 开销。

已核验的现实限制：

- HF v5.17.0 Flex 对 `attention dropout>0` 直接报错；官方 Qwen3-0.6B Base 默认为 0，但仍检查实际载入 config/LoRA dropout。
- PyTorch v2.14.0 仍标为 prototype。源码明确 **CPU/MPS 不支持 backward**，所以本项目的 Flex 训练路线以 CUDA 为目标；Mac 上的 correctness 可走普通 eager/SDPA，不能承诺 MPS Flex 训练。
- GQA 需要正确的 Q/KV 头映射；保留 HF Qwen 的投影、QK normalization、RoPE 和 backend 封装，只更换 attention mask/计算，而非重写完整 Qwen。
- dense mask 传给 eager/SDPA 只是正确性实现，未必跳过屏蔽乘法；FlashAttention-2 的通常 2D padding mask 不能表达此树。Flex 应使用真正 BlockMask，不能指望任意 4D dense tensor 自动变成稀疏加速。
- 大块遇到短候选时可能大量变成 partial block。mask 构造、动态重编译、padding 和调度开销可能吞掉理论收益；公开 kernel 榜单不能预测本项目速度。

依据：[HF v5.17.0 Flex integration](https://github.com/huggingface/transformers/blob/v5.17.0/src/transformers/integrations/flex_attention.py)、[PyTorch v2.14.0 Flex 实现](https://github.com/pytorch/pytorch/blob/v2.14.0/torch/nn/attention/flex_attention.py)、[官方 FlexAttention 设计说明](https://pytorch.org/blog/flexattention/)。

## 8. 成本模型：按路径和有效注意边计数

令 `s_b=|S_b|, q_bj=|Q_bj|, c_bjk=|C_bjk+R|`，都包含实际分隔 token。独立展开与共享树处理的 token 数分别为：

```text
T_flat = Σ_bjk (s_b + q_bj + c_bjk)
T_tree = Σ_b s_b + Σ_bj q_bj + Σ_bjk c_bjk
```

每层每个 query head 的有效 causal attention 边数：

```text
E_flat = Σ_bjk L_bjk (L_bjk+1)/2
E_tree = Σ_b s_b(s_b+1)/2
       + Σ_bj [s_b*q_bj + q_bj(q_bj+1)/2]
       + Σ_bjk [(s_b+q_bj)*c_bjk + c_bjk(c_bjk+1)/2]
```

MLP/投影成本大致随 `T`，attention 点积/加权成本随 `E*Hq*d_head`；每层投影实际尺寸以 config 为准。共享前缀仍会被每个后缀 query 读取，所以不会消掉 `s*q` 或 `(s+q)*c` 项。推理 cache 的理想 KV 字节量为 `2*layers*Hkv*d_head*T_tree*bytes_per_value`，不包含 activations、临时量、padding 或物理复制；默认 batch 复制缓存常达不到这个下界。

dense packed mask 的内存仍是 `O(B*Nmax²)`，dense attention 也可能执行这一量级的工作。**T_tree 小于 T_flat 不代表 dense tree 必然更快。** 很多短前缀、长候选聚成巨树时，兄弟间被屏蔽的笛卡尔积甚至使 dense tree 比独立 batch 更慢。真正稀疏 kernel 跳过整块后，才可能更接近 E_tree；padding 到块边界也增加实际工作。

应分别记录 tokenization、mask/BlockMask 创建、编译、prefill、分支前向、归一化、端到端时延与峰值显存；冷启动和热缓存分开。吞吐至少按 state、问题、候选三种单位报告，不能用“HTTP 并发数”替代。

## 9. Choice 的 IIA 限制与第二结构

独立 scalar scorer 满足：`p(a)/p(b)=exp(z_a-z_b)`；新增候选不会改变原两项的相对 odds。这是结构性 IIA 限制，与 softmax 温度或训练数据量无关。

反例：题目要求选择候选集合中最接近其平均值的数字。`{0,4,5}` 应选 4；加入 100 后 `{0,4,5,100}` 应选 5。若 `h_4,h_5` 都不读取候选集，两者相对排序不能翻转。不能声称首版覆盖所有集合相关语义。

可选修复：

| 方案 | 能力/代价 | 建议 |
|---|---|---|
| 把完整候选集写进 Q | 仍共享 S/Q 前缀，可以学习集合关系；Q 长度变为包含所有候选，且文本顺序引入偏差 | 简单可行对照，需候选换序增强和稳定性测试 |
| 基于候选 hidden 的集合头 | `u=mean_k φ(h_k)`，`z_k=ψ([h_k,u,log K])`；也可无位置编码的候选 self-attention | 推荐作为第二结构，保留主干共享和置换等变 |
| 代码处理精确集合规则 | 对排序、均值等可执行规则零歧义 | 与模型判断组合，避免强迫模型做精确计算 |

集合头若每个候选使用相同 φ/ψ、pool 对称、无候选序号特征，则候选置换会等变地置换输出；这不自动保证标签改写不变，也不保证它学会所有关系。相比将整个集合写回语言骨干，它无法恢复候选 hidden 已经丢弃的细粒度信息，应实测任务收益。

**Score 分支保持级别隔离。** 不使用上述候选 set context/集合头；独立编码每个等级，归一化后算分布/期望。官方 Score 文档说不看相邻等级或等级数值，不能为了 Choice 更灵活而破坏这个接口语义。训练 ordinal loss 可以用顺序信息指导输出分布，和推理向某一级暴露其它级别文本是不同机制。[TypeSafe Score 文档](https://docs.typesafe.ai/primitives/score)

## 10. 最小验收测试与不能承诺的部分

测试应先用随机小模型通过，再用**同一真实 Qwen checkpoint 的骨干**验证；纯 Python attention toy 只能验证数学机制，不能替代 HF 整合。

| 必须测试 | 方法/应发现的问题 |
|---|---|
| 路径等价 | 完全相同段 token，比较独立路径与树版每层对应 hidden、叶 logits 和题分布；关闭 dropout |
| 梯度等价 | 相同叶损失/归一化，比较 embedding、Q/K/V/O、MLP、norm、head、LoRA 的梯度；确认 state 未 detach |
| 分支与 state 隔离 | 改其它题/其它 state/兄弟候选文本，检查本叶 hidden/logit 不变；Choice 加候选后概率归一化变化不算泄漏 |
| permutation | 改问题排列、候选排列、batch state 排列，映射回原 ID 后一致 |
| position 反例 | 故意用 packed arange 或每节点从0起，测试应失败；否则测试可能太弱 |
| mask 反例 | 故意改成普通下三角或允许兄弟边，测试应检测跨题/候选污染 |
| cache fork | 分支执行顺序改变不影响 logits；不能复用已被兄弟追加的对象 |
| 分词边界 | 保存并比较实际 path token IDs，而非只比字符串；含不同候选前导空格/标点 |
| padding/GQA | 不同 state/候选长度、pad query、空内容、单候选，检查 finite 输出及所有有效路径 |
| backend | eager→SDPA→Flex 分别比较 forward/backward；版本、dtype、误差容限写入报告 |
| 性能 | 实际负载扫描 s/J/K/c、分桶与块大小；同时比独立 batch、dense tree、prefix KV、Flex tree |

不能提前承诺：共享树必然提速、Mac 上 Flex 反向可用、0.6B 能达到 Jev 质量、Base 一定优于 Instruct、树注意力就是 Jev 的内部架构、经过 scalar readout 就自动获得校准。能明确实施的是**一个有独立路径裁判、完整梯度、严格隔离、可替换 kernel 的概率判别模型**；算法与真实反馈如何改善质量由相同骨干/数据/预算实验决定。
