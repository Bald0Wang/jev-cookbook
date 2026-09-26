# AGENT.md — 第七章实战应用 · AI 助手工作手册

> 本文档面向 AI 助手（Claude / Codex / 人类协作者），是第七章所有实验的**操作规范**。
> 目标：新加入的助手读完本文件即可独立完成——新增实验、跑验证测试、截图、写八节报告、提交推送，不踩任何已知坑。

---

## 1. 本章在仓库中的位置

```
jev-cookbook/
└── main/
    └── 07_实战应用/          ← 本章根目录
        ├── README.md          章节导览（三个来源、十二个可运行应用）
        ├── TESTING.md         统一测试环境与验证指南（八节报告规范）
        ├── start.py           ⚡ 一键启动（7 服务 + 总控菜单 :4200）
        ├── .env               密钥（gitignore 覆盖，永不入库）
        ├── logs/              运行日志（gitignore）
        ├── figures/           总控菜单截图
        └── app/               十二个项目（按来源分三组）
            ├── jev-games/     外部项目（lzdFeiFei）：贪吃蛇/扫雷/狼人杀 + React 入口
            ├── maze/          闭环控制应用（Fyuan0206）：50×50 通关录制回放
            ├── predict_position/ 移动靶射击（Fyuan0206）：失败模式实况
            ├── browser-use/   浏览器智能体：travel 夹具三步回放 + live smoke
            ├── typesafe-mario-repro/ Mario 复现：NES 模拟器 + 本地替身驾驶员
            ├── smart-home/    智能家居完整版：3D 演练场 + 语音 + 成本统计
            ├── doudizhu/      斗地主：CSS 扑克观战
            ├── blackjack/     21 点：资金曲线
            └── sudoku/        数独：MRV 选格 + 试错记忆
```

## 2. 必须遵守的规范

### 2.1 密钥安全（最高优先级）

- **所有 `.env` 文件必须被 gitignore 覆盖**——写入 `.env` 之前先验证：
  ```bash
  git check-ignore -q "<路径>/.env" && echo "✅" || echo "❌ 未忽略，先修 gitignore"
  ```
- **永远不用 `git add -A`**——只 `git add` 你明确改过的文件路径。
- 每次提交前扫一遍：`git status --short | grep "\.env"` 应无输出。
- 密钥轮换后更新所有本地 `.env`，但 **key 永远不写进代码、报告或 README**。

### 2.2 八节实验报告

每个实验必须有 `EXPERIMENT.md`，严格八节（以 playground 规范为准）：

1. **这是什么**
2. **实验意义**
3. **要回答的问题**
4. **实验怎么做的**
5. **Jev 每一步怎么工作**
6. **实验结果与说明**
7. **成本与耗时**
8. **结论与后续**

- 数据必须实测（真实 API 或本地裁判），人工数据显式标注；
- 截图存 `figures/` 子目录，在报告中引用；
- 失败数据不删——诚实标注失败模式比只报好数字有价值。

### 2.3 一键启动（start.py）

- 新增有 HTTP 服务面的实验时，在 `SERVICES` 列表加一行：
  ```python
  ("名称", "标题", 端口, "入口路径", "观察要点", "报告相对路径"),
  ```
- CLI 实验加 `RUNNABLES` 字典：`slug → (标题, bash命令, 说明, 报告路径)`。
- **新增服务前先跑 `python3 start.py stop` 再 `start.py`**——端口冲突时 start.py 自动 +1。
- 菜单页面每 15 秒自动刷新状态（🟢/⚪），不需要手动刷新。

### 2.4 回放实验（final.html）

- `final.html` 是**本地录制的回放**，不调 API。播放器自带播放/暂停/单步/时间轴/调速。
- 每个回放页顶部必须有 📖 实验解读卡（`<details open>` 折叠块），说明：这段回放在做什么、关键数字、模型看到的 vs 代码控制的分工。

### 2.5 已知坑（不要重蹈覆辙）

