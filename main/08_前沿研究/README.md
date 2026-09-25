# 08 · 前沿研究（Research Snapshots）

第八章收录两个**研究型快照**——不是教程，而是对社区前沿项目独立走读、复现与评估的完整记录。它们的共同点：都在回答"System One 判断模型在真实系统里到底怎么用、值不值"这个问题，且结论全部来自可复核的实测。

## [jev_mem/](jev_mem/) · Jev-Mem：System-One 控制的智能体记忆

> 上游：[libingzheren/Jev-Mem](https://github.com/libingzheren/Jev-Mem)（UT Dallas，[arXiv:2609.23986](https://arxiv.org/abs/2609.23986)，MIT）。
> 本目录是独立研究快照，笔记本输出为 **2026-09-25 真实 API 实测**（System-One = 真 Jev，System-Two = DeepSeek，embedding = Qwen3-Embedding）。

| 文件 | 内容 |
|---|---|
| [`jev_mem_walkthrough.ipynb`](jev_mem/jev_mem_walkthrough.ipynb) | 三平面架构讲解、写入/读取管线走读（**7 组 Jev 类型化决策**）、16 轮中文对话四臂实验（滑窗 / 全上下文 / 朴素 RAG / Jev-Mem） |
| [`jev_mem_scaling.ipynb`](jev_mem/jev_mem_scaling.ipynb) | 长程缩放：48~384 轮的质量/延迟/token 曲线；真 LoCoMo 样本（419 轮）对照；三组实验结论与选型判据 |

**核心数字**：Jev-Mem 对朴素 RAG 的增益集中在时间/多跳题；全上下文每题 token 随轮数线性涨（384 轮时相差 81 倍），Jev-Mem 恒定 ~120 tok；真 LoCoMo 上全上下文 0.60 对 Jev-Mem 0.98。

**与教程的关系**：写入/读取管线里的每一个决策点就是第一章的三原语（Choice 定类型、Score 定留存、Noul 定相关性）——这是"原子判断 + 代码组合"在记忆系统里的完整落地。

## [jev_harness/](jev_harness/) · JevHarness：项目分析与评估

> 上游：[TianyuCodings/JevHarness](https://github.com/TianyuCodings/JevHarness)（NanoJev 作者的新项目，社区贡献文档）。
> 文档：[`JevHarness 项目分析与评估.md`](jev_harness/JevHarness%20项目分析与评估.md)。

核心主张：**把"开发策略"和"执行策略"分开**——开发阶段用强编码 LLM 写出决策 Harness；在线阶段执行显式的流程、特征与结构化判断，不再让强模型参与每一步。若 Harness 用 Jev 节点，在线仍调 Jev 服务——它降低的是逐步调用强 LLM 的需求，而非完全移除推理服务。

**与教程的关系**：这正是第七章四个游戏环境（NanoJev `snake_game.py` 模式）的工程化延伸——`doudizhu/`、`sudoku/` 的"确定性引擎 + 类型化判断"就是最小的 Harness。

## 阅读建议

先读第一章（三原语与原子判断）→ 第六章（评测方法论）→ 再进本章：jev_mem 看"判断模型怎么管记忆"，jev_harness 看"判断模型怎么管控制流"。两份快照互为镜像：一个向外扩（长程记忆），一个向内收（确定性执行）。
