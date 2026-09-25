# Notebooks

本目录收录与 TypeSafe 官方文档对应的中文实验笔记，采用「理论 → 分步实验 → 观察与小结」的结构。
从下表按章节阅读，每本 Notebook 均可独立运行。

## 章节笔记本

**八章文件夹结构**：每章一个文件夹（`01_认识Jev/` … `08_前沿研究/`），章内 notebook 独立编号；第七章以 README 为目录收录可运行应用，第八章收录研究快照（jev_mem / jev_harness）。第四章每篇官方配方单开一本、篇尾附「知识补充」；官方文档中没有对应章节的扩展实验留在根目录不编号。

| Notebook | 对应官方章节 | 内容 |
|---|---|---|
| 章节 | Notebook | 对应官方文档 | 内容 |
|---|---|---|---|
| 第一章 | [01 · 认识 Jev](01_认识Jev/01_认识Jev.ipynb) | Introduction + Quickstart + Use Case Map + AI Primer（四章合并） | Jev 是什么、与 LLM 的区别、三原语上手、场景地图、校准、社区实测补充、赛事指挥台综合实验 |
| 第二章 | [01 · System One](02_核心概念/01_SystemOne.ipynb) | [System One](https://docs.typesafe.ai/concepts/system-one) | 单次调用机制、与 LLM 对比、退款三问与问题 ID 对照 |
| 第二章 | [02 · 状态](02_核心概念/02_状态.ipynb) | [State](https://docs.typesafe.ai/concepts/state) | 状态格式、信息量与政策条件 |
| 第二章 | [03 · 原语](02_核心概念/03_原语.ipynb) | [Primitives](https://docs.typesafe.ai/primitives) | Choice / Score / Noul、结构化与中文场景 |
| 第二章 | [04 · 置信度](02_核心概念/04_置信度.ipynb) | [Confidence](https://docs.typesafe.ai/confidence) | 分布形状、三路分流、阈值与分类层级 |
| 第二章 | [05 · 应用构建](02_核心概念/05_应用构建.ipynb) | [How to Build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one) | Python 控制流程、客服分支与五个小配方 |
| 第三章 | [01 · 架构模式](03_架构模式/01_架构模式.ipynb) | [Patterns](https://docs.typesafe.ai/patterns) | 推测性扇出、置信度门控、复合评分与意图路由（各模式合一册） |
| 第四章 | [实战指南 18 篇](04_实战指南/) | [Cookbooks](https://docs.typesafe.ai/cookbooks) | 每篇一个官方配方一本 notebook，篇尾附「知识补充」（关联章节/社区实测/工程坑） |
| 第五章 | [01 · 智能家居实验](05_智能家居实验/01_智能家居实验.ipynb) | [Smart Home Demo](https://docs.typesafe.ai/demos/smart-home) | 投机提示复刻、Notebook 内单次调用实测、内嵌 3D 应用；配套 [`smart_home_demo/`](05_智能家居实验/smart_home_demo/) |
| 第六章 | [01 · 模型评测](06_模型评测/01_模型评测.ipynb) | [JevBench](https://github.com/fstandhartinger/jevbench) 式基准 | Laya vs Jev：231 道公开题四维对比（准确率/底线/Brier/ECE）；来自 [PR #6](https://github.com/Bald0Wang/jev-docs-zh/pull/6)（作者 Micheal024），配套 [`laya/benchmark/`](../laya/benchmark/) 评测框架 |
| 第七章 | [实战应用合集](07_实战应用/README.md) | — | 九个可运行应用：外部 [jev-games](https://github.com/lzdFeiFei/jev-games)（贪吃蛇/扫雷/狼人杀 + React 入口）+ 自家 [jev-playground](https://github.com/Bald0Wang/jev-playground) 五项目，以项目为单位收录在 `app/` |
| 第八章 | [前沿研究](08_前沿研究/README.md) | Jev-Mem（[arXiv:2609.23986](https://arxiv.org/abs/2609.23986)）+ JevHarness | 两个研究快照：判断模型管记忆（四臂实测/长程缩放/LoCoMo）与管控制流（开发/执行分离） |
| 扩展 | [Pi + Jev 集成实验](Pi_Jev集成实验.ipynb) | — | Pi RPC、Skill 选择与工具执行前的 gate 判断 |
| 扩展 | [DSH × Jev 决策协作](DSH_Jev决策协作.ipynb) | — | 原语、路由代码、真实会话与失败复盘；[配套工程](../apps/dsh-jev-decision/) |

01–03、06 已用真实 API 在线执行验收；04/05/07 与两本扩展实验的验收记录见维护表。
详细检查与逐章记录见 [维护与验证说明](MAINTENANCE.md)。

## 研究子项目（独立目录）

| 目录 | 内容 | 输出性质 |
|---|---|---|

## Cookbooks 实战指南（18 篇）

官方 18 篇 Cookbook 每篇单开一本 notebook，位于 [`04_实战指南/`](04_实战指南/)（官方目录顺序编号 01–18）：
01 自一致性Noul · 02 自一致性Choice · 03 并行提问 · 04 重排序 · 05 逐行语义搜索 · 06 结构恢复 · 07 函数调用 · 08 技能推荐 · 09 实体对齐 · 10 RAG段落分类 · 11 引用核查 · 12 LLM防护栏 · 13 SDE级联 · 14 日期抽取 · 15 预解析值抽取 · 16 层级分类 · 17 自动研究特征发现 · 18 基于置信度的分类。

每本篇尾附**知识补充**：适用场景、与本章其他篇目/其他章节的关联路径、社区实测数字与工程坑。前 8 篇由 `generators/build_cookbook_notebooks.py` 生成（含补充注入），后 10 篇为独立成稿。
## 本地运行

需要 Python ≥ 3.10。在本目录执行以下命令创建环境（优先使用 uv）：

```bash
./setup_env.sh
```

入门与概念七章使用已验证的 SDK 版本，运行前安装对应约束：

```bash
.venv/bin/python -m pip install -r requirements.txt -c generators/constraints-foundations.txt
```

在本地配置启动进程的 `TYPESAFE_API_KEY` 环境变量后，打开所需章节：

```bash
.venv/bin/jupyter lab 01_认识Jev.ipynb
```

密钥仅从环境变量读取，请勿写进 Notebook。选择“重启内核并运行全部”，确保不依赖之前的变量。

入门与概念七章默认 `live` 模式，缺少密钥或调用失败即停止；无密钥学习可明确选择离线模式：

```bash
JEV_RUN_MODE=offline .venv/bin/jupyter lab 01_认识Jev.ipynb
```

原有章节可能在鉴权失败时自动使用离线示例，具体以各章说明为准。离线输出均为人工数据，不能视为模型实测结果。

## 目录与维护

```text
notebooks/
├── 01_认识Jev.ipynb … 07_架构模式.ipynb  # 按上表选择正式章节
├── 01_认识Jev/ … 08_前沿研究/       # 八章文件夹（七章 app/ 应用合集，八章研究快照）
│   └── 05_智能家居实验/smart_home_demo/  # 第五章配套：本地服务 + 3D 应用
├── generators/             # 生成器、公共组件、模板与版本约束
├── pi_jev_demo/             # Pi + Jev 配套 extension 与 skills
├── tests/                  # 本地检查
├── validation/             # 执行记录与离线预览
├── requirements.txt
├── setup_env.sh
├── README.md               # 阅读与运行入口
└── MAINTENANCE.md          # 生成、验证、验收与贡献说明
```

修改内容请编辑生成器，再重新生成并执行 Notebook。具体命令、验证记录和贡献说明见 [MAINTENANCE.md](MAINTENANCE.md)，制作规范见 [项目手册](../AGENT.md)。

应用实验（迷宫、移动靶射击、浏览器智能体）位于 [apps](../apps/)，属于可运行工程。

## DSH × Jev 学习案例

生成器：`generators/build_dsh_jev_decision_notebook.py`。先按配套工程安装 Node.js 24 依赖并编译。Notebook 默认实时模式，最多 4 次 TypeSafe 请求；只从环境变量读取 `TYPESAFE_API_KEY`，失败即停止。设置 `DSH_JEV_RUN_MODE=recorded` 可重读已归档的真实响应，不发送新请求、不自动回退。完整 DSH 会话仍需独立按工程指南运行，两种验证不能混为一谈。
