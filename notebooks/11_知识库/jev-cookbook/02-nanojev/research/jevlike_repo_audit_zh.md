# Jevlike 源码审查

核验：2026-09-17。仓库：[vinnylarouge/jevlike](https://github.com/vinnylarouge/jevlike)。固定提交 `94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452`。只读下载至临时目录，未安装依赖、运行仓库代码或加载其 checkpoint。

## 结论

它是有真实训练代码的变长候选评分起点，可以借鉴候选 mask、共享上下文读出和数据构建器；不能视作已经完成 Jev 通用能力或 RLCD 的复现。主文本训练只优化硬标签交叉熵。游戏分支的 PPO 以环境回报为目标，不能据此称为校准概率训练。

## 实际实现

| 模块 | 源码观察 | 对我们的价值与缺口 |
|---|---|---|
| `model.py:AttentionHead` | 候选向量作为 query，对 context token 的 key/value 做 cross-attention，再由共享点积产生 K 个分数 | 真正按候选并行、context 读出可共享；候选之间没有交互，仍有独立打分的集合限制 |
| `FrozenTransformerScorer` | `AutoModel` 完全冻结且 `no_grad`；context 编码一次，全部 options 另做一次 batch 编码并均值池化 | 证明直接 LLM 初始化有现成实现；只训练浅 head 的语义适配能力需要测，不能替代本项目的 backbone 后训练 |
| `TinyScorer` | 从零学字节 embedding，候选为字节均值；context 加位置 embedding | 适合检查张量与数据流程，不应期待开放语义能力 |
| `train.py` | AdamW、硬标签 CE、验证 NLL 选 checkpoint | 可借鉴训练骨架；没有教师完整分布、舍入处理、任务混合或独立校准阶段 |
| `data.py` | 每条是 context/options/单个 label；没有单独的 question 和题型字段 | question 可以被写入 context，但不能自动保证同 state 多题隔离与复用；需换成本项目 schema |
| `eval.py` | top1/top3、十箱 ECE、打乱上下文对照 | 上下文对照值得采用；需要补 NLL/Brier、分任务指标、独立校准和实际工作流测试 |

一手代码：[模型](https://github.com/vinnylarouge/jevlike/blob/94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452/jevlike/model.py)、[训练](https://github.com/vinnylarouge/jevlike/blob/94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452/jevlike/train.py)、[评测](https://github.com/vinnylarouge/jevlike/blob/94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452/jevlike/eval.py)。

“一遍评分”是计算范式描述：HF 分支实际分别调用 backbone 编码 context 和 options，然后调用 head。没有答案 token 解码循环，但不是整个系统只调用了一次 backbone。

## 数据究竟是什么

默认 synthetic 是颜色与动物组成的徽章匹配：context 直接写出目标，2–8 个选项包含它。它检查文本匹配与候选归一化，不证明新问题、新规则或概率校准。

Wikispeedia 构建器选取完成路径中的一次点击，以终点文章分组切分 train/validation/test；候选为当前页面链接，超过上限时抽取子集并强制包含实际点击。这是可用的实际动作数据，但标签是人选择过的点击，不是唯一最优动作，也不是无偏的全候选行为概率。候选采样改变了条件空间，不能从缩小菜单的结果直接推断原菜单表现。[数据构建器](https://github.com/vinnylarouge/jevlike/blob/94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452/jevlike/data.py)

## 复用前应修正的问题

以下是静态代码推断，未在本机运行 torch 复现：

1. **CPU best checkpoint 可能不是快照。** `trainable_state` 使用 `parameter.detach().cpu()`，在参数本来就在 CPU 时没有 clone，返回 tensor 可共享存储；后续更新可能覆盖所记录的最优参数。应显式 `detach().cpu().clone()`。
2. **ECE 排除了精确 confidence=1。** 每箱上界都用严格小于，最后一箱也如此。应覆盖端点，并同时提供 NLL/Brier，避免高置信错答漏计。
3. **合成数据跨进程顺序未固定。** 先构造字符串 set，再转 list 后 shuffle；只固定 Random seed 不保证不同 Python hash seed 下候选顺序相同。应先排序再 shuffle，并记录生成器版本。
4. **没有独立 question 契约。** 需要将题意、state、候选、题型分开保存，才能做问题变化与题间隔离测试。
5. **不能照搬 checkpoint 加载。** 仓库使用 `torch.load(..., weights_only=False)`。本轮没有加载这些外部文件；若采用其模型接口，我们保存自己的 safetensors 权重与 JSON 配置。

前两项对应 [model.py](https://github.com/vinnylarouge/jevlike/blob/94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452/jevlike/model.py) 与 [eval.py](https://github.com/vinnylarouge/jevlike/blob/94f5fd1b0b11d52bbdfdf4e0ee6aa96b568f8452/jevlike/eval.py)；第三项对应数据构建器的 `synthetic_example`。

## 采用决定

采用其思路作为低成本对照：冻结 LLM 编码器＋候选 cross-attention head，测试与可训练 LLM 路线的语义/吞吐差距。借鉴变长候选 mask、打乱 context 的负对照，以及来源分组的数据构建思路。若复制代码，保留 MIT 署名；外部模型与数据仍分别记录来源。

不沿用原字节匹配数据作为主训练分布，不沿用其 headline 加速数字作为我们的验收目标，不将游戏回报训练命名为 RLCD。没有对这份仓库写改动或对外提交消息。
