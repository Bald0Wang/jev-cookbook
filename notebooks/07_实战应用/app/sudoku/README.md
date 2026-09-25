# 数独 — Jev 解题台

让一个判定模型（Jev / 本地约束推理替身）一步步解数独，参照
[NanoJev](https://github.com/TianyuCodings/NanoJev) 的 `snake_game.py` 模式构建：
确定性生成（SplitMix64 种子流）、完整可验证的 JSON 状态、`render_request` 渲染问题、
程序化 gold 标签（唯一解可计算）。

## 快速开始

```bash
# 评测：本地裁判解 N 个谜题（零依赖，纯标准库）
python3 jev_sudoku.py --episodes 10 --holes 40

# 接真实 Jev
pip install typesafe-sdk
export TYPESAFE_API_KEY=你的key     # console.typesafe.ai 获取
python3 jev_sudoku.py --judge jev --episodes 10
```

## 玩法与决策

- `make_sudoku(seed, holes)` 生成唯一解谜题（默认 40 空格，可加到 55+ 提升难度）
- harness 用 **MRV**（约束最多的空格优先）选出下一格，judge 回答一个 `choice`：填 1–9 哪个数字
- 每个数字的 criterion 带本格约束事实：`row 0 已含 [1,2,3,5,6,7,8]；column 7 已含 [3,5,9]…`
- 另有 9 个 `boolean` 问题：`d 填这里是否与唯一解一致`（gold 可程序化判定）
- 填错记 mistake，3 错终局；填满即胜
- 模型看到的棋盘**不含 solution 与种子**——与贪吃蛇省略 RNG 状态同一约定

## 难度旋钮与试错记忆（本地裁判：naked/hidden single，绝不看 solution）

```bash
python3 jev_sudoku.py --episodes 10 --holes 40                    # 10/10 全胜
python3 jev_sudoku.py --episodes 10 --holes 55                    # 无记忆：2/10
python3 jev_sudoku.py --episodes 10 --holes 55 --trial-memory     # 加试错记忆：5/10
```

试错记忆：猜错的数字会被记住并在下一拍发布回请求（「此格已证错：1, 2」），
裁判不再重复同一个错答案。对 50–55 空格提升显著（约束裁判 55 洞 0/10 → 5/10），
机制与数据见 EXPERIMENT.md。

40 洞的谜题在 MRV + 排除事实下必然产生 naked single；55 洞需要真正的搜索。
这正是有意义的评测区间——换真 Jev 上来，同样的差距就是模型推理能力的度量。

## 产物

`artifacts/`：每局 JSONL（逐步的候选、回答、gold、对错）+ 汇总 JSON（胜率、平均得分、错误数）。

## 实验报告

完整实验（意义 / 问题 / 过程 / 结果）见 [EXPERIMENT.md](EXPERIMENT.md)，
可复现脚本 `experiment.py`，数据在 `artifacts/`。

## 文件

- `sudoku_game.py` — 引擎：生成/校验/step/请求渲染/gold（对齐 snake_game.py 的函数签名）
- `jev_sudoku.py` — 评测 runner（本地裁判 / 真 Jev）
