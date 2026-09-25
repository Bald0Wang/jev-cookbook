# Jev-Mem 研究笔记本（System-One 控制的智能体记忆）

> **关于本目录 / About**: 本目录是对 [Jev-Mem](https://github.com/libingzheren/Jev-Mem)
> （UT Dallas，2026-09-21 开源，[arXiv:2609.23986](https://arxiv.org/abs/2609.23986)）的独立研究快照：
> 架构走读 + 四臂对照实验 + 长程缩放实验 + 真 LoCoMo 基准。笔记本内的输出全部为
> **2026-09-25 真实 API 实测结果**（System-One = 真 Jev `jev-latest`，System-Two = DeepSeek
> `deepseek-chat`，embedding = 硅基流动 Qwen3-Embedding-0.6B）；API key 不在仓库内。
> 文中提到的 `../Jev-Mem` 路径指本地克隆（MIT License，架构图引自其 docs/figures）。

| 文件 | 内容 |
|---|---|
| `jev_mem_walkthrough.ipynb` | 三平面架构讲解、写入/读取管线走读（7 组 Jev 类型化决策）、16 轮中文对话四臂实验（滑窗 / 全上下文 / 朴素 RAG / Jev-Mem） |
| `jev_mem_scaling.ipynb` | 长程缩放：同一组事实与题目拉到 48~384 轮，质量/延迟/token 缩放曲线；附真 LoCoMo 样本 0（419 轮）Jev-Mem vs 全上下文对照；§5 三组实验结论总览与选型判据 |
| `overall_structure.png` | Jev-Mem 论文架构图（引自上游仓库） |

核心数字（详见笔记本）：D Jev-Mem 对朴素 RAG 的增益集中在时间/多跳题（决策面与 embedding 质量正交）；
全上下文每题 token 随轮数线性涨（384 轮时 81 倍差），D 恒定 ~120 tok；真 LoCoMo 上全上下文 0.60 对 D 0.98。
