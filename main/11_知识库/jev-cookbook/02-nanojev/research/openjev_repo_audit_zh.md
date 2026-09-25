# TheoLeeCJ/openjev 固定版本源码审计

审计日期：2026-09-17。仓库：[TheoLeeCJ/openjev](https://github.com/TheoLeeCJ/openjev)。固定 commit：[`b4782a6c953f05c6255706d7a219f4e032af5b58`](https://github.com/TheoLeeCJ/openjev/tree/b4782a6c953f05c6255706d7a219f4e032af5b58)，获取时为 `master`。

只读下载了必要源码、文档、清单和少量已发布结果到 `/private/tmp/openjev_audit_b4782a6`。没有执行仓库代码，没有安装依赖、下载模型、调用 Jev/付费模型或读取本项目 `.env`。数值核对使用我们自己写的 JSON 解析及哈希代码；这与重跑 GPU 模型不同。

## 结论：有实质共享计算的冻结基线，值得复用，但不是已训练的 Jev 复刻

它不只是一个 JSON 包装器：实现了通用自然语言问题、受限选项 logits 直接读出、同 state 的 native prefix cache，以及一次 batch 的多题后缀前向。作者明确没有复现 Jev 的未知网络、RLCD 或已校准概率；这个边界与代码相符。[README](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/README.md)

**建议把 frozen direct 和 shared suffix 作为我们必须超过的两条基线，并复用它的 tokenizer 边界检查、缓存分支、计时和结果清单设计。** 我们新增的工作应聚焦直接概率训练、可训练读出、候选/问题泛化、真正跨 state 调度与经验证的共享训练图。没有必要重写其已经处理好的基础检查，也不能把其已有共享前缀能力写成“尚未实现”。

## 1. forward、batch 与 cache：代码实际做了什么

| 模块 | 已实现 | 与本项目目标的差别 |
|---|---|---|
| `direct.py` | 把 state、criterion、全部 options 放进 prompt；一次 forward，取最后位置的固定大写字母 token logits，再对合法字母归一化 | 保留 LM head；没有 scalar head 训练；概率是条件化 token score |
| `serial.py` | 相邻相同 state 复用一次 prefill；每题 `deepcopy` 父缓存后独立处理后缀 | 保存重复计算，但题目仍串行，且复制 cache |
| `shared.py` | 验证所有 rows 为同一 exact state，prefill 一次，`reorder_cache(zeros(batch))` 扩成各题分支，后缀 batch 一次 forward | 是真实模型 batch；不是物理零拷贝前缀，也不是共享训练图 |
| `cli.py` | shared 模式接受同 state 多题；direct/reranker 模式逐 row 调用 | 没有独立 states 的 unified batching scheduler |
| `benchmarks/shape777.py` | 37 个 state 各自 21 题，state group 外层循环 | 777 次判断不是 37 states 同时做一张 batch |

代码：[direct](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/src/openjev_phase1/direct.py)、[serial](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/src/openjev_phase1/serial.py)、[shared](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/src/openjev_phase1/shared.py)、[CLI](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/src/openjev_phase1/cli.py)、[shape777 runner](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/benchmarks/shape777.py)。

`core.py` 限定 **2–16 个选项**，用 `A` 到 `P` 映射输出，候选 ID 不作为语义文本进入 prompt。每个 slot 必须是一个可精确 round-trip 的 token；还验证 `tokenize(prompt+letter) == tokenize(prompt)+[letter]`。这比直接假定 A/B token ID 可用更可靠。超过最大输入长度会报错，不静默截断。[core.py](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/src/openjev_phase1/core.py)

同一题的所有候选都放进问题 prompt，所以这一路径可以利用候选集合关系，**不受我们逐候选 scalar scorer 的相同 IIA 限制**。相应代价是序列顺序影响，以及不符合 Score“每级不读取邻级”的独立语义。源码没有原生 Score 期望、ordinal loss 或 Jev confidence 实现；二选一可表达 Boolean 判断，但它仍是通用选项协议。

## 2. shared 路径的合理设计与需要加的检查

有价值的实现细节：

- `_state_prefix` 只截取 evidence 前缀，并去掉最后一个边界 token，以降低 JSON 标点造成分词合并的风险；然后逐题核对 token prefix 真正一致，不一致就拒绝。
- 后缀右侧 padding，attention mask 覆盖 `prefix+suffix`；position IDs 从真实 prefix 长度起；实际最后 token 的位置单独记录。
- 每题是独立 batch row；它没有把其它题的答案拼给当前题。从代码构造看，预期实现的是题间隔离。
- prefix prefill、cache replicate、suffix forward 分别计时；使用 `torch.inference_mode()` 并同步 CUDA。

这些设计不等于已经证明数值等价。`tests/test_shared.py` 只有 layout/padding 与空后缀拒绝两类测试，未见真实模型的跨题扰动、分支排列、cache 隔离、FP32 对照或梯度测试。[测试源码](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/tests/test_shared.py)

另一个可优化点：它把所有不同后缀末端位置合并为 `selected_positions`，每个 batch row 都在这些位置做词表读出，再取自己的一个位置。当有 `J` 题、`U` 个不同末端位置时，中间 logits 可达到 `[J,U,V]`，最终只有 `[J,K]` 被使用。可改为 gather 每个 row 的真实最后 hidden，再只投影所需 token 行，或者训练新的 scalar head；不能把当前实现描述成已经移除词表投影。[shared.py](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/src/openjev_phase1/shared.py)

serial 模式记录了合法 token 的原始质量 `allowed_token_mass`，以及全词表 argmax，有助于看见 forced-choice 丢掉的信息；当前 direct/shared 公开 scorer 没有一致暴露这两个诊断字段。复用时宜统一。

## 3. 模型结构不能直接等同于我们的 Qwen3 树

仓库模型清单锁定：

- direct：`Qwen/Qwen3.5-4B`，revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`。
- reranker：`Qwen/Qwen3-Reranker-4B`，revision `22e683669bc0f0bd69640a1354a6d0aebcfeede5`。

其 loader 要求远程模型固定 40 位 SHA，`trust_remote_code=False`，只暴露一张 CUDA GPU；Qwen3.5 选择原生 text config/model 类。依赖固定为 torch 2.10.0、Transformers 5.17.0 等；这些是仓库环境记录，不是本机已验证可运行的安装组合。[模型清单](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/manifests/models.json)、[requirements](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/requirements.txt)

我们另核验了它所锁定 revision 的 **Qwen 官方配置**：32 层中有 24 层 `linear_attention`、8 层 `full_attention`，词表 248,320。它不是纯 Qwen3 full-attention 堆栈。缓存包含相应 native 状态；把我们的任意 4D 树掩码套到所有层，不会自动分叉线性递归状态。若以后采用 Qwen3.5，需要为线性层明确实现树分叉或保守的批量缓存复制，并重新验证等价性。[锁定模型官方 config](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)

## 4. 训练、数据与已发布结果

当前源码是冻结 inference/evaluation 项目，未提供可训练 scalar head、优化器循环、RLCD reward、校准训练器、LoRA 成品或学生权重。作者将它定位为 Phase 1，后续再研究目标语义与校准；不要把 docs 中提到的 pilot 排除规则扩写成当前已经发布训练流水线。[METHOD](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/docs/METHOD.md)、[RESULTS](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/docs/RESULTS.md)

本轮直接解析清单，确认其评测矩阵为 706 rows：authored 144、WANLI 256、TypeSafe 102、Every 204。外部 source-selection 为 562 条；每个来源分别报告，不混成单一准确率。[评测矩阵](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/benchmarks/manifests/evaluation-matrix.jsonl)、[来源选择](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/benchmarks/manifests/source-selection.jsonl)

**authored144 不是独立人工金标。** 文件有 36 个 group，三个 family 各 48 rows，全部标为 test；provenance 表示自创合成、经模型复核、未经人工裁定。它可复用为一个公开测试子集，不能既拿来训练又沿用其测试成绩，也不能把标签可信度宣传成人类复核。[authored144.jsonl](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/benchmarks/data/authored144.jsonl)

作者发布的主要观察是 frozen direct 在其通用判断任务上优于同规模 reranker；TypeSafe 子集数字是与公开模型参考分布比较，**不是人工正确率，也不是 live Jev 对照**。仅覆盖可对齐的 102 rows/20 cases，排除 Score 与并列目标；不能外推成已达到 Jev 全面能力。[metric contract](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/benchmarks/manifests/metric-contract.json)

我们独立解析已发布 2,331 行预测，确认三个模式各 777 行，并重新计算出：

| 对 fresh 的比较 | argmax 翻转 | 最大概率绝对差 | 平均概率绝对差 |
|---|---:|---:|---:|
| serial prefix | 5/777 | 0.0933859 | 0.0078250 |
| parallel suffix | 6/777 | 0.0624188 | 0.0076972 |

这与发布 raw report 一致。**这证明提交记录之间一致，不证明共享实现已数值等价；本轮没有复跑模型。** 作者将其置于 BF16/内核差异背景下，但没有 FP32、固定 kernel 的消融足以把差异唯一归因为 BF16。尤其 0.06–0.09 的个别概率漂移，应保留为待调查事项。[原始预测](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/results/raw/shape777-direct.predictions.jsonl)、[原始报告](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/results/raw/shape777-direct.json)

同一报告中作者给出单 RTX 3090 下 fresh 333.1 秒、serial 72.3 秒、parallel 38.8 秒；这是 warm model 的该固定负载结果，不能除以 Jev 服务时延来得出快慢。我们未重测这些计时。

另独立核对了下载的四个 raw 文件与 `SHA256SUMS` 一致：compact-array、quality-comparison、shape777-direct 及其 predictions。仓库 `verify_published.py` 会比对许多摘要字段，但 direct 的 5/6 次翻转使用硬编码数目，并不在此 helper 中从 direct 预测重新计算；我们上面的独立计算补上了这个窄检查。helper 不能替代完整的指标重算和 GPU 重跑。[SHA256SUMS](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/results/raw/SHA256SUMS)、[verify_published.py](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/benchmarks/verify_published.py)

## 5. 许可与可复用模块

项目代码采用 MIT，保留其版权与许可文本后可复用；外部模型和数据不随 MIT 一并改许可。仓库列出第三方来源、revision 和哈希，排除没有重分发授权的原始 TypeSafe 数据。其 fetch 脚本提供四个公开 TypeSafe `*-cases.js` URL 和哈希，这让特定公开案例更可追溯；不因此推断整个官方 benchmark 已完全开源或数据可用于任意训练。[LICENSE](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/LICENSE)、[THIRD_PARTY](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/THIRD_PARTY.md)、[fetch_sources.py](https://github.com/TheoLeeCJ/openjev/blob/b4782a6c953f05c6255706d7a219f4e032af5b58/benchmarks/fetch_sources.py)

| 可复用项 | 应如何使用 |
|---|---|
| 输入校验、prompt hash、模型 revision 记录 | 作为所有基线的审计契约 |
| slot token/boundary 检查 | 直接用于冻结 label-logits 基线，避免分词假设 |
| prefix 一致性、suffix padding/position、cache 分支 | 用于保守共享推理原型；补 isolation/FP32/branch-order 检查 |
| allowed token mass | 所有 label-logits 模式统一保留，以解释强制归一化 |
| 分来源指标、扰动集、哈希清单 | 测试基准；保留原始标签来源和 test 用途 |
| shared prefix 的计时分解 | 区分前缀计算、复制、后缀前向与端到端成本 |

必须新增的核心：可训练判别函数与适当概率目标、可信独立结果及校准分区、超 16 候选策略、Score 隔离与后处理、真正跨 state 的 batching、训练共享梯度、候选集合交互消融和可复现的 kernel 等价性测试。浏览器 demo 不是本轮审计重点，不能把其量化浏览器模型成绩替代上述 4B CUDA 基线。

这项仓库证据会调整我们的起点：**先将通用冻结模型的直接选项 logits 列为强基线，再证明训练后 scalar scorer 的质量或效率收益。** 不应未经对照就假设 reranker 是最优底座，也不应把 frozen direct 的能力归功于尚未实施的 RLCD。
