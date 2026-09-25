# 可精确求解的游戏决策数据

这组自写小游戏将“动作是否合法”“哪个动作最优”“真实走完后是否成功”变成可由程序检查的目标。井字棋采用完整 minimax，网格导航采用 BFS；不调用 Jev 或其他教师 API，不使用 GPU。它不是 Doom，也不代表已复现 Jev 的游戏能力。

代码：`scripts/game_tasks.py`、`scripts/build_game_decisions.py`。数据位于 `research/private_games_v2/`，包含五个 split、合并的 `all.jsonl` 和 `manifest.json`。初始生成的文件没有 teacher 字段；后续教师标注由独立流程完成，不影响这里的程序真值定义。

## 实际规模与分区

随机种子为 17。每个状态同时生成一个动态动作 Choice、一个 Boolean、一个 Score 问题，共 1,160 个状态、3,480 道题。

| 游戏 | train | dev | calibration | test | ood |
|---|---:|---:|---:|---:|---:|
| 井字棋 | 360 | 40 | 40 | 80 | 40 |
| 网格导航 | 400 | 40 | 40 | 80 | 40 |
| 合计状态 | 760 | 80 | 80 | 160 | 80 |

井字棋从空盘枚举所有可达状态，任意一方获胜立即停止扩展，得到 5,478 个原始状态。过滤终局和仅剩一个合法动作的状态后，按 D4 的 8 种旋转/镜像合并：中后盘、2–5 个合法动作的 ID 池有 539 个对称类；早盘、6–9 个合法动作的 OOD 池有 54 类。先分配完整对称类到 split，再在类内选择一个朝向渲染。默认使用其中 520 个 ID 类和 40 个 OOD 类。

网格 ID 为 4×4，OOD 为 6×6。生成独立障碍、目标与起点；**分组键包含尺寸、障碍与目标的 D4 标准形式，并忽略起点**。因此同一障碍/目标地图的不同起点及对称变换不会跨 split。本版本每个地图组仅保留一个起点，也没有在同一 split 重复同组。

完整数据审计确认 1,160 个唯一环境状态、1,160 个唯一源组，跨 split 的上述源组交集为 0。该结论限于所声明的状态/对称类/地图组隔离：井字棋共享规则，分区之间仍可能存在父子局面；网格也可能有局部结构相似，不能据此声称所有结构相似性都被排除。

## 游戏规则与标签

井字棋中 X 先手，轮流落子，连成横、竖或对角三子获胜。合法候选严格等于所有空格；minimax 从当前行动方视角取胜/和/负价值 `+1/0/-1`。只最大化结果，不额外偏好更早获胜或更晚失败。动作目标包含所有具有最优 minimax 价值的合法动作。Boolean 判断当前方能否强制获胜，Score 的三档依次为负、和、胜。

网格只能向 north/east/south/west 走一步，每步代价 1，不能越界或穿墙。**候选筛选只查看当前位置相邻墙壁与边界，不调用 BFS，也没有 STOP 动作。** BFS 从目标反向计算精确距离；能到达目标时，动作目标包含所有能沿最短路前进的合法动作。无法到达目标时，问题明确约定全部合法动作并列，避免暗中利用“是否提供 STOP”泄漏可达性。各 split 恰有 25% 网格状态不可达。Boolean 判断可达性；Score 分成 1–2 步、3–5 步、至少 6 步、不可达四档。

对不可达网格，动作质量本来就无法按“能否到达”区分，动作命中最优集合也会容易获得高分；评估必须单独报告可达状态的导航成功率与路径效率，不能把不可达样本的任意动作算成真实导航成功。

## 与训练器兼容的记录

原有顶层字段 `id/state_id/family_id/split/state/questions/gold/metadata` 保持一致，动作问题 ID 为 `action`，辅助问题为 `solvable` 和 `value`。新增：

