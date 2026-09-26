# 第七章 · 实战应用合集

> 前六章教你写判断代码，本章给你看**别人用同一套原语做出的完整成品**——两个来源、九个可运行项目，每个都能独立跑起来。

## 01 为什么值得跑别人的项目

读教程和读真实代码的差距，在于**工程细节的密度**：怎么把 judge 嵌进游戏循环、观战页面怎么实时渲染决策、上游依赖坏了怎么定位。这些在教程里只能点到，在项目里全是现成答案。本章九个项目全部 vendored 进 `app/`，克隆仓库即可运行，无需切到上游。

## 02 九个项目

| 项目 | 一句话 | 与教程的连接 |
|---|---|---|
| [`app/jev-games/games/gridloop/`](app/jev-games/games/gridloop/) | Jev 贪吃蛇（作者 [lzdFeiFei](https://github.com/lzdFeiFei)） | 每一步方向选择是一次 Choice，带 React 统一入口做双模型对比 |
| [`app/jev-games/games/minesweeper/`](app/jev-games/games/minesweeper/) | Jev 扫雷 | 概率推断替代硬编码规则 |
| [`app/jev-games/games/werewolf/`](app/jev-games/games/werewolf/) | Jev 狼人杀 | 多轮对话中的身份判断 |
| [`app/jev-games/apps/web/`](app/jev-games/apps/web/) | React + Vite 统一入口 | `/games/*` 对比路由 |
| [`app/doudizhu/`](app/doudizhu/) | 斗地主三座位自动对局 | NanoJev 模式：确定性引擎 + JSON 状态 + 渲染省略隐藏信息 |
| [`app/blackjack/`](app/blackjack/) | 21 点 | 基本策略 gold + 爆牌概率预计算，本地裁判零依赖 |
| [`app/sudoku/`](app/sudoku/) | 数独评测 | MRV 选格 + 试错记忆：55 洞约束裁判 **0/10 → 5/10** |
| [`app/typesafe-mario-repro/`](app/typesafe-mario-repro/) | typesafe-mario 复现研究 | 上游两处缺陷实锤 + 帧粒度 8→4 提升 **2.8×** |
| [`app/smart-home/`](app/smart-home/) | 智能家居完整版 | 语音/LLM 对比/成本统计；精简版见第五章 |

## 03 两个必看的细节

**数独的试错记忆**：猜错的数字被记住并在下一拍发布回请求（"此格已证错：1, 2"），裁判不再重复犯错——这是把**应用侧的迭代喂回判断侧**的最小范例，55 洞场景胜率翻倍。

**Mario 复现的方法论**：上游 headless 环境缺抬起沿、nametable 相机页错位导致网格一半时间全空——复现他人项目时，"替身死了是数据不是缺陷"，误归因到模型头上会糊掉真相。这套定位思路比结论更值钱。

## 04 来源与许可

- jev-games：作者 [lzdFeiFei](https://github.com/lzdFeiFei)，[原仓库](https://github.com/lzdFeiFei/jev-games)未附 LICENSE，版权归原作者，仅作学习收录；
- 其余五项目来自 [Bald0Wang/jev-playground](https://github.com/Bald0Wang/jev-playground)（CC0-1.0，对齐 NanoJev 约定），仓库级架构文档见 [`app/ARCHITECTURE.playground.md`](app/ARCHITECTURE.playground.md)。

各项目内的 README / EXPERIMENT.md 有完整实验报告与数据。
