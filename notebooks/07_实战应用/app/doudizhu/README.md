# 斗地主 — Jev 牌桌

让一个判定模型（Jev / 本地规则替身）在真实斗地主规则下打牌，浏览器实时观战。
参照 [NanoJev](https://github.com/TianyuCodings/NanoJev) 的 `snake_game.py` 模式构建：
确定性引擎、完整可验证的 JSON 状态、`render_request` 渲染问题、程序化 gold 标签。

## 快速开始

```bash
python3 serve_doudizhu.py            # 本地裁判，零依赖（纯标准库）
python3 serve_doudizhu.py --host 0.0.0.0 --port 8801   # 局域网观战
```

浏览器打开提示的地址（默认 http://127.0.0.1:8801）。三家座位由参考策略驱动，自动连续开局。

**接真实 Jev**：

```bash
pip install typesafe-sdk
export TYPESAFE_API_KEY=你的key      # console.typesafe.ai 获取
python3 serve_doudizhu.py --judge jev
```

## 规则与决策

- 54 张牌（含双王），随机座位当地主（20 张），两农民各 17 张；先出完者获胜
- 支持牌型：单张 / 对子 / 三张 / 三带一 / 三带二 / 顺子(≥5) / 连对(≥3) / 飞机(≥2) / 炸弹 / 王炸
- 模型每步回答一个 `choice`：从全部合法动作中选一个。每个候选的 criterion 带后果
  （"出 对子9，压制桌面对子5，手牌剩 9 张"）
- 模型只看到**公开事实**：自己的手牌、别家剩余张数、桌面牌型、倍率——看不到任何暗牌
- gold 标签：每个动作是否压过桌面（确定性真值）+ 参考策略推荐（标注为策略非最优）

## 可视化

绿呢牌桌、CSS 手绘扑克（红桃方块红字）。👑 地主标记、决策者金色高亮、出牌气泡、
💥 炸弹/王炸震屏特效、🎉 胜利横幅、地主/农民比分牌。右侧面板显示发给模型的问题全文、
全部合法动作与参考概率、裁判的实际回答。

## 参数

```bash
--port 8801        # 端口
--host 0.0.0.0     # 允许局域网访问
--pace 0.7         # 出牌节奏（秒/步）
--seed 1           # 首局发牌种子
--judge jev        # 用真 Jev（需 typesafe-sdk + TYPESAFE_API_KEY）
--no-browser       # 不自动开浏览器
```

## 实验报告

完整实验（意义 / 问题 / 过程 / 结果）见 [EXPERIMENT.md](EXPERIMENT.md)，
可复现脚本 `experiment.py`，数据在 `artifacts/`。

## 文件

- `doudizhu_game.py` — 引擎：发牌、牌型生成与压制、出牌推进、状态校验、请求渲染、gold
- `serve_doudizhu.py` — 观战服务器（本地裁判 / 真 Jev）
