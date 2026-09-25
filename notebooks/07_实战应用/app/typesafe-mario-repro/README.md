# typesafe-mario-repro

在真实 NES 模拟器上复现并可视化 [fhshaik/typesafe-mario](https://github.com/fhshaik/typesafe-mario)——一个让 TypeSafe 的 Jev 模型直接选择《超级马力欧兄弟》手柄输入的实验项目。附带浏览器实时观战、跨局记忆、以及一组对照实验。

> **看什么**：模型看不到画面。harness 把 NES 内存（RAM）解析成结构化 JSON——位置、速度、前方敌人投影、地形几何、实测推理延迟——发给 Jev；Jev 在 7 个手柄宏（跑/跳/组合）中选一个，模拟器推进几帧，循环。本项目把这条决策链的每一环都搬到浏览器里实时展示。

---

## 快速开始（3 步）

**要求**：Python 3.13+（推荐用 [uv](https://docs.astral.sh/uv/) 自动安装）、macOS/Linux/Windows 均可。

```bash
# 1. 上游仓库放在本目录的兄弟位置
git clone https://github.com/fhshaik/typesafe-mario
cd typesafe-mario

# 2. 建环境（ROM 已随 gym-super-mario-bros 打包，无需自备）
uv venv --python 3.13 .venv
.venv/bin/pip install -e ".[mario,dev]"     # Windows: .venv\Scripts\pip ...

# 3. 启动可视化服务
cd ../typesafe-mario-repro
../typesafe-mario/.venv/bin/python viz_server.py
```

浏览器打开 **http://127.0.0.1:8770** 即可观看。局域网内同事访问用启动时打印的局域网地址（`--host 0.0.0.0` 默认开启）。

常用参数：

```bash
--port 8770                  # 端口
--fps 30                     # 画面速率（网页上也可调 12–240）
--latency-ms 60              # 模拟模型往返延迟（让反应时序参与决策）
--frames-per-decision 4      # 决策粒度：4 显著优于默认 8（见"发现"）
--host 127.0.0.1             # 只限本机访问
--env synthetic              # 换成无 ROM 的合成对照环境
```

**接真实 Jev**：设置 `TYPESAFE_API_KEY`（console.typesafe.ai 获取）并去掉 `viz_server.py` 中 `patched_client` 替换即可，其余代码零改动。默认状态下的模型应答来自一个**本地规则替身**（页面上有黄色横幅注明）——它验证管道，不代表 Jev 的真实水平。

---

## 页面上有什么

| 区域 | 内容 |
|---|---|
| 游戏画面 | 真 NES 帧实时直传（256×240 RGBA） |
| 模型被问到的问题 | 选中动作、每个动作的量化 criterion、置信度、推理延迟 |
| 概率分布 | 7 个手柄宏的完整 Choice 概率，选中项高亮 |
| 处境判断 | Noul（此刻前跳是否有利）、Score（危险度）、起跳窗口判定 |
| 碰撞网格 | 模型实际看到的 11×9 `local_grid` |
| 关卡地图 | 从 NES nametable 逐帧拼接累积的地形图 + 白线标当前位置 |
| 阵亡分布 | 每次阵亡按 x 位置堆叠计数——一眼看出"老死在哪" |
| Jev 的跨局记忆 | 每次阵亡时发给模型的完整上下文会存档，下一局以 `prior_attempts` 注入（可开关/清空） |
| 进度曲线 | 每决策一个点，旗杆线在首次通关后自动标注 |

控件：重新开始 / 暂停 / 自动重开 / 倍速 / 保存截图。API 端点（`/frame.rgba`、`/state.json`、`/model_input.json`、`/level.json`、`/history.json`、`POST /control`）可单独取用做二次开发。

---

## 实验脚本

所有脚本都在真机（内置 ROM）上运行，产出 JSON 到 `artifacts/`：

```bash
PY=../typesafe-mario/.venv/bin/python

$PY repro_real_env.py --decisions 300    # 完整决策闭环复现
$PY ab_real_env.py --decisions 400       # 上游缺陷 A/B：抬起沿（决定性证据）
$PY harness_ab.py --episodes 6           # harness v1 vs v2（JevHarness 风格）对照
```

## 三个主要发现

1. **上游 headless 路径缺按键抬起沿**（真机实锤）：SMB 在 A 键按下沿起跳，dashboard 路径处理了这一点，`--display none` 没有。同一策略同一种子：基线卡死在 x=594（269 个决策原地不动、269 次下令起跳都没跳起来），加上抬起沿跑到 x=1124。模型正确识别了"需要起跳"，但指令没有被执行——而状态里没有任何字段告诉它这件事。
2. **决策粒度是第一约束**：`--frames-per-decision` 从默认 8 降到 4，同一策略 best_x 提升 2.8 倍（1124→3156）。机制：4 格水管的起跳窗口实测仅 28.6px 宽，8 帧粒度一拍跨 21px，经常整拍错过。这比任何提示词工程都值钱。
3. **跳跃物理的精确数字**（喂给 harness 做预计算）：跑跳峰值 68px（4.25 格）在 t=25 帧、滞空 47 帧、水平跨度 82px；过 3 格水管的起跳窗口是距墙 33.8–93.6px。此前所有"神秘死亡"都能用这些窗口精确解释。

## 数独（NanoJev 风格的第二环境）

参照 [NanoJev](https://github.com/TianyuCodings/NanoJev) 的 `snake_game.py` 模式做的数独环境：
纯标准库、确定性生成（SplitMix64 种子流）、完整可验证的 JSON 状态、`render_request` 渲染成
choice + 9 个 boolean 的问题、程序化 gold 标签（唯一解可计算），渲染时省略 solution 与
RNG——与贪吃蛇省略 RNG 状态完全同构。

```bash
$PY jev_sudoku.py --episodes 10 --holes 40   # 40 洞：naked-single 读者 10/10 全胜
$PY jev_sudoku.py --episodes 10 --holes 55   # 55 洞：同一读者只剩 2/10 胜率
$PY jev_sudoku.py --judge jev                # 设 TYPESAFE_API_KEY 后走真 Jev
```

- 每步问一拍：harness 用 MRV（约束最多优先）选出下一格，judge 回答填哪个数字
- 每个数字的 criterion 带本格约束事实（"row 0 已含 [1,2,3...]，3 不可能"），对错即时判定
- 本地裁判只读公开约束（naked/hidden single），**绝不看 solution**——它的错误有信息量：
  40 洞全胜、55 洞 2/10，难度旋钮直接给出评测区分度
- 产物在 `artifacts/sudoku/`（JSONL 逐步记录 + 汇总）

## 牌类与棋类游戏已独立成文件夹

斗地主、21 点、数独已拆分到工作区顶层独立目录（各自带 README，纯标准库即可运行）：

```bash
../doudizhu/serve_doudizhu.py     # 斗地主观战（CSS 扑克、炸弹震屏、比分牌）
../blackjack/serve_blackjack.py   # 21 点观战（暗牌、资金曲线、爆牌概率）
../sudoku/jev_sudoku.py           # 数独评测（难度旋钮 40/55 洞）
```

## 目录

```
viz_server.py          可视化服务（本项目主入口）
mario_harness_v2.py    JevHarness 风格 harness v2（起跳窗口/动态 criteria/教训蒸馏）
attempt_memory.py      跨局记忆：阵亡上下文存档与注入
parser_fix.py          传感器修复：nametable 相机页错位（REPORT §11）
harness_ab.py          harness v1 vs v2 真机对照
ab_real_env.py         抬起沿缺陷真机 A/B
repro_real_env.py      真机完整闭环
repro_run.py           共享模块：替身裁判 + SDK 客户端补丁 + 日志汇总
REPORT.md              完整研究报告（方法、全部数据、失败机制链、更正记录）
```

> 2026-09-22 整理：合成环境时代的文件（synthetic_nes.py、repro_dashboard.py、
> ab_release_edge.py、verify_parser.py、verify_outcome.py）已移除——真机路径使它们
> 冗余，相关故事保留在 REPORT.md 的历史记录里。斗地主 / 数独 / 21 点已拆分为
> 工作区顶层的独立文件夹（`../doudizhu`、`../sudoku`、`../blackjack`），各自带 README，
> 纯标准库即可运行。

## 边界（分享前值得一读）

- 模型应答默认来自**本地规则替身**，不是 Jev；模拟器、ROM、NES 内存、解析器、决策循环、策略、SDK 编解码全部是上游真实代码。接真实 Key 的方法见上。
- 上游仓库未附 LICENSE 且声明不含任何 Nintendo ROM 或游戏数据；本项目使用的 ROM 来自 `gym-super-mario-bros` 包自带文件。
- 上游仓库（`typesafe-mario/`）未改动一行；全部工作在本目录的脚手架层完成。
- 完整方法、数据与过程中的错误更正见 [REPORT.md](REPORT.md)。

## 实验报告

结构化实验报告（意义 / 问题 / 过程 / 结果四段式）见 [EXPERIMENT.md](EXPERIMENT.md)；
完整研究记录见 [REPORT.md](REPORT.md)。