| 坑 | 原因 | 解法 |
|---|---|---|
| `.env` 入库 | `git add -A` 扫到了新建的 .env | 先写 gitignore 再创建 .env；只 add 明确路径 |
| macOS 无 `timeout` 命令 | GNU coreutils 不是 macOS 自带 | 用 nbconvert 的 `--ExecutePreprocessor.timeout` 或 Python subprocess timeout |
| 推理型模型正文在 `reasoning_content` | `content` 为空 | 服务端做了回退读取 |
| doudizhu/blackjack 无 `--no-open` | 参数名不同 | start.py 用 `--judge local` 代替 |
| werewolf 发言走模板 | 无 DeepSeek key | 发言显式标 `template_fallback`，判断仍由 Jev 完成 |
| browser-use TYPE_TEXT 需要文本模型 | 判断与生成分离是硬约束 | 配 `TEXT_MODEL_API_KEY`（任意 OpenAI 兼容端点） |
| maze/predict_position 部分测试不可收集 | 训练侧模块未随应用提取收录 | 已归因，不是逻辑回归 |
| 并行会话覆写 | 同仓库多会话同时写 | 提交前 `git status` 复核；只 add 自己改的文件 |

## 3. 常见操作流程

### 3.1 新增一个实验

1. 在 `app/` 下创建项目目录（含 README.md、入口文件、figures/）
2. 写 `EXPERIMENT.md`（八节，数据实测）
3. 有 HTTP 服务面 → 在 start.py `SERVICES` 加一行
4. CLI 实验 → 在 start.py `RUNNABLES` 加一行
5. 跑一遍验证，截图存 `figures/`
6. 更新 TESTING.md 实测汇总表
7. 更新章节 README.md 项目表
8. `git add <明确路径>`（不用 -A），commit + push

### 3.2 跑全部验证测试

```bash
cd main/07_实战应用
python3 start.py          # 启动 7 服务 + 菜单
python3 start.py status   # 检查状态
# 逐项目跑测试（见 TESTING.md 逐项目命令表）
python3 start.py stop     # 结束
```

### 3.3 截图

- 浏览器实验：ZCode 浏览器 `tab.screenshot()` → 存项目 `figures/`
- CLI 实验：输出渲染成 HTML 后截图，或直接存 stdout 日志
- 3D / canvas 实验：确保页面渲染完成后再截（等 ≥1.5s）

### 3.4 密钥轮换

1. 在上游平台轮换（console.typesafe.ai / platform.stepfun.com）
2. 更新所有本地 `.env`（`grep -rl "旧key前缀" main/07_实战应用/app/ --include=".env"`）
3. 验证新 key：`curl -s https://api.typesafe.ai/v1/systemone -H "Authorization: Bearer $NEW_KEY" ...`
4. 重启受影响的服务
5. **不要**把新旧 key 写进任何代码、报告或 README

## 4. 当前状态速查

| 指标 | 值 |
|---|---|
| 可运行项目 | 12 |
| 八节报告 | 12（全部完成） |
| 截图 | 10+ 张（`figures/` 各项目分布） |
| 一键启动服务 | 7 个（端口 4173/4174/4175/4180/8801/8802/8812） |
| CLI 实验命令 | 5 个（browser-use ×2 / maze / predict_position / sudoku） |
| 回放页 | 3 个（maze / predict_position / browser-use 的 final.html） |
| 测试套件 | maze 35 过 + predict_position 28 过 + browser-use 21 守卫全过 |

## 5. 上游仓库与许可

| 项目 | 上游 | 许可 |
|---|---|---|
| jev-games | [lzdFeiFei/jev-games](https://github.com/lzdFeiFei/jev-games) | 未附 LICENSE（版权归原作者） |
| maze / predict_position | Fyuan0206（PR #3 收录） | 随上游 |
| browser-use | [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) | MIT |
| typesafe-mario-repro | [fhshaik/typesafe-mario](https://github.com/fhshaik/typesafe-mario) | 上游未改 |
| doudizhu / blackjack / sudoku / smart-home | [Bald0Wang/jev-playground](https://github.com/Bald0Wang/jev-playground) | CC0-1.0 |

**更新 vendored 项目时**：从上游重新 rsync（排除 `.git` / `node_modules` / `__pycache__` / `.env` / `certs`），不要手动逐文件搬运。
