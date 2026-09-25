# Jev 的请求与回复结构：怎么设计的，怎么跑的

这份文档讲清楚四件事：一次调用长什么样、回复有哪几种结构、一次推理从环境到
动作的完整路径、以及为什么这样设计。所有报文片段都是真实采样的
（马里奥的请求/回复来自 `artifacts/sample_*.json`，其余来自各引擎的
`render_request`）。

## 1. 一句话概括

**一次 HTTP 调用 = 一份状态（state）+ 一组问题（questions）；回复 = 每个问题
一个带概率和置信度的答案。** 状态是我们整理好的事实，问题是我们要它做的判断，
答案除了结论还附带「它有多确定」和「各个选项的概率分别多少」。

## 2. 请求长什么样

真实请求（马里奥，节选自 `sample_request.json`）：

```json
{
  "state": {
    "objective": "Reach the flag in World 1-1 without dying.",
    "player": { "x": 172, "y": 79, "grounded": true, "jump_phase": "grounded", ... },
    "hazard": { "enemy_ahead": true, "nearest_enemy_kind": "goomba", ... },
    "terrain": { "obstacle_distance_tiles": null, "gap_distance_tiles": 6, ... },
    "reaction_timing": { "action_horizon_frames": 8, "last_inference_delay_frames": 0, ... },
    ...
  },
  "model": "jev-latest",
  "questions": {
    "next_action": {
      "type": "choice",
      "instructions": "Which controller macro should Mario commit to next? ...",
      "criteria": { "noop": "Release the controls ...", "right_run_jump": "Start a running jump ...", ... }
    },
    "jump_needed": { "type": "noul", "instructions": "Do trusted terrain ... indicate a forward jump ...?" },
    "danger": { "type": "score", "instructions": "How dangerous is Mario's immediate situation?",
                "criteria": ["Safe open movement", "Potential obstacle or enemy soon", "Immediate collision ..."] }
  }
}
```

三个部分各司其职：

- **state**：任意 JSON。四个实验分别放棋盘、手牌、游戏内存解析结果。
  可以随时加字段（我们的 v2 harness 就加了 `takeoff_window` 和 `prior_attempts`），
  模型直接读结构，不用解析自然语言。
- **questions**：一个请求里可以问多个问题。每个问题有 `type`（下面第三节）、
  `instructions`（策略陈述：「有 KO 就拿」「队友的牌不要压」）和 `criteria`
  （每个选项的当场事实）。马里奥一次问三个，共享同一份 state——省两次往返。
- **model**：模型名，如 `jev-latest`。

## 3. 回复有哪几种结构

回复里每个问题对应一个答案对象，共三种原语（字段名来自 SDK 的 wire model）：

```json
{
  "model": "jev-latest",
  "usage": { "input_tokens": 1932, "output_tokens": 12 },
  "answers": {
    "next_action": {
      "type": "choice", "choice": "right_run", "confidence": 0.88,
      "probabilities": { "noop": 0.02, "right_run": 0.88, ... }
    },
    "jump_needed": { "type": "noul", "noul": 0.05 },
    "danger": {
      "type": "score", "score": 0.0, "confidence": 0.85,
      "legend": { "0": "Safe open movement", "1": "Potential obstacle or enemy soon", ... },
      "probabilities": { "0": 0.9, "1": 0.08, "2": 0.02 }
    }
  }
}
```

| 原语 | 回答什么 | 回复字段 | 四个实验里的用法 |
|---|---|---|---|
| `choice` | 从 criteria 里选一个 | `choice`、`probabilities`（每个选项的概率）、`confidence` | 四个实验的主力：填哪个数字 / 出哪手牌 / hit还是stand / 按哪个手柄宏 |
| `noul` | 是/否 | `noul`（0–1，越大越「是」） | 马里奥问「此刻前跳有没有用」 |
| `score` | 按等级打分 | `score`（0–2）、`probabilities`、`legend`（等级说明） | 马里奥问「处境多危险」，驱动页面的危险度条 |

两个细节值得知道：

- **`probabilities` 是完整分布**，不只是答案。我们的可视化页面直接把它画成
  概率条；做 gold 对照实验时，偏离多少一算就知道。
- **`confidence` 和 `probabilities` 不是一回事**：前者是模型对这次判断的整体
  确定程度，后者是选项间的相对可能性。两者都可以用来做「不确定就升级处理」
  这类门控。

## 4. 一次推理怎么跑完（以马里奥为例）

从环境推进到动作生效，一共九步：

