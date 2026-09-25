# 训练后结构检查与 GPU 延迟

执行时间：2026-09-17 13:38 UTC。代码：`scripts/check_trained_invariance.py`；原始结果：`research/trained_invariance_timing.json`。

## 对象与范围

独立脚本复用现有 `train_toy_decisions.DecisionModel` 和 `load_examples`，从已完成的 `runs/base_teacher` 本地加载 tokenizer、backbone config 和 `best.safetensors`，不重新下载基础模型，不执行训练更新。该 checkpoint 在第 36 步按 dev teacher CE 选出，SHA-256 为 `cd6384b284a4c7d376fbe81afdcf46ed0be9c6c943cda48900514c65f578880f`。

在 A100-SXM4-80GB 的物理 GPU 7 上运行，PyTorch `2.14.0+cu130`、Transformers `5.17.0`，FP32 参数存储、BF16 autocast、SDPA，与训练器的推理精度一致。使用固定测试集文件顺序的前 8 个 state，共 24 个问题、68 条候选 token 路径、76 个输出概率；Boolean 仅一条语义路径输出两个概率。完整输入路径最长 85 tokens，这组数据均来自支持工单场景，不能代表所有任务与长上下文。

此训练原型使用独立的完整候选路径批处理，Choice 使用集合 attention head；没有共享树、KV prefix 复用或逐 token 生成。此前 tiny Qwen 的 tree 等价检查是另一项独立实验。

## 结构检查结果

BF16 的预设工程诊断容差为 raw logit 绝对差 `0.02`、概率绝对差 `0.005`，并保留全部实测值。这不是理论误差界限，也不保证逐位不变。

| 对照 | 最大 raw logit 差 | 最大概率差 | 结果 |
|---|---:|---:|---|
| 每题单独运行 vs 8-state batch | 0.26953125 | 0.01507676 | **超出诊断容差** |
| 每个 state 单独运行 vs 8-state batch | 0.00097656 | 0.00000280 | 容差内 |
| 候选随机重排并按候选 ID 还原 | 0 | 0.000000119 | 容差内 |
| state 与 question 同时逆序 | 0 | 0 | 容差内 |
| 改动另一 state 的三个 token，观察未改动 state | 0 | 0 | 容差内 |
| Score 改动另一级语义，观察未改动级别 | 0 | 可变化 | 原始分数独立 |

前五项对照均没有首选答案变化；Boolean 保持固定的 `[false,true]` 输出约定，不进行候选重排。无关 state 的扰动保持 token 长度不变，并对该 state 的全部问题/候选一致修改；被改动 state 自身概率最大变化约 `0.05553`，说明扰动实际生效。

Score 检查将 level 1 的候选文本替换成 level 0 的文本，保持 level 0 的语义路径不变。8 道 Score 题的 level 0 原始 logit 均未变化；其 softmax 概率可因另一级分数改变而变化，实测最大变化约 `0.49910`。这符合当前结构要求；不能要求归一化后的概率也独立。Choice 不要求候选间分数独立，因为它有显式集合交互。

## 单题 BF16 差异的追加诊断

发现单题对照超容差后，使用同一 checkpoint 关闭 autocast，追加了 FP32 单题与批处理比较：

- 最大 raw logit 差：`6.29425e-5`。
- 最大概率差：`4.45545e-6`。
- 24 道题没有首选答案变化。

FP32 差异显著收敛，结合等形状的重排和无关输入扰动结果，支持低精度或批次形状相关数值敏感性的解释。尚未逐算子定位具体 kernel，因此不把其完整根因写成已证实结论。BF16 对 FP32 的最大概率差，在混合批处理中为 `0.01369`，单题运行中为 `0.02873`。

JSON 中的综合 `all_invariance_checks_within_diagnostic_tolerance` **保留为 false**，没有放宽阈值把首项改成通过。当前结果支持结构隔离与候选置换设计，但还不能承诺 BF16 在任意 batch 形状下给出相同概率。对概率稳定性有要求的使用场景，需固定服务精度/批处理策略并进一步验证。

## 固定短输入的延迟

各批次分别预热 2 次、测量 20 次，使用 CUDA 同步后的壁钟时间；包含模型内部 tensor 组装和 host-to-device copy，排除 tokenize、输出传回 CPU、HTTP、排队。每个批次使用同一固定数据前缀，百分位数按 `(n-1)*fraction` 线性插值。

| 同批 state 数 | 问题数 | 候选路径数 | p50 | p95 | 问题/秒（按 p50） | GPU 峰值 allocated |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 7 | 26.89 ms | 27.58 ms | 111.6 | 2.424 GB |
| 4 | 12 | 34 | 45.89 ms | 45.92 ms | 261.5 | 2.546 GB |
| 8 | 24 | 68 | 84.72 ms | 85.07 ms | 283.3 | 2.695 GB |

显存单位为十进制 GB，allocated 含模型参数；相对于预热前模型常驻 allocated 的增量分别约 30.3、151.7、301.1 MB。完整 JSON 同时记录每次延迟和 reserved memory。以上是固定短输入上的本地 GPU 微基准，20 次采样不能用作线上尾延迟保证，QPS 指问题数而非 HTTP 请求数。它不是 Jev API 的同条件速度比较，也不是共享树优化收益测量。

本环境仍使用已验证的进程内 `torch._native.triton_utils.deregister_op_overrides()`，绕过缺少 `Python.h` 的可选 eager Triton 覆盖；没有修改训练器或系统依赖。脚本、执行 JSON 的 SHA-256 已核对一致。
