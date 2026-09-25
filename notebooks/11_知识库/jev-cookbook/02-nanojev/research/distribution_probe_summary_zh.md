# Jev 条件概率分布探针

已发出 40/40 次独立评估，成功 40 次，失败 0 次，未决 0 次。已知供应商费用 $0.004269636；未知费用预留 $0。

这是自有合成问题的有限诊断，不是扩充训练集。参考值来自题目明示的条件概率规则，没有抽取实际 outcome；因此这里报告分布对齐差异，不把它叫作实际校准误差。

每个 K 包含明确唯一答案、未揭示均匀抽签、两个标签各半、明示非均匀权重四类，每类各用原序与逆序。每次请求仅一个 state 与一道 Choice。

| K | 情形 | 顺序 | 原生和 | 零项数 | 原生最大项 | 原生熵(nats) | 最近邻区间可行 | 参考落区间 |
|---|---|---|---:|---:|---:|---:|---|---|
| 2 | explicit_unique | original | 1 | 1 | 1 | 0 | true | true |
| 2 | explicit_unique | reverse | 1 | 1 | 1 | 0 | true | true |
| 2 | unrevealed_uniform | reverse | 1 | 0 | 0.96 | 0.1679441 | true | false |
| 2 | unrevealed_uniform | original | 1 | 0 | 0.95 | 0.1985152 | true | false |
| 2 | two_support_half | reverse | 1 | 0 | 0.97 | 0.1347422 | true | false |
| 2 | two_support_half | original | 1 | 0 | 0.96 | 0.1679441 | true | false |
| 2 | explicit_weighted | original | 1 | 1 | 1 | 0 | true | false |
| 2 | explicit_weighted | reverse | 1 | 0 | 0.99 | 0.05600153 | true | false |
| 5 | explicit_unique | original | 1 | 4 | 1 | 0 | true | true |
| 5 | unrevealed_uniform | original | 1 | 0 | 0.92 | 0.37581 | true | false |
| 5 | explicit_unique | reverse | 1 | 4 | 1 | 0 | true | true |
| 5 | unrevealed_uniform | reverse | 1 | 0 | 0.94 | 0.3015147 | true | false |
| 5 | two_support_half | original | 1 | 3 | 0.95 | 0.1985152 | true | false |
| 5 | two_support_half | reverse | 1 | 3 | 0.99 | 0.05600153 | true | false |
| 5 | explicit_weighted | original | 1 | 4 | 1 | 0 | true | false |
| 5 | explicit_weighted | reverse | 1 | 4 | 1 | 0 | true | false |
| 20 | explicit_unique | original | 1 | 19 | 1 | 0 | true | true |
| 20 | explicit_unique | reverse | 1 | 19 | 1 | 0 | true | true |
| 20 | unrevealed_uniform | reverse | 0.99 | 15 | 0.92 | — | true | false |
| 20 | unrevealed_uniform | original | 1 | 14 | 0.9 | 0.4755618 | true | false |
| 20 | two_support_half | original | 1 | 18 | 0.93 | 0.2536389 | true | false |
| 20 | two_support_half | reverse | 1 | 18 | 0.94 | 0.2269675 | true | false |
| 20 | explicit_weighted | original | 1 | 19 | 1 | 0 | true | false |
| 20 | explicit_weighted | reverse | 1 | 17 | 0.98 | 0.1119021 | true | false |
| 64 | explicit_unique | original | 1 | 63 | 1 | 0 | true | true |
| 64 | explicit_unique | reverse | 1 | 63 | 1 | 0 | true | true |
| 64 | unrevealed_uniform | reverse | 0.99 | 60 | 0.92 | — | true | false |
| 64 | unrevealed_uniform | original | 0.99 | 57 | 0.87 | — | true | false |
| 64 | two_support_half | original | 1 | 62 | 0.93 | 0.2536389 | true | false |
| 64 | two_support_half | reverse | 1 | 62 | 0.94 | 0.2269675 | true | false |
| 64 | explicit_weighted | original | 1 | 63 | 1 | 0 | true | false |
| 64 | explicit_weighted | reverse | 1 | 63 | 1 | 0 | true | false |
| 255 | explicit_unique | original | 1 | 254 | 1 | 0 | true | true |
| 255 | explicit_unique | reverse | 1 | 254 | 1 | 0 | true | true |
| 255 | unrevealed_uniform | original | 0.99 | 235 | 0.75 | — | true | false |
| 255 | unrevealed_uniform | reverse | 1 | 242 | 0.84 | 0.8139694 | true | false |
| 255 | two_support_half | original | 1 | 251 | 0.89 | 0.4125336 | true | false |
| 255 | two_support_half | reverse | 1 | 251 | 0.86 | 0.4762427 | true | false |
| 255 | explicit_weighted | original | 1 | 251 | 0.97 | 0.1677005 | true | false |
| 255 | explicit_weighted | reverse | 1 | 253 | 0.98 | 0.09803911 | true | false |

全零时不定义 argmax 或概率最大值，非单位和时不定义原生分布熵。完整 argmax（含并列）、每 K 汇总、参考逐项差异、另标的 proxy-normalized 熵与差异，见同名 JSON；原始值和费用保存在私有 JSONL。

| K | 情形 | 按候选 ID 还原后的原生最大逐项差 | 两个最大值之差 | proxy-normalized 最大逐项差 |
|---|---|---:|---:|---:|
| 2 | explicit_unique | 0 | 0 | 0 |
| 2 | unrevealed_uniform | 0.01 | 0.01 | 0.01 |
| 2 | two_support_half | 0.01 | 0.01 | 0.01 |
| 2 | explicit_weighted | 0.01 | 0.01 | 0.01 |
| 5 | explicit_unique | 0 | 0 | 0 |
| 5 | unrevealed_uniform | 0.02 | 0.02 | 0.02 |
| 5 | two_support_half | 0.04 | 0.04 | 0.04 |
| 5 | explicit_weighted | 0 | 0 | 0 |
| 20 | explicit_unique | 0 | 0 | 0 |
| 20 | unrevealed_uniform | 0.02 | 0.02 | 0.02929293 |
| 20 | two_support_half | 0.01 | 0.01 | 0.01 |
| 20 | explicit_weighted | 0.02 | 0.02 | 0.02 |
| 64 | explicit_unique | 0 | 0 | 0 |
| 64 | unrevealed_uniform | 0.05 | 0.05 | 0.05050505 |
| 64 | two_support_half | 0.01 | 0.01 | 0.01 |
| 64 | explicit_weighted | 0 | 0 | 0 |
| 255 | explicit_unique | 0 | 0 | 0 |
| 255 | unrevealed_uniform | 0.09 | 0.09 | 0.08242424 |
| 255 | two_support_half | 0.03 | 0.03 | 0.03 |
| 255 | explicit_weighted | 0.02 | 0.01 | 0.02 |

- reference_distribution 是题目定义的条件分布；本次没有抽样观测标签，分布差异不称为实际校准误差。
- 每种情形每个顺序只有一次请求，顺序差异可能混合服务随机性；不能据此单独认定候选顺序导致差异。
- 原生概率未经归一化；另列 proxy-normalized 仅用于诊断，全零不补均匀分布。
- 只有 probabilityDecimals 时，最近邻舍入及闭区间是诊断假设；没有确认供应商舍入模式或边界取舍。
- 40 个合成条件概率探针不能证明广泛能力或实证校准，也不能还原 Jev 内部 RLCD 算法。
- 预算是客户端估算与并发预留守卫，不是供应商单请求强制上限；未知失败费用保留 reserve。
