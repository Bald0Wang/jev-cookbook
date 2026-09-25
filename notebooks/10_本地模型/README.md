# 10 · 本地模型（Laya）

第十章收录 **Laya**——开源的非自回归类型化决策模型（Convai Innovations，Apache-2.0）：输入同样是 state + 类型化问题，一次前向并行回答 Choice/Score/Noul。换句话说，**这是"Jev 的同类"，而且能跑在你自己的机器上**。

## 本章内容

| 内容 | 位置 |
|---|---|
| 模型介绍、Jev 对比与本地调用（原项目总览文档） | [`模型介绍与对比.md`](模型介绍与对比.md) |
| RLCD 微调：原理与实验优化 | [`RLCD原理与实验优化.md`](RLCD原理与实验优化.md) |
| 中文数据集构造（ShareGPT-zh 38K 管线） | [`DATA_GENERATION.md`](DATA_GENERATION.md) · [`data_generation/`](data_generation/) · [`notebooks/zh_dataset_construction.ipynb`](notebooks/zh_dataset_construction.ipynb) |
| 微调实操与实验记录 | [`FINETUNING.md`](FINETUNING.md) · [`finetune_*.py`](.) · [`notebooks/full_v2_finetuning.ipynb`](notebooks/full_v2_finetuning.ipynb) · [`experiments/`](experiments/) |
| 本地推理服务与 Jev 兼容接口 | [`serve.py`](serve.py) · [`client.py`](client.py) |
| Laya vs Jev 基准（第六章的配套框架本体） | [`benchmark/`](benchmark/) |

> 模型权重约 2.2 GB 不随仓库分发，获取方式见 [`模型介绍与对比.md`](模型介绍与对比.md) 第 5 节；
> `data_generation/generated/` 的大体积生成数据被 gitignore，用脚本本地再生。

## 与教程的关系

- 第六章 [模型评测](../06_模型评测/) 的对比框架就来自本章的 `benchmark/`（231 道公开题，Laya-local vs Jev）；
- 第一章讲的"校准决策（RLCD）"，本章是亲手微调一个同类模型的完整实操；
- 第八章 jev_mem 用了 Laya 做过对照（见其 README）。
