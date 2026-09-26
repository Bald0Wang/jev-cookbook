# 移动靶射击（Predict Position）验证测试报告 · 作者 Fyuan0206（PR #3）

## 1. 这是什么

ViZDoom 移动靶实验：模型在 left / right / shoot / noop 四个动作里选，成功以**真实击杀**为准。state 含可见物体标签框、血量/弹药/姿态与最近 4 帧。

## 2. 实验意义

这是"暴露失败模式"的实验：原仓库实测 Jev 完整测试集 **11/128**、演示局 seed 9300720 在 1.40s 开火打偏——失败模式是「过早开火、很少转身」。它诚实地划出了判断模型在**时序动作**上的边界。

## 3. 要回答的问题（本轮验证）

随提取收录的测试套件在本机能否通过？需要 ViZDoom 的部分能否运行？

## 4. 实验怎么做的

`main/.venv` 跑 `scripts/` 下 5 个自包含测试模块（截图 `figures/tests-cli.png`）。

## 5. Jev 每一步怎么工作（原设计）

state = 可见物体框 + 血量/弹药/姿态 + 最近 4 帧；Choice 在四动作里选；射击时机、转身阈值由代码门控（不是模型属性）。

## 6. 实验结果与说明

| 模块 | 结果 |
|---|---|
| test_unified_doom_env | **13 passed** |
| test_build_predict_position_demo | **9 passed** |
| test_build_shooting_demo | **6 passed**（4 subtests，4.32s） |
| test_sonic_predict_data / test_prepare_sonic_supervision | 收集失败（训练侧依赖未收录） |

**28 通过、0 逻辑失败**。运行完整模型评估还需 ViZDoom 环境与 checkpoint（见原 docs/SONIC_PREDICT_POSITION_RESULTS.md）。

## 7. 成本与耗时

0.16 秒、零 API 调用。

## 8. 结论与后续

环境与构建逻辑全绿。这个项目的价值恰在它的失败数据：把"判断模型不擅长时序连续控制"讲清楚了——这正是第 5 章用"状态查询走本地直读、不进判断"这类设计的原因。终局演示见 `final.html`。
