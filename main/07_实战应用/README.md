# 07 · 实战应用合集（Applications）

第七章不再讲新概念，而是把**用 Jev 做出来的完整应用**收在一起——两个来源、九个项目，每个都是能独立跑起来的成品：

## 来源一：jev-games（外部项目，作者 [lzdFeiFei](https://github.com/lzdFeiFei)）

> 原仓库：https://github.com/lzdFeiFei/jev-games （完整克隆收录（22caced），内容原样保留；
> 该仓库未附 LICENSE 文件，版权归原作者，这里仅作学习收录并显著署名。）

小游戏合集，每个游戏 `games/<名称>/` 独立运行，另有 React + Vite 统一入口（`apps/web/`）提供总览/对比路由。

| 项目 | 说明 | 运行 |
|---|---|---|
| [`jev-games/games/gridloop/`](app/jev-games/games/gridloop/) | Jev 贪吃蛇 | 见其 README（`server.mjs` + 本地 key） |
| [`jev-games/games/minesweeper/`](app/jev-games/games/minesweeper/) | Jev 扫雷 | 同上 |
| [`jev-games/games/werewolf/`](app/jev-games/games/werewolf/) | Jev 狼人杀 | 同上 |
| [`jev-games/showcase/jev-games/`](app/jev-games/showcase/jev-games/) | 决策复盘展示 | 静态页面 |
| [`jev-games/apps/web/`](app/jev-games/apps/web/) | React 统一入口 | `cd apps/web && npm run dev` |

## 来源二：jev-playground（自家仓库 [Bald0Wang/jev-playground](https://github.com/Bald0Wang/jev-playground)）

四个确定性游戏环境 + 一个 3D 演练场，全部遵循 NanoJev 的 `snake_game.py` 模式（确定性引擎、完整可验证 JSON 状态、渲染时省略隐藏信息）。**本地裁判零依赖可跑；设 `TYPESAFE_API_KEY` 后同一套问题走真实 Jev，代码零改动。**

| 项目 | 说明 | 快速开始 |
|---|---|---|
| [`doudizhu/`](app/doudizhu/) | 斗地主：三座位自动对局，CSS 扑克实时观战 | `python3 serve_doudizhu.py` |
| [`blackjack/`](app/blackjack/) | 21 点：基本策略 gold、爆牌概率预计算 | `python3 serve_blackjack.py` |
| [`sudoku/`](app/sudoku/) | 数独评测：MRV 选格 + 试错记忆（55 洞 0/10 → 5/10） | `python3 jev_sudoku.py --episodes 10` |
| [`typesafe-mario-repro/`](app/typesafe-mario-repro/) | typesafe-mario 真机复现：上游两缺陷实锤 + 粒度实验 | 见其 README（需 Python 3.13 + 上游 venv） |
| [`smart-home/`](app/smart-home/) | 智能家居 3D 演练场（完整版，含语音/LLM 对比/成本统计） | `python3 serve_smart_home.py` |

> 仓库级总览与共同架构（无需切换到上游仓库）：[`README.playground.md`](app/README.playground.md) · [`ARCHITECTURE.playground.md`](app/ARCHITECTURE.playground.md)。
> `smart-home` 的精简配套版（仅服务 + 页面）也同时放在第五章 [`05_智能家居实验/smart_home_demo/`](../05_智能家居实验/smart_home_demo/)，供该章实验直接使用；这里的是带完整 README 与实验报告的项目原貌。

## 与教程各章的关系

- 判断原语（Choice/Score/Noul）怎么变成一个能玩的游戏 → 见 `doudizhu/`、`sudoku/` 的 judge 设计；
- 一次调用捆绑多问 + 代码端剪枝 → 见 `smart-home/`（第一章 5 节有模式讲解）；
- 怎么公平评测 → 第六章；
- 复现他人项目时如何定位上游缺陷 → `typesafe-mario-repro/`。

各项目内的 README / EXPERIMENT.md 有完整说明与实验数据。
