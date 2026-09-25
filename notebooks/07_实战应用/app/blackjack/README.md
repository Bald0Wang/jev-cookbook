# 21点 — Jev 牌桌

让一个判定模型（Jev / 本地基本策略替身）打 21 点，浏览器实时观战、看它每次决策的完整
推理材料。参照 [NanoJev](https://github.com/TianyuCodings/NanoJev) 的 `snake_game.py`
模式构建：确定性引擎、完整可验证的 JSON 状态、`render_request` 渲染问题、程序化 gold。

## 快速开始

```bash
python3 serve_blackjack.py            # 本地裁判，零依赖（纯标准库）
python3 serve_blackjack.py --host 0.0.0.0 --port 8802   # 局域网观战
```

浏览器打开提示的地址（默认 http://127.0.0.1:8802）。自动连续下注（每手 10），破产自动换下一副牌。

**接真实 Jev**：

```bash
pip install typesafe-sdk
export TYPESAFE_API_KEY=你的key      # console.typesafe.ai 获取
python3 serve_blackjack.py --judge jev
```

## 规则与决策

- 单副牌，低于 15 张自动重洗；BJ 赔 3:2；庄家所有 17 停牌；首两张可 double；不做分牌
- 模型每步回答一个 `choice`：`hit` / `stand` / `double`
- 模型看到的是 JevHarness 式的**预计算事实**：手牌价值（软/硬）、庄家明牌、
  **鞋组成**、**下一张爆牌概率**——不需要它自己数牌
- 模型看不到：鞋的顺序、庄家的暗牌
- gold = 基本策略表（硬牌/软牌 × 庄家明牌的完整矩阵），标注为策略参考

## 可视化

庄家暗牌背面朝上、玩家明牌、💰 资金条与每轮输赢筹码历史、爆牌概率大字显示。
右侧面板显示发给模型的问题全文（含鞋组成 JSON）与裁判的实际回答。

## 参数

```bash
--port 8802        # 端口
--host 0.0.0.0     # 允许局域网访问
--pace 0.7         # 动作节奏（秒/步）
--seed 1           # 首副牌种子
--judge jev        # 用真 Jev（需 typesafe-sdk + TYPESAFE_API_KEY）
--no-browser       # 不自动开浏览器
```

## 命令行评测（不开浏览器）

```python
import blackjack_game as B
state = B.make_blackjack(seed=1)
while not state['done']:
    state = B.step(state, B.basic_strategy(state))
print(state['bank'])   # 基本策略下的资金轨迹
```

## 实验报告

完整实验（意义 / 问题 / 过程 / 结果）见 [EXPERIMENT.md](EXPERIMENT.md)，
可复现脚本 `experiment.py`，数据在 `artifacts/`。

## 文件

- `blackjack_game.py` — 引擎：鞋、发牌、命中/停牌/加倍、庄家规则、结算、请求渲染、gold
- `serve_blackjack.py` — 观战服务器（本地裁判 / 真 Jev）
