# 迷宫游戏（Maze）

从 NanoJev 提取的迷宫相关主要代码。迷宫是这条流水线的核心场景：**模型只做局部几何判断，代码负责路线规划**，两者严格分离。

## 模型看到什么、控制什么

- **观测**：以 agent 为中心的 **5×5 ASCII 局部窗口**、当前坐标与目标坐标、最近的物理事件，以及**完整已观测边图**的紧凑行掩码。拿不到整张墙图、拿不到最短路径答案。
- **动作**：只提供**未试过**的方向（包括会撞墙的方向——撞墙也是有效信息）。局部没有未试方向时，代码可以沿已验证的通路重新站位，每次重站位消耗同样的物理预算并单独记录。
- **问题**：每步 4 个独立的 `clear_<direction>` 布尔命题（朝某方向走一步是否不出界且不撞墙），加一个规划压力测试（最短路径动作、可达性、七级距离 Score）。
- **成功**：在物理尝试预算内到达目标。

## 文件清单

### 环境与数据构造

| 文件 | 作用 |
|---|---|
| `scaled_maze.py` | 迷宫生成器与模拟器。四种拓扑：`corridor`（直线偏置 DFS）、`tree`（无偏 DFS）、`loops`（有环）、`random_obstacle`（种子障碍密度，保留最大连通块） |
| `unified_grid_envs.py` | `UnifiedMazeEnv`，Gym 风格 `reset/step/close`。含 5×5 窗口渲染、边记忆掩码、重站位宏。**同时含 Snake 环境**（`UnifiedSnakeEnv`），因为迷宫模块依赖同一文件 |
| `snake_game.py` | Snake 模拟器，`unified_grid_envs.py` 的依赖，一并复制 |
| `game_tasks.py` | 纯标准库的可解玩具：`grid_navigation`（BFS 距离）与 `tic_tac_toe`（negamax），提供精确解、D4 变换和同源分组 |
| `game_question_profiles.py` | 问题模板（原子问题、规划问题的措辞） |
| `game_outcomes.py` | 事件记录：把一次执行的动作和真实结果写成训练行 |
| `build_scaled_games.py` | 生成跨尺寸课程（默认 8/16/32 训练、50 作尺寸 OOD） |
| `build_local_maze_data.py` | 用**推理时同一个渲染器**把已有迷宫快照转成局部原子问题；保留地图分组与 split 划分 |
| `build_navigation_v3.py` | 生成导航数据集（500 张图 / 3,000 状态 / 9,000 问题），排除之前游戏数据集里的所有源地图 |
| `assemble_navigation_v3_views.py` | 组装 `ascii_single` / `ascii_multi` / `coords_single` / `coords_multi` 四种视图 |

### 评估与控制器

| 文件 | 作用 |
|---|---|
| `evaluate_composed_maze.py` | **原子判断 + 代码规划**评估：在固定最短路线上跑诊断性问题，模型的输出无权改路线 |
| `evaluate_model_edges_maze.py` | **模型引导的边缘探索**：模型给 4 个局部安全概率，代码按概率排序未试边、记录真实碰撞反馈、只用物理验证过的开边做 BFS 找新前沿 |
| `evaluate_navigation_v3.py` | 闭环导航评估，`--policy greedy/sample/oracle/random`；每个活跃状态批量一次前向 |
| `evaluate_scaled_games.py` | 跨尺寸课程评估 |

### 测试

`test_scaled_maze.py`、`test_unified_grid_envs.py`、`test_game_outcomes.py`、`test_build_local_maze_data.py`、`test_composed_maze.py`、`test_model_edges_maze.py`、`test_scaled_pipeline.py`

### 文档（`docs/`）

| 文件 | 内容 |
|---|---|
| `SCALED_GAMES.md` | 环境与问题语义、拓扑定义、生成与验证命令 |
| `ATOMIC_PLANNING.md` | 原子判断 vs 代码规划的分离，固定路线基准结果 |
| `MODEL_EDGE_RESULTS.md` | 模型引导边缘探索的实测结果（2×size² 尝试预算） |
| `DEVELOPMENT_RESULTS.md` | 固定迷宫/Snake 试点（128 步上限）结果 |

### 配置（`configs/`）

`hard_navigation_demo_v1_cases.jsonl`（硬导航演示的冻结案例）、`unified_navigation_demo_v1.json`

### 本仓库回放

| 路径 | 作用 |
|---|---|
| `final.html` | 可双击打开的 Jev 50×50 动态回放（轨迹已内嵌，默认自动播放） |

## 跑测试

```bash
cd maze
PYTHONPATH="/c/Users/24019/Desktop/NanoJev-main/scripts" \
  python -m unittest discover -s scripts -p 'test_*.py'
# Ran 74 tests — OK (skipped=2)
```

## 需要的共享模块

测试通过 `PYTHONPATH` 从原仓库 `scripts/` 取这些模块，**未复制到本文件夹**：

| 模块 | 谁需要它 |
|---|---|
| `predict_toy_decisions.py` | `build_local_maze_data.py`、`evaluate_*.py`（渲染与编码）、多个测试 |
| `train_pipeline_decisions.py` | `build_scaled_games.py`（行校验与 split 常量）、`game_outcomes.py`、多个测试 |
| `evaluate_native_qwen_maze.py` | `test_model_edges_maze.py` |

要实际训练，还需要原仓库的 `train_pipeline_decisions.py`（训练器）和一个 checkpoint；命令见 `docs/SCALED_GAMES.md` 和原仓库 `research/pipeline_runbook.md`。

## 典型用法

```bash
# 1) 生成课程数据（纯标准库，无需 GPU）
python scripts/build_scaled_games.py --output-dir data/scaled_games_v4b --seed 20260920 \
  --train-sizes 8,16,32 --ood-sizes 50 --train-maps-per-size 12 --eval-maps-per-size 4 \
  --maze-states-per-map 4 --snake-states-per-episode 4 --snake-horizon 96

# 2) 只做 schema 校验，不加载模型
python scripts/train_pipeline_decisions.py --input data/scaled_games_v4b/policy --validate-only

# 3) 局部原子问题数据 + 训练（需要 GPU 和 checkpoint）
python scripts/build_local_maze_data.py --input data/scaled_games_v4b/policy --output data/local_maze_v1

# 4) 原子判断 + 代码规划评估
python scripts/evaluate_composed_maze.py --episodes results/rollout_pilot_episodes.jsonl \
  --engine checkpoint --checkpoint <checkpoint> --output composed_local_atomic.json
```

注意：`docs/ATOMIC_PLANNING.md`、`docs/DEVELOPMENT_RESULTS.md`、`docs/MODEL_EDGE_RESULTS.md` 在原仓库里是由 `summarize_*.py` 从 `results/*.json` 自动生成的表格，改数据要改生成脚本，不要手改表格。
