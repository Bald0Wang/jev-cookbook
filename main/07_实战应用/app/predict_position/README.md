# 位置预测游戏（ViZDoom Predict Position）

从 NanoJev 提取的 Predict Position（移动靶火箭弹）相关主要代码。这是统一 checkpoint 里最难的任务：模型要学会**何时转身、何时等待、何时开火**。

## 模型看到什么、控制什么

- **观测**：ViZDoom `predict_position` 场景下**可见物体标签的边界框**（不是像素）、玩家血量/弹药/姿态、最多最近 4 帧快照。完整物体列表、扇区和 automap 全部关闭。
- **动作**：4 个稳定 ID——`left`、`right`、`shoot`、`noop`。Predict Position 用转身键（Basic 场景用平移键，同一适配器）。
- **成功**：`KILLCOUNT` 正增长，与游戏原生奖励无关。原生超时、死亡、无击杀的脚本终止、任务截止都算失败。
- **时间记账**：`max_steps` 数模型决策数，可选 `max_ticks` 限制受控物理 tick；所有截止都是**任务终止**（`terminated=True, truncated=False`），采集器拒绝把外部截断当成失败标签。

## 文件清单

### 环境

| 文件 | 作用 |
|---|---|
| `unified_doom_env.py` | `UnifiedDoomEnv`，同步 headless `PLAYER` 模式。`scenario='basic'\|'predict_position'`，`frame_skip=4`，`history_length=2`。内部单 tick 推进以保证脚本地图退出重置时钟前不丢首次击杀。**懒加载 `vizdoom`**，没装也能 import |
| `unified_game_pipeline.py` | 采集管线（`cases` / `rollout` / `dataset` 子命令）：跑完整回合、写带 `continuation_policy_id` 和逐回合 SHA256 的清单，再把回合转成训练行。**跨游戏共享**，但本文件夹的监督代码直接依赖它，故一并复制 |

### 数据准备

| 文件 | 作用 |
|---|---|
| `sonic_predict_data.py` | 采集移动靶专家回合（896 个回合 / 17,498 个决策），注册案例队列并做同源分组隔离 |
| `sonic_predict_policy.py` | 专家策略 |
| `evaluate_sonic_dev_epsilon.py` | 开发集探索率选择 |
| `prepare_sonic_supervision.py` | 生成 hard（one-hot）/ soft（API 分布）两种监督臂；Maze/Snake/Basic 行按原字节保留。会把自己和依赖源的 SHA256 写进清单 |
| `run_sonic_supervision.py` | 监督训练运行器 |
| `summarize_sonic_supervision.py` | 汇总训练结果 |

### 评估

| 文件 | 作用 |
|---|---|
| `complete_sonic_evaluation.py` | 完整 128 案例 test/OOD 评估 |
| `evaluate_native_qwen_shooting.py` | 未调优 Qwen3-0.6B 基线（用原始词汇头，不用决策头） |
| `evaluate_native_qwen_unified.py` | 统一场景下的原生 Qwen 评估 |
| `replay_unified_episodes.py` | CPU 重放校验：重新执行录制的动作并逐字段比对，不做推理 |
| `filter_predict_position_wins.py` | 从完整队列里筛出演示用的胜局 |

### 演示导出

| 文件 | 作用 |
|---|---|
| `build_predict_position_demo.py` | 导出演示 JSON + 图集；导出前在 CPU 上重放录制决策做校验 |
| `build_shooting_demo.py` | 射击演示共用的渲染器 / `AtlasWriter` |

### 本仓库回放

| 路径 | 作用 |
|---|---|
| `final.html` | 可双击打开的本地动作记录回放（默认自动播放）；有逐帧图时显示原图，缺图时使用明确标注的场景示意，同时展示动作概率 |
| `figures/showcase-replay.png` | 回放页截图，展示 tick、动作选择与概率分布 |
| `frames/<seed>/` | 可选逐帧图目录；当前提取快照未收录原始逐帧图，因此回放页不会把示意画面伪装成真实帧 |

### 测试

`test_sonic_predict_data.py`、`test_prepare_sonic_supervision.py`、`test_run_sonic_supervision.py`、`test_summarize_sonic_supervision.py`、`test_complete_sonic_evaluation.py`、`test_native_qwen_shooting.py`、`test_sonic_dev_epsilon.py`、`test_unified_doom_env.py`、`test_build_predict_position_demo.py`、`test_build_shooting_demo.py`

