# 第十章 · 本地模型（Laya）

> Jev 是闭源 API。如果你想要**跑在自己显卡上**的同类模型——本章的 Laya 就是：开源、Apache-2.0、单张消费级显卡延迟 **32.8ms**（比 Jev 远程接口还快数倍），上线 3 天 **8820 Star**。

## 01 Laya 是什么

Convai Innovations 发布的非自回归类型化决策模型：输入同样是 state + 类型化问题，一次前向并行回答 Choice/Score/Noul。输出头直接给候选项打分——候选项前放专属 `[MASK]` 标记，在标记位读分、同题候选做 softmax。**加一套业务标签只需在请求里定义 schema，不用为每个标签新建分类头或重训。**

三个 checkpoint 怎么选（详见[`模型介绍与对比.md`](模型介绍与对比.md)）：

| Checkpoint | 参数 | 上下文 | 用途 |
|---|---|---|---|
| `models/` | 4.21 亿，ModernBERT-large | 512 | 英语 |
| `models/multilingual/` | 3.22 亿，mmBERT | 1,024（骨干可到 8,192） | **中文/多语言，默认推荐** |
| `models/typed-decisions/` | 4.21 亿 | 1,024 | 特定工作流微调版 |

一个重要提醒：`typed-decisions` 不是"Pro 版"——它在通用 typed-decisions 零样本集上（0.362/0.342）**低于多数类基线 0.461**。模型卡的微调分不能当开箱即用能力，务必按自己任务实测。

## 02 本章实操内容

| 内容 | 说明 |
|---|---|
| [`模型介绍与对比.md`](模型介绍与对比.md) | 与 Jev 的共同点和差异、checkpoint 选型、权重获取（约 2.2GB 不随仓库分发） |
| [`RLCD原理与实验优化.md`](RLCD原理与实验优化.md) | 用 RLCD 微调出校准决策模型的原理与实验迭代 |
| [`data_generation/`](data_generation/) + `zh_dataset_construction.ipynb` | 中文数据集构造：ShareGPT-zh 38K 生成管线 |
| `finetune_*.py` + `full_v2_finetuning.ipynb` + `experiments/` | 微调实操与实验记录（官方配方复现 + full-v2，含诊断报告） |
| `serve.py` / `client.py` | 本地推理服务与 Jev 兼容接口——微调完直接挂进第 6 章的评测框架 |

## 03 核心价值

- **从使用者到训练者**：第一章讲 RLCD 是 Jev 的训练路线，本章让你亲手走一遍——数据怎么造、实验怎么对比、失败怎么诊断；
- **闭环验收**：微调出的模型经 `serve.py` 起本地服务，直接接第六章 `benchmark/` 跑同一套 231 题，与 Jev 同表对比；
- **成本自由**：判断任务量大时（第 4 章批量场景），本地模型把每千次决策成本压到近乎为零。