```
① NES 模拟器推进 4-8 帧
        ↓
② 从 RAM 读原始字节（位置、敌人槽位、nametable 地形缓冲）
        ↓
③ MarioStateParser 解析成结构化事实（local_grid、敌人投影、地形几何）
        ↓
④ （v2 harness）特征预计算：起跳窗口判定、跨局记忆蒸馏
        ↓
⑤ 组装 state + questions（policy.py 里构造 Choice/Noul/Score 对象）
        ↓
⑥ typesafe_sdk 序列化成 JSON，POST /v1/systemone
        ↓
⑦ SDK 用 Pydantic wire model 校验回复（字段不符会直接报错）
        ↓
⑧ 答案提取：policy.py 的 _answer() 从 choices/nouls/scores 三个字典里取回
        ↓
⑨ 代码把答案变成输入：right_run_jump → SIMPLE_MOVEMENT[4] → 模拟器执行
```

第 ⑧ 步是 harness 与回复结构唯一的接触点，上游代码里长这样
（`typesafe_mario/policy.py`）：

```python
action_answer = self._answer(response, "next_action", "choices")   # 取 choice 答案
jump_answer  = self._answer(response, "jump_needed", "nouls")      # 取 noul 答案
danger_answer = self._answer(response, "danger", "scores")         # 取 score 答案
```

另外每步都会记录两个数：`latency_ms`（这次推理花了多久，供下次请求的
`reaction_timing` 使用——模型据此知道"我的决定生效时世界已经前进了多少"）和
`usage`（token 用量，用于算钱）。

## 5. 为什么这样设计

**为什么 state 用 JSON 而不是一段话？** 模型读结构和人读表格一样直接；
我们要加字段（起跳窗口、跨局记忆）也是加个键就行，不用改提示词模板。
上游 README 说得直白："TypeSafe accepts JSON directly, so there is no need to
flatten telemetry into prose."

**为什么算术要留在代码里？** 起跳窗口、爆牌概率、合法出牌集合——这些算错了
没法问责，而且每次请求重算浪费 token 还引入方差。代码算成结论（
`jump_must_start_this_decision: true`），模型只解释结论。这是 JevHarness 的
核心分工："Reason deeply during development. Freeze the strategy."

**为什么一次调用问多个问题？** 三个判断共享同一份 state。合并成一次请求，
总延迟是一次往返而不是三次；token 上 state 也只付一份。

**为什么要概率分布？** 三个用途：页面可视化（概率条）、置信度门控（不确定时
可以让代码兜底）、和 gold 对照（`make_record` 记录的 gold 分布 vs 模型分布，
偏离度直接可算）。

**instructions 和 criteria 的分工？** instructions 是**策略**（对所有局势成立
的判断规则），criteria 是**每个选项的当场事实**（"出对子 9，剩 9 张"）。
策略写一次，事实每拍重算——这就是 JevHarness 宝可梦 harness 的做法，
我们四个实验沿用了同一结构。

## 6. 本地替身和真 API 的区别

没有 API Key 时，实验用一个本地替身回答请求。注入点在 SDK 客户端构造处
（`repro_run.py` 的 `patched_client`）：把 SDK 的 client 类换成一个子类，
把 HTTP 传输换成本地对象。**请求序列化、回复校验、答案提取走的都是同一条
真实代码路径**，只是最后没有网络往返。

替身按同样的 schema 生成答案（本文第 3 节的样例就来自替身，结构上真 API
的回复一模一样）。接真 API：设 `TYPESAFE_API_KEY`，去掉替换即可，
`render_request` 和答案消费代码零改动。

## 7. 四个实验的设计对照

| 实验 | state 里放什么 | 问题设计 | 用的原语 | 答案怎么变成动作 |
|---|---|---|---|---|
| 数独 | 9×9 棋盘、待填格、行列宫的已用数字 | 1 个 choice（9 个数字）+ 9 个 boolean（该数字是否与解一致） | choice | 选中的数字填进格子；错记失误 |
| 21点 | 双方手牌、庄家明牌、剩余牌组成、爆牌概率 | 1 个 choice（hit/stand/double） | choice | 直接执行对应动作 |
| 斗地主 | 自己的 20/17 张牌、别家剩牌数、桌面牌型、倍率 | 1 个 choice（50+ 个合法出牌，逐个带后果说明） | choice | 出牌/过 |
| 马里奥 | 位置/速度/敌人投影/地形/反应时序/上回合结果 8 组事实 | 1 个 choice（7 个手柄宏）+ noul + score | choice + noul + score | 手柄宏 → `SIMPLE_MOVEMENT` 索引 → 模拟器 |

每行的 `state` 与 `questions` 构造都在各项目的 `render_request`（马里奥在
`policy.py` 的 `choose`），gold 标签在 `make_record`，可直接对照阅读。
