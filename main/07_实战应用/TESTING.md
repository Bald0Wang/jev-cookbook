# 第七章 · 统一测试环境与验证指南

## ⚡ 一键启动（推荐）

```bash
cd main/07_实战应用
python3 start.py        # 拉起全部 7 个服务 + 打开总控菜单（:4200）
python3 start.py stop   # 全部停止
python3 start.py status # 只看状态
```

总控菜单包含：**7 个实况服务卡**（贪吃蛇/扫雷/狼人杀/智能家居/Games Lab/斗地主/21 点，带 :端口）+ **3 张回放卡**（迷宫/移动靶/浏览器 final.html，本地录制不调 API，随时可看）+ **Mario 实况卡**（:8770，自动探测上游 venv，缺失时降级为报告卡）+ **5 个一键运行实验**（数独/迷宫测试/移动靶测试/守卫回归/live smoke——点击即跑、输出就地显示，可重跑）。密钥从本目录 `.env` 读取（已 gitignore）。

> 以 [jev-playground](https://github.com/Bald0Wang/jev-playground) 的实验规范为准：每个项目一份 **EXPERIMENT.md 八节报告**（这是什么 / 实验意义 / 要回答的问题 / 实验怎么做的 / Jev 每一步怎么工作 / 实验结果与说明 / 成本与耗时 / 结论与后续），运行截图存 `figures/`，**数据必须实测**、人工数据必须标注。

## 1. 环境清单（一次配好，全章通用）

| 组件 | 版本/要求 | 用途 |
|---|---|---|
| Python | ≥ 3.12（本仓库 `main/.venv`）+ pytest、httpx[http2]、typesafe-sdk 0.7.x | maze / predict_position 测试套件、browser-use |
| Node.js | ≥ 18（本机 24） | jev-games 三个游戏 + React 入口 |
| Chrome | 任意近期版本 | browser-use 的 Browser Harness（CDP） |
| `TYPESAFE_API_KEY` | [console.typesafe.ai](https://console.typesafe.ai/keys) 免费注册 | 全部项目的 Jev 调用 |
| `TEXT_MODEL_API_KEY`（可选） | 任意 OpenAI 兼容端点 | 仅 browser-use 的 TYPE_TEXT |

**密钥安全**：各项目用自己目录的 `.env`（browser-use / jev-games/games/*），已被仓库 `.gitignore` 覆盖（`main/07_实战应用/app/**/.env`）——**浏览器和 git 都不会接触 key**。

## 2. 每个项目怎么跑、验证什么

| 项目 | 启动命令 | 验证方式 | 报告 |
|---|---|---|---|
| [gridloop](app/jev-games/games/gridloop/) | `cd app/jev-games/games/gridloop && node server.mjs` → :4173 | `/api/move` 直连测延迟 + 浏览器自动驾驶 | [EXPERIMENT.md](app/jev-games/games/gridloop/EXPERIMENT.md) |
| [minesweeper](app/jev-games/games/minesweeper/) | 同上 → :4174 | 自动扫雷全程 + 动作统计 | [EXPERIMENT.md](app/jev-games/games/minesweeper/EXPERIMENT.md) |
| [werewolf](app/jev-games/games/werewolf/) | 同上 → :4175 | 完整一局（夜间技能/白天投票全走 Jev） | [EXPERIMENT.md](app/jev-games/games/werewolf/EXPERIMENT.md) |
| [web 入口](app/jev-games/apps/web/) | `npm install && npm run build` | 构建 + 总览页渲染 | [EXPERIMENT.md](app/jev-games/apps/web/EXPERIMENT.md) |
| [maze](app/maze/) | `pytest scripts/test_*.py` | 环境核心 35 测试全绿；训练侧依赖缺失的失败已归因 | [EXPERIMENT.md](app/maze/EXPERIMENT.md) |
| [predict_position](app/predict_position/) | 同上 | 28 测试全绿；完整评估需 ViZDoom + checkpoint | [EXPERIMENT.md](app/predict_position/EXPERIMENT.md) |
| [browser-use](app/browser-use/) | `python scripts/check_guards.py` + `scripts/smoke.py` | 21 项守卫 + 真 Jev 端到端（verified: true） | [EXPERIMENT.md](app/browser-use/EXPERIMENT.md) |
| [doudizhu](app/doudizhu/) | `python3 serve_doudizhu.py` | 见其 EXPERIMENT.md（playground 原报告） | ✓ |
| [blackjack](app/blackjack/) | `python3 serve_blackjack.py` | 同上 | ✓ |
| [sudoku](app/sudoku/) | `python3 jev_sudoku.py --episodes 10` | 同上 | ✓ |
| [mario 复现](app/typesafe-mario-repro/) | 见其 README | 同上 | ✓ |
| [smart-home](app/smart-home/) | `python3 serve_smart_home.py` | 见其 EXPERIMENT.md | ✓ |

## 3. 实测结果汇总（2026-09-26，真实 API）

| 项目 | 关键实测 |
|---|---|
| gridloop | 决策 0.29–0.85s；自动驾驶分数 4→30、蛇长 5→33、零死亡 |
| minesweeper | 31 动作 / 159 格翻开 / 18 旗（20 雷），零触雷；无解即停 |
| werewolf | 完整一局狼人胜利；投票置信 43–93% 分层；跨轮一致性检查生效 |
| browser-use | 21 守卫全过；live smoke 6 决策 5 动作 verified:true，3.65s |
| maze | 35 测试过 / 4 失败（训练侧依赖缺失，已归因）/ 0 逻辑回归 |
| predict_position | 28 测试全过 / 2 模块依赖缺失 |
| web 入口 | Vite 构建 501ms，产物 299KB（gzip 95KB） |

## 4. 已知边界（诚实清单）

- maze / predict_position 部分测试因**训练侧模块未随应用提取**而不可收集（`predict_toy_decisions`、`train_pipeline_decisions` 等）——不是逻辑回归；
- browser-use 的 TYPE_TEXT 需要 `TEXT_MODEL_API_KEY`（判断与文本生成分离是硬约束）；
- werewolf 无 `DEEPSEEK_API_KEY` 时发言走模板（显式标注 template_fallback），判断仍由 Jev 完成；
- jev-games 端口约定：4173/4174/4175，被占自动 +1。
