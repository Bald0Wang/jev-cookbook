# Jev Cookbook

[Jev](https://docs.typesafe.ai) 是 TypeSafe AI 的旗舰模型——第一个 **System One 模型**：向它发送**状态（state）**和**类型化问题**（Choice / Score / Noul 三种原语），它返回带**概率与置信度**的结构化答案，代码直接消费——不做文本生成，无需解析。

本仓库是一个**完整的中文学习与实战体系**：十一章可运行教程、官方文档全站中文翻译、开源同类模型（Laya）微调全流程、Agent 集成示范，以及 500+ 文件的知识库快照。

> **在线文档站：https://bald0wang.github.io/jev-cookbook/**（GitHub Pages 自动部署）

---

## 仓库地图

```text
jev-cookbook/
├── main/                  ★ 十一章教程体系（本仓库核心，见下）
├── content/               官方文档中文翻译（Markdown 源）
├── dist/                  翻译站构建产物（Pages 从这里发布）
├── assets/                翻译站用的样式与图片
├── apps/dsh-jev-decision/ DSH × Jev 配套工程（第九章的实体）
└── AGENT.md               本仓库的工作流手册（贡献与验收约定）
```

---

## ★ main/ — 十一章教程体系

每章一个文件夹、章内独立编号；全部中文场景、中文提示词，各册可独立运行。
**在线优先**：检测到 `TYPESAFE_API_KEY` 即调真实模型，无 Key 自动降级离线示例（输出明确标注来源，不冒充实测）。
章节索引与逐章说明见 **[`main/README.md`](main/README.md)**，验收与维护记录见 [`main/MAINTENANCE.md`](main/MAINTENANCE.md)。

| 章 | 文件夹 | 内容 |
|---|---|---|
| 一 | `main/01_认识Jev/` | 合并官方 Introduction / Quickstart / Use Case Map / AI Primer 四章：Jev 是什么、与 LLM 的区别、三原语一次调用、场景地图、校准、社区实测补充、赛事指挥台综合实验 |
| 二 | `main/02_核心概念/`（5 册） | System One 机制与 LLM 对比、状态、原语（Choice/Score/Noul）、置信度、如何用 TypeSafe 构建 |
| 三 | `main/03_架构模式/` | 推测性扇出、置信度门控、复合评分、意图路由（官方 Patterns 合一册） |
| 四 | `main/04_实战指南/`（18 册） | 官方 Cookbook 每篇一本：自一致性 ×2、并行提问、重排序、逐行语义搜索、结构恢复、函数调用、技能推荐、实体对齐、RAG 段落分类、引用核查、LLM 防护栏、SDE 级联、日期抽取、预解析值抽取、层级分类、特征发现、置信度分类——篇尾附「知识补充」（关联章节 / 社区实测数字 / 工程坑） |
| 五 | `main/05_智能家居实验/` | 官方 Smart Home Demo 复刻：Notebook 内单次投机调用实测 + 内嵌 3D 应用；配套 `smart_home_demo/`（本地代理服务 + Three.js 页面，语音走阶跃 ASR，成本实时统计） |
| 六 | `main/06_模型评测/` | Laya vs Jev：231 道 JevBench 公开题四维对比（准确率 / 多数类底线 / Brier / ECE）；评测纪律：无重试、无回退、不修补答案、预算记账（来自 PR #6，作者 Micheal024；框架本体在第十章 `benchmark/`） |
| 七 | `main/07_实战应用/` | 九个可运行应用：外部 jev-games（贪吃蛇 / 扫雷 / 狼人杀 + React 统一入口，作者 lzdFeiFei）+ jev-playground 五项目（斗地主 / 21 点 / 数独 / Mario 复现 / 智能家居），以项目为单位收录 |
| 八 | `main/08_前沿研究/` | 两个研究快照：**Jev-Mem**（判断模型管记忆——三平面架构走读、四臂实测、48~384 轮缩放、真 LoCoMo）与 **JevHarness**（管控制流——开发/执行分离的项目评估） |
| 九 | `main/09_Agent集成/` | Jev 嵌入真实 Agent：Pi 工具执行前的 gate 判断（配套 `pi_jev_demo/` 扩展）+ DSH 决策协作与失败复盘 |
| 十 | `main/10_本地模型/` | Laya（开源类型化决策模型，Apache-2.0）全流程：模型介绍与 Jev 对比、RLCD 微调实操、中文数据集构造（ShareGPT-zh 38K 管线）、本地推理服务（`serve.py` Jev 兼容接口）、第六章基准框架本体 `benchmark/` |
| 十一 | `main/11_知识库/` | 知识库全量快照（21 板块）：官方文档中译、NanoJev、jevbench、飞书深度研究、公众号长文、Laya 部署示例——教程引用数字的原始出处 |

配套设施：`main/generators/`（章节笔记本生成源，重生成不丢补充内容）、`main/tests/`（结构契约测试）、`main/validation/`（离线预览）、`main/setup_env.sh`（一键环境）。

## content/ + dist/ — 官方文档中文翻译站

[docs.typesafe.ai](https://docs.typesafe.ai) 官方文档的**全站中文翻译**，在线阅读地址就是页首的文档站链接，`main/` 各章里的「中文参考」也指向它。

> ⚠️ 翻译部分为**非官方**社区翻译，仅供学习参考。文档内容与商标版权归原作者 TypeSafe AI 所有；翻译如有疏漏，以[英文原版](https://docs.typesafe.ai)为准。

## apps/dsh-jev-decision/ — DSH 配套工程

第九章 DSH 决策协作的实体工程（TypeScript）：构建产物、真实会话归档（2026-09-24）与验证文档；笔记本经同一插件的 ToolRuntime 发起真实请求，不启动聊天主模型。

## 致谢与来源

- **Micheal024**（[PR #6](https://github.com/Bald0Wang/jev-cookbook/pull/6)）：第六章评测框架与 Laya vs Jev 基准；
- **lzdFeiFei**（[jev-games](https://github.com/lzdFeiFei/jev-games)）：第七章收录的小游戏合集（原仓库未附 LICENSE，版权归原作者，仅作学习收录）；
- [jev-playground](https://github.com/Bald0Wang/jev-playground)：第七章自家应用的原仓库；
- [jev-cookbook-archive](https://github.com/Bald0Wang/jev-cookbook-archive)：知识库快照的导出源（本仓库更名前的同名私有库）。

## 快速开始

```bash
git clone https://github.com/Bald0Wang/jev-cookbook.git && cd jev-cookbook/main
./setup_env.sh                                    # 创建 .venv（uv 优先，Python ≥3.10）
export TYPESAFE_API_KEY=你的key                    # 可选：不设则用离线示例学习
.venv/bin/jupyter lab 01_认识Jev/01_认识Jev.ipynb  # 从第一章开始
```

工作流、验收与维护约定见 [AGENT.md](AGENT.md)。
