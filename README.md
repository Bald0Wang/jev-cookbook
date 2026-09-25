# Jev Cookbook — Jev 中文教程与知识库

[![License](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans)

> *机器原生智能：让软件直接消费模型的判断，而不是解析它生成的文本。*

**在线阅读：https://bald0wang.github.io/jev-cookbook/** ｜ 教程运行目录：[`main/`](main/README.md)

## 项目简介

Jev Cookbook 是一个关于 **Jev**——TypeSafe AI 的旗舰 System One 模型——的中文开源教程与知识体系。向 Jev 发送**状态（state）**和**类型化问题**（Choice / Score / Noul 三种原语），它返回带**概率与置信度**的结构化答案，代码直接消费：不做文本生成，无需解析。

本项目把这条「状态 → 问题 → 概率 → 动作」的决策链路，做成**十一章可运行的中文教程**：从三原语入门，到官方 18 篇实战配方、语音智能家居实战、模型评测方法、Agent 集成示范，再到用 RLCD 微调一个开源同类模型（Laya），并附 500+ 文件的资料库快照。全部实验使用中文场景与中文提示词，配有真实 API 实测输出。

## 项目意义

大模型应用里最常见也最脆弱的一环，是把模型生成的文本**解析**回程序能用的决策——慢、贵、还会坏。System One 模型（Jev 与开源的 Laya）代表另一条路线：模型原生输出类型化决策与校准概率，分支、排序、路由直接交给代码。

这条路线的中文资料此前几乎是空白。本项目的每一次实验都在回答同一组问题：**该不该用判断模型？怎么问出好问题？概率可信到什么程度？和传统大模型比到底差多少？**——并且全部结论有可复现的实验支撑（含 231 题公开基准的四维对比）。

## 项目受众

具备基础 Python 能力、想入门「AI 对软件」开发范式的开发者。不需要机器学习背景；不配置 API Key 也能用离线示例学完全部代码路径。

## 项目亮点

- **在线优先，离线兜底**：检测到 `TYPESAFE_API_KEY` 即调真实模型，无 Key 自动降级离线示例，输出始终标注来源、不冒充实测；
- **真实数据教学**：教程里的概率、延迟、token 与成本（如 JevBench 榜单、Rerank 对照、重跑漂移 1.2%）全部来自可复核的实测，人工演示数据明确标注；
- **一套主线多种形态**：同一套原语贯穿教程（11 章）、可玩应用（游戏/3D 智能家居）、Agent 集成（Pi/DSH）与本地微调（Laya）；
- **诚实的评测纪律**：第六章基准无重试、无回退、不修补答案、预算记账，示范"怎么公平地评测一个判断模型"。

## 学习指南

### 前置要求

- Python ≥ 3.10、会用 Jupyter Notebook（`main/setup_env.sh` 一键建环境）；
- 一个 `TYPESAFE_API_KEY`（[console.typesafe.ai](https://console.typesafe.ai/keys) 免费注册可领）——**可选**，没有也能离线学。

### 必修（建议按序）

1. **第 1 章 认识 Jev**（`main/01_认识Jev/`）：合并官方 Introduction / Quickstart / Use Case Map / AI Primer——一册读懂 Jev 是什么、怎么调、用在哪、概率为什么可信；
2. **第 2 章 核心概念**（`main/02_核心概念/`，5 册）：System One 机制与 LLM 对比、状态、原语、置信度、如何构建；
3. **第 3 章 架构模式**（`main/03_架构模式/`）：推测性扇出、置信度门控、复合评分、意图路由。

### 实践篇

- **第 4 章 实战指南**（18 册）：官方 Cookbook 每篇一本，篇尾「知识补充」附关联章节、社区实测与工程坑；
- **第 5 章 智能家居实验**：Notebook 内单次投机调用实测 + 内嵌 3D 应用（语音输入、成本统计）；
- **第 9 章 Agent 集成**：Jev 嵌入真实 Agent——Pi 工具调用前的 gate 判断、DSH 决策协作复盘。

### 进阶与拓展

- **第 6 章 模型评测**：Laya vs Jev，231 道公开题四维对比与评测纪律（来自社区 PR #6）；
- **第 10 章 本地模型**：Laya（Apache-2.0 开源同类）RLCD 微调全流程——数据构造、训练、本地 Jev 兼容服务；
- **第 7 章实战应用**（九个可运行项目）、**第 8 章前沿研究**（Jev-Mem / JevHarness）、**第 11 章知识库**（教程引用数字的原始出处）。

### 目录结构

```text
main/        十一章教程（generators/ 生成器、tests/ 契约测试、setup_env.sh 环境）
content/     官方文档中文翻译（Markdown 源）
dist/        翻译站构建产物（在线阅读地址即由此发布）
apps/        DSH × Jev 配套工程（第 9 章实体）
```

> 官方文档翻译部分为**非官方**社区翻译，仅供学习参考；内容与商标版权归原作者 TypeSafe AI 所有，以[英文原版](https://docs.typesafe.ai)为准。

## 致谢

- **[Micheal024](https://github.com/Micheal024)** — 第 6 章评测框架与 Laya vs Jev 基准（[PR #6](https://github.com/Bald0Wang/jev-cookbook/pull/6)）
- **[lzdFeiFei](https://github.com/lzdFeiFei)** — 第 7 章收录的 [jev-games](https://github.com/lzdFeiFei/jev-games) 小游戏合集（原仓库未附 LICENSE，版权归原作者，仅作学习收录）
- [Bald0Wang/jev-playground](https://github.com/Bald0Wang/jev-playground) — 第 7 章自家应用的原仓库
- [TypeSafe AI](https://typesafe.ai) — 官方文档与 Playground

欢迎通过 [Issues](https://github.com/Bald0Wang/jev-cookbook/issues) 反馈勘误与建议，或直接提 Pull Request（工作流见 [AGENT.md](AGENT.md)）。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Bald0Wang/jev-cookbook&type=Date)](https://star-history.com/#Bald0Wang/jev-cookbook&Date)

## 关注我们

<div align="left">
<a href="https://github.com/datawhalechina">
<img src="https://img.shields.io/badge/Datawhale-开源组织-blue" alt="Datawhale">
</a>
</div>

**Datawhale** 是一个专注于数据科学与 AI 领域的开源组织，汇集了众多领域院校和知名企业的优秀学习者，聚合了一群有开源精神和探索精神的团队成员。本项目将以 Datawhale 开源课程标准持续维护，欢迎加入一起学习成长。

## LICENSE

<a rel="license" href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans">
<img alt="知识共享许可协议" src="https://img.shields.io/badge/CC-BY--NC--SA%204.0-lightgrey" />
</a>

本仓库原创内容采用 [署名-非商业性使用-相同方式共享 4.0 国际许可协议](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans)；收录的第三方项目（如 jev-games、JevBench 题集、知识库快照）版权归各自作者，按其原许可使用。
