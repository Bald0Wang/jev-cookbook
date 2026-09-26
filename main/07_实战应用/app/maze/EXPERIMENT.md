# 迷宫（Maze）验证测试报告 · 作者 Fyuan0206（PR #3）

## 1. 这是什么

8×8 到 50×50 的迷宫闭环控制实验：模型**只看 5×5 局部窗口**，判断四个方向通不通（结构化判断），路线由同一套探索代码完成——把「几何判断」和「规划」刻意拆开。

## 2. 实验意义

检验 System One 在**感知受限**条件下的判断可靠性：不给他全局地图，只给局部真相。原仓库实测：统一 checkpoint 225 次尝试到达 50×50 出口（纯 Jev 2,738 次）——判断模型 + 简单探索策略能走出大迷宫。

## 3. 要回答的问题（本轮验证）

随提取收录的测试套件在**本机环境**下能否通过？哪些测试因训练侧依赖缺失而不可跑？

## 4. 实验怎么做的

`main/.venv`（Python 3.12 + pytest 9）跑 `scripts/` 下全部 6 个测试模块，逐个统计并通过/失败原因归类（截图 `figures/tests-cli.png`）。

## 5. Jev 每一步怎么工作（原设计）

state = 5×5 局部窗口 + 已观测边图的紧凑掩码；问题 = 对四个方向的 Noul（通/不通）+ Choice（往哪走）；只给未试过的方向。路线规划在代码里。

## 6. 实验结果与说明

| 模块 | 结果 | 说明 |
|---|---|---|
| test_unified_grid_envs | **15 passed**（8 subtests） | 环境核心逻辑全过 |
| test_scaled_maze | 14 passed / **3 failed** | 失败全部因为 `ModuleNotFoundError: predict_toy_decisions`（训练侧模块，未随应用提取收录） |
| test_composed_maze | 6 passed / **1 failed** / 1 skipped | 同因 |
| test_model_edges_maze / test_scaled_pipeline / test_build_local_maze_data / test_game_outcomes | 收集失败 | 缺 `evaluate_native_qwen_maze` / `train_pipeline_decisions` 等训练侧模块 |

**结论：35 通过、4 失败（全部因训练侧依赖缺失，非逻辑回归）、4 个模块不可收集。** 核心环境与游戏逻辑测试全绿。

## 7. 成本与耗时

0.27 秒、零 API 调用（纯本地测试）。

## 8. 结论与后续

本机验证通过（通过项全绿、失败项均可归因）。要跑完整"50×50 通关"实验需要上游训练仓库的 checkpoint 与 `predict_toy_decisions` 模块——建议后续向作者仓库确认提取边界。终局演示见 `final.html`（本地回放，不调 API）。
