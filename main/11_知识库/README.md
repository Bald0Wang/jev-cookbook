# 第十一章 · 知识库

> 教程负责带着动手，本章负责**随时查证**。教程里引用的每一个社区数字——JevBench 榜单、Rerank 对照、重跑漂移、Laya 三篇长文——原始出处都在这里。

## 01 这是什么

[Bald0Wang/jev-cookbook](https://github.com/Bald0Wang/jev-cookbook)（原私有库，现归档为 jev-cookbook-archive）的**全量快照**：21 个板块、500+ 文件。收录原则引自知识库自己的说明——**文档全收，代码只取能说明「状态 → 问题 → 概率 → 动作」这条决策链路的实现**；测试、脚手架、依赖锁、数据集、模型权重一律不收。来源与版本 commit 见 [`jev-cookbook/SOURCES.md`](jev-cookbook/SOURCES.md)。

## 02 板块地图

| 板块 | 内容 | 教程中的用途 |
|---|---|---|
| 01 官方文档中译 | 全站翻译源 | [翻译站](https://datawhalechina.github.io/jev-cookbook/)的内容基础 |
| 02 NanoJev | snake_game.py 模式源头 | 第 7 章四个游戏环境的共同范式 |
| 15 jevbench | v1.2 全部结果与分析 | 第 6 章 75.4/100%/0.65s/$0.04 等数字的出处 |
| 18 Jev 替代 Rerank 实验 | 80 条 SciFact 对照 | 第 4 章重排序篇 nDCG@10 +0.0778 的出处 |
| 04 fast-jev-compaction | Claude Code 压缩插件 | 第 1/4 章引用的生产用法 |
| 08 eve 决策模型研究 / 10 飞书研究报告 | 决策模型横向研究 | 选型判据 |
| 19–21 Laya 三篇公众号 | 架构/开源/HF 榜 | 第 10 章的背景阅读 |
| laya-model | 本地部署与 Jev 兼容接口示例 | 第 10 章实操参考 |
| 03/05/06/07/09/12–14/17 | trader、awesome 清单、Skill、ultrafast、SDK、公众号、飞书讲座 | 泛读与背景 |

## 03 使用方式

- **查证**：教程任何数字 → 本章搜出处；
- **泛读**：入口读物 [`jev-cookbook/README.md`](jev-cookbook/README.md)（"Jev 是什么"三分钟版 + 一条主线阅读路径）；
- **引用**：对外使用时注意各板块的原始许可（见 SOURCES.md）。

> 快照同步自上游私有仓库；更新方式：从上游重新导出覆盖本章目录。
