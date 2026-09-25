# 真实 PyTorch Qwen3 共享前缀树数值检查

执行时间：2026-09-17 13:28 UTC。脚本：`scripts/check_qwen_tree.py`；完整结果：`research/qwen_tree_check.json`。结果 JSON 记录脚本 SHA-256、随机种子、完整模型配置、固定 token 路径、各参数梯度误差和预先设置的 FP32 验收阈值。

## 检查对象与结论

在 `capyubara-0` 的物理 GPU 7（NVIDIA A100-SXM4-80GB）上，使用 PyTorch `2.14.0+cu130`、Transformers `5.17.0` 的真实 `Qwen3Model` 模块，运行随机初始化的两层模型：hidden size 64、4 个 query heads、2 个 KV heads、head dimension 16、MLP dimension 128、词表 128。模型使用默认固定 RoPE、eager attention、dropout=0、`use_cache=False`，在叶子隐藏状态后接一个共享 scalar head。共检查 25 个参数张量、82,368 个参数元素的反向梯度。

该配置下，**共享前缀树和逐候选独立路径在 FP32 数值容差内通过了前向、loss、全部参数梯度一致性检查**。这是可执行实现的数值证据，支持继续实现此结构。

固定输入包含 2 个 state、4 个 question、9 个 candidate，叶子路径长度不同，每题包含 2 或 3 个候选。flat 版本批处理每条完整 `S+Q+C+readout` 路径；tree 版本将两棵 state 树打包成一个序列，显式构造 `[1,1,N,N]` 的 `0/-inf` additive mask，并让每个 token 的 position id 等于它在所属完整路径上的位置。两个版本都保留整个反向图，所有题目交叉熵按题取均值，不对共享 state 的梯度额外除以分支数。

## 实测数值

| 检查项 | FP32 | BF16 |
|---|---:|---:|
| 叶子隐藏状态最大绝对差 | 4.76837e-7 | 0 |
| scalar logits 最大绝对差 | 2.16067e-7 | 0 |
| flat/tree loss 绝对差 | 0 | 0 |
| 全部参数梯度最大绝对差 | 6.25849e-7 | 9.765625e-3 |
| 全部参数梯度相对 L2 差 | 4.87373e-7 | 6.23205e-3 |
| state、question、candidate 重排后最大隐藏状态差 | 4.76837e-7 | 0 |
| 改变另一 state 后，当前 state 的最大隐藏状态差 | 0 | 0 |
| 改变一条 candidate 后，其他候选叶子的最大隐藏状态差 | 0 | 0 |

BF16 测量使用模型参数和运算直接转换到 BF16，并非 FP32 master weights 的混合精度训练。此次 BF16 前向相同，但反向存在约 0.623% 的全局相对 L2 差；因此结果文件只将 BF16 标为已测量，不宣称逐位或 FP32 级别的梯度等价。较低精度中的累加顺序、共享计算与重复计算会影响数值，后续正式训练应单独观察。

负对照确保检查能够抓住关键实现错误：

- 错把整片 packed forest 当普通连续 causal 序列，FP32 最大隐藏状态差为 **1.99684**。
- 错用 packed 全局列号作为 position ids，FP32 最大隐藏状态差为 **0.687860**。
- 改变第二个 state 的输入后，该 state 自身叶子最大变化 **1.74717**，而第一 state 为 0，说明隔离测试的扰动实际生效。

独立路径实际 token 数为 66，tree 为 38；此数字仅描述输入复用。当前实现构造 dense mask，不是块稀疏执行，**本检查没有测量速度、显存收益或吞吐量**。

## 当前环境的兼容性处理

最初运行在 RoPE 的批量矩阵乘处失败。此安装版本的 PyTorch 自动将部分 eager 运算分派到可选 native Triton override，而该环境的 Python 3.14 缺少 `Python.h`，导致 Triton driver 编译失败。

执行前在本进程内调用下面的现有函数后，FP32 与 BF16 的完整前向、反向均成功；没有安装或修改系统依赖，也没有修改 torch 包文件：

```python
from torch._native import triton_utils
triton_utils.deregister_op_overrides()
```

这是所测 PyTorch 2.14 的内部 API，功能是撤销可选 native Triton 运算覆盖，恢复普通 ATen 路径。脚本通过显式 `--disable-native-triton` 开关使用，并在 JSON 环境字段记录；不应把它当成跨版本稳定接口，或认为它能够禁用显式 FlexAttention/torch.compile 对 Triton 的依赖。

复现命令（只可见授权的物理 GPU 7）：

```bash
CUDA_VISIBLE_DEVICES=7 /home/rwang/openjev_codex_20260917/.venv/bin/python \
  /home/rwang/openjev_codex_20260917/check_qwen_tree.py \
  --disable-native-triton \
  --output /home/rwang/openjev_codex_20260917/qwen_tree_check.json
```

## 结论的边界

此次没有加载预训练权重，没有执行 optimizer update，没有验证完整 Qwen3-0.6B/4B 的任务质量、LoRA、SDPA、FlashAttention、FlexAttention、KV cache 分叉或大规模训练效率。它验证的是固定短输入、随机 tiny Qwen3、eager dense mask 这组明确条件下的结构与反向传播实现。没有任何结果用于推断 Jev 的真实内部架构。