### 文档（`docs/`）

| 文件 | 内容 |
|---|---|
| `SONIC_PREDICT_POSITION.md` | 训练管线与数据构造 |
| `SONIC_PREDICT_POSITION_RESULTS.md` | 完整 test/OOD 结果 |
| `PREDICT_POSITION_DEMO.md` | 演示录制：seed 9300720 NanoJev 等到 tick 177（5.06 s）开火命中，Jev 在 tick 49（1.40 s）开火打偏 |

### 配置（`configs/`）

`sonic_predict_supervision_v1.json` + `_cases.jsonl` + `_novelty.json`（监督实验协议）、`predict_position_demo_v1.json`（演示案例）、`sonic_unified_sft_v1.json`（统一 SFT 四臂配置）、`sonic_policy_pool_weights.json`

## 跑测试

```bash
cd predict_position
PYTHONPATH="/c/Users/24019/Desktop/NanoJev-main/scripts" \
  python -m unittest discover -s scripts -p 'test_*.py'
# Ran 79 tests — FAILED (errors=4)
```

**4 个 error 全在 `test_prepare_sonic_supervision.py`**，原因：`prepare_sonic_supervision.py` 会把 `train_unified_games.py` 和 `train_pipeline_decisions.py` 的 SHA256 记进输出清单（`preparation_source_sha256`），并要求这两个文件与它同目录。这两个是跨四个游戏共享的训练器，没有复制进来。其余 75 个测试通过。

要消除这 4 个 error，把这两个文件复制进 `scripts/` 即可——但会连锁引入 `predict_toy_decisions`、`summarize_unified_games` 等更多共享模块，实测反而让可加载测试从 79 掉到 35，所以这里选择用 `PYTHONPATH`。

## 需要的共享模块

| 模块 | 谁需要它 |
|---|---|
| `train_unified_games.py` | `prepare_sonic_supervision.py`、`run_sonic_supervision.py`、`complete_sonic_evaluation.py`、多个测试 |
| `train_pipeline_decisions.py` | `prepare_sonic_supervision.py` 及多个测试 |
| `predict_toy_decisions.py` | 训练器与推理路径 |
| `summarize_unified_games.py`、`summarize_appo_supervision.py` | `complete_sonic_evaluation.py`、`summarize_sonic_supervision.py` |
| `appo_basic_data.py`、`evaluate_appo_doom.py` | `sonic_predict_data.py`、`evaluate_native_qwen_*.py`（复用 Basic 的 APPO 专家代码） |
| `evaluate_native_qwen_navigation.py` | `evaluate_native_qwen_shooting.py` |
| `test_appo_basic_data.py`、`test_native_qwen_unified.py`、`test_unified_training.py` | 对应测试的夹具 |

## 典型用法

```bash
# 1) 采集专家回合（需要 .env 里的 API 凭据和预算上限）
python scripts/unified_game_pipeline.py rollout \
  --cases configs/sonic_predict_supervision_v1_cases.jsonl --engine jev \
  --controller greedy --epsilon 0.10 --seed 17 --env-batch 4 \
  --env-file ../../NanoJev-main/.env --journal-dir research/private_pp \
  --budget-usd 2 --output data/pp_expert.jsonl

# 2) 生成 hard / soft 监督数据（--original 原始混合数据，--expert 专家回合，--protocol 实验协议）
python scripts/prepare_sonic_supervision.py \
  --original data/mixed_all.jsonl --expert data/pp_expert.jsonl \
  --output data/pp_supervision --protocol configs/sonic_predict_supervision_v1.json

# 3) CPU 重放校验（不推理，逐字段比对录制的动作与结果）
python scripts/replay_unified_episodes.py --episodes data/pp_expert.jsonl --output replay.json
```

`complete_sonic_evaluation.py` 是需要启动器 PID 和多 GPU 的内部评估壳（`--original-launcher-pid`、`--gpus`），不是单机命令；完整 128 案例评估流程见 `docs/SONIC_PREDICT_POSITION_RESULTS.md`。ViZDoom 相关命令需要 `pip install vizdoom==1.3.0`；训练需要 CUDA GPU 和 `requirements-toy.txt` 里的固定版本。
