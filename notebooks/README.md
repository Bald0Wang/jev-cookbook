# Notebooks

本目录收录与 TypeSafe 官方文档对应的中文实验笔记，采用「理论 → 分步实验 → 观察与小结」的结构。
从下表按章节阅读，每本 Notebook 均可独立运行。

## 章节笔记本

**章节结构（五部）**：第一章 `01_认识Jev`（官方 Introduction/Quickstart/Use Case Map/AI Primer 四章合并）；第二章 `02–06`（System One、状态、原语、置信度、应用构建——各自独立不合并）；第三章 `07_架构模式`（官方 Patterns 各模式已合为一册）；第四章 `08_实战指南`（官方 Cookbook 十八篇合并）；第五章 `09_智能家居实验`（官方 Demo + 配套 `smart_home_demo/` 文件夹）。官方文档中没有对应章节的扩展实验不编号。

| Notebook | 对应官方章节 | 内容 |
|---|---|---|
| [01 · 认识 Jev（建议从这里开始）](01_认识Jev.ipynb) | Introduction + Quickstart + Use Case Map + AI Primer（四章合并） | Jev 是什么、与 LLM 的区别、三原语上手、场景地图、校准、社区实测补充、赛事指挥台综合实验 |
| [02 · System One](02_SystemOne.ipynb) | [System One](https://docs.typesafe.ai/concepts/system-one) | 单次调用机制、与 LLM 对比、退款三问与问题 ID 对照 |
| [03 · 状态](03_状态.ipynb) | [State](https://docs.typesafe.ai/concepts/state) | 状态格式、信息量与政策条件 |
| [04 · 原语](04_原语.ipynb) | [Primitives](https://docs.typesafe.ai/primitives) | Choice / Score / Noul、结构化与中文场景 |
| [05 · 置信度](05_置信度.ipynb) | [Confidence](https://docs.typesafe.ai/confidence) | 分布形状、三路分流、阈值与分类层级 |
| [06 · 应用构建](06_应用构建.ipynb) | [How to Build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one) | Python 控制流程、客服分支与五个小配方 |
| [07 · 架构模式](07_架构模式.ipynb) | [Patterns](https://docs.typesafe.ai/patterns) | 推测性扇出、置信度门控、复合评分与意图路由 |
| [08 · 实战指南](08_实战指南.ipynb) | [Cookbooks](https://docs.typesafe.ai/cookbooks) 十八篇合并 | 自一致性、并行提问、重排序、语义搜索、结构恢复、函数调用、技能推荐、实体对齐、RAG 段落、引用核查、防护栏、SDE 级联、日期抽取、预解析、层级分类、特征发现、置信度分类 |
| [09 · 智能家居实验](09_智能家居实验.ipynb) | [Smart Home Demo](https://docs.typesafe.ai/demos/smart-home) | 投机提示复刻、Notebook 内单次调用实测、内嵌 3D 应用；配套 [`smart_home_demo/`](smart_home_demo/) |
| [Pi + Jev 集成实验](Pi_Jev集成实验.ipynb) | — | Pi RPC、Skill 选择与工具执行前的 gate 判断 |
| [DSH × Jev 决策协作](DSH_Jev决策协作.ipynb) | — | 原语、路由代码、真实会话与失败复盘；[配套工程](../apps/dsh-jev-decision/) |

01–03、06 已用真实 API 在线执行验收；04/05/07 与两本扩展实验的验收记录见维护表。
详细检查与逐章记录见 [维护与验证说明](MAINTENANCE.md)。

## 研究子项目（独立目录）

| 目录 | 内容 | 输出性质 |
|---|---|---|
| [jev_mem/](jev_mem/) | Jev-Mem（UT Dallas，arXiv:2609.23986）记忆架构研究：架构走读、16 轮四臂对照、48~384 轮长程缩放、真 LoCoMo 基准与结论总览 | 2026-09-25 真实 API 实测（真 Jev + DeepSeek + Qwen3-Embedding） |
| [jev_harness/](jev_harness/) | [JevHarness 项目分析与评估](jev_harness/JevHarness%20项目分析与评估.md)（社区贡献） | 项目分析文档 |

## Cookbooks 实战指南（18 篇）

官方 18 篇 Cookbook 已合并为 [`08_实战指南.ipynb`](08_实战指南.ipynb) 一册（原 `cookbooks/` 散册已移除，生成方式见 `generators/build_cookbook_notebooks.py`）。每篇一节、共用一套准备样板：逐格定义 state 和 questions，调用真实 TypeSafe API，再由 Python 完成排序、阈值、重建或函数分派。十八篇篇目见该册目录（自一致性×2、并行提问、重排序、语义搜索、结构恢复、函数调用、技能推荐、实体对齐、RAG 段落分类、引用核查、LLM 防护栏、SDE 级联、日期抽取、预解析值抽取、层级分类、特征发现、置信度分类）。

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
├── smart_home_demo/         # 第九章配套：本地服务 + 3D 应用
├── generators/             # 生成器、公共组件、模板与版本约束
├── pi_jev_demo/             # Pi + Jev 配套 extension 与 skills
├── jev_mem/                # Jev-Mem 记忆架构研究（独立子项目，见其 README）
├── jev_harness/            # JevHarness 项目分析（社区贡献）
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