```python
gold_probs = {
    "action": {action_id: probability_for_each_legal_action},
    "solvable": {"false": 0.0_or_1.0, "true": 0.0_or_1.0},
    "value": {"0": ..., "1": ..., ...},
}
gold_probs_kind = {
    "action": "optimal_action_policy",
    "solvable": "deterministic_truth",
    "value": "deterministic_truth",
}
optimal_actions = {"action": [...all_equally_optimal_action_ids...]}
```

Choice 的 `gold_probs` 是**最优动作集合上的均匀训练策略目标**，不是成功概率、真实世界不确定性或校准置信度。Boolean 和 Score 目标是确定性真值的 one-hot 分布。`gold.action` 仅为按动作 ID 字典序选出的一个代表；多解样本设置 `metadata.representative_optimal_action_not_unique_truth=true`，评估时必须接受全部 `optimal_actions.action`，不能把另一个同样最优的动作当错。

`metadata.environment_state` 保存可直接交给环境的 JSON 状态，`metadata.oracle` 保存精确解与各动作价值/代价，方便独立核验。它们不会被拼进 `state` 或 `questions`。所有渲染模板与 split 标题全文保存在 manifest；标题按 split 改变，游戏规则和问题模板明确共享，未宣称模板完全隔离。

## 供真实 rollout 复用的接口

```python
from game_tasks import valid_actions, step, solve
from build_game_decisions import make_record

state = {"game": "tic_tac_toe", "board": "XX.OO....", "player": "X"}
legal = valid_actions(state)        # ["cell_3", "cell_6", ...]
exact = solve(state)               # 当前方 value、全部 optimal_actions
record = make_record(state, "rollout", index=0, seed=17)
next_state = step(state, "cell_3")  # 返回新状态，不改变原输入
```

井字棋 board 是长度 9 的字符串，`.` 为空位，行优先；动作 `cell_1` 到 `cell_9` 使用 1-based 位置编号。`player` 表示下一步行动方，终局也保留轮换后的下一方标识，因此终局 `value` 是该方视角。

```python
state = {
    "game": "grid_navigation", "size": 4,
    "walls": [[0, 1], [1, 1]],
    "position": [0, 0], "goal": [0, 3],
}
```

网格坐标为 0-based `[row,column]`，动作是 `north/east/south/west`。`solve` 返回 `distance`（不可达时为 null）、`reachable`、`action_costs`、`optimal_actions`。到达目标或无合法动作时 `terminal=true`。

`make_record(state, split, index=0, seed=17, rng=None)` 支持 `split="rollout"`，此时使用与训练一致的标题/问题模板，继续随机化候选显示顺序。有且仅有一个合法动作时可如实渲染一个候选，不造出假动作；rollout 推荐直接执行唯一动作并单独计数，避免将被迫步骤算作模型决策。终局或无合法动作会拒绝渲染 Choice，由 rollout 调用方处理结束条件。

## 验证与限制

执行 `python3 scripts/build_game_decisions.py --self-test` 可运行 5 项测试并按固定种子重新生成数据。测试覆盖立即制胜和强制阻挡、非法动作、终局与输入不变性、合法状态枚举、对称变换、BFS 多条最短路/绕路/不可达、同图异起点分组、生成重现性、重复/分区泄漏拒绝、多最优动作分布和 rollout 渲染。生成后还会逐条重算所有动作与辅助标签，核对概率映射和归一化。

按当前训练器的完整候选路径拼接方式，全部输入为 ASCII，最长路径的 UTF-8 字节数加 EOS 为 **401**。这为 byte-level Qwen tokenizer 的 512-token 限制留出了余量；实际训练仍应调用所用 tokenizer 核对，并保持超长报错、不截断。manifest 记录生成代码和各 split 内容的 SHA-256。

数据并未强行平衡每个辅助标签。例如 4×4 网格中至少 6 步的类别较少：train 10/400、dev 0/40、calibration 0/40、test 2/80；6×6 OOD 中为 8/40。标签和最优动作数的完整分布均在 manifest。OOD 只改变井字棋剩余步数/候选数量或网格尺寸，不是新规则或开放世界任务。独立教师标注、学生训练、模型概率校准与真实 rollout 成绩应分别报告。
