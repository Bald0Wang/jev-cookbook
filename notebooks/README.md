# Notebooks

本目录收录与 TypeSafe 官方文档对应的中文实验笔记，采用「理论 → 分步实验 → 观察与小结」的结构。
从下表按章节阅读，每本 Notebook 均可独立运行。

## 章节笔记本

| Notebook | 对应官方章节 | 内容 |
|---|---|---|
| [简介实验](introduction_experiments.ipynb) | [Introduction](https://docs.typesafe.ai/introduction) | 模型定位、原子判断与组合评分 |
| [快速开始实验](quickstart_experiments.ipynb) | [Quickstart](https://docs.typesafe.ai/introduction/quickstart) | Playground、HTTP 请求与三种答案 |
| [AI 入门实验](ai_primer_experiments.ipynb) | [AI Primer](https://docs.typesafe.ai/introduction/machine-learning-primer) | 概率信号、否定与模糊表达 |
| [System One 实验](system_one_experiments.ipynb) | [System One](https://docs.typesafe.ai/concepts/system-one) | 多问共享状态、组合路径与问题 ID |
| [状态实验](state_experiments.ipynb) | [State](https://docs.typesafe.ai/concepts/state) | 状态格式、信息量与政策条件 |
| [原语实验](primitives_experiments.ipynb) | [Primitives](https://docs.typesafe.ai/primitives) | Choice / Score / Noul、结构化与中文场景 |
| [置信度实验](confidence_experiments.ipynb) | [Confidence](https://docs.typesafe.ai/confidence) | 分布形状、三路分流、阈值与分类层级 |
| [架构模式实验](patterns_experiments.ipynb) | [Patterns](https://docs.typesafe.ai/patterns) | 推测性扇出、置信度门控、复合评分与意图路由 |
| [应用构建实验](build_with_typesafe_experiments.ipynb) | [How to Build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one) | Python 控制流程、客服分支与五个小配方 |
| [应用场景实验](use_case_map_experiments.ipynb) | [Use Case Map](https://docs.typesafe.ai/concepts/use-case-map) | 相关性排序、空结果出口与可验证配方 |
| [Pi + Jev 集成实验](pi_jev_integration_experiments.ipynb) | — | Pi RPC、Skill 选择与工具执行前的 gate 判断 |

简介、快速开始、AI 入门、System One、状态、应用构建和应用场景七章已通过离线验证，**真实 API 验收待完成**。
详细检查与逐章记录见 [维护与验证说明](MAINTENANCE.md)。

## Cookbooks 实战指南（18 篇）

`cookbooks/` 覆盖官方全部 18 篇实战指南，命名规则为「官方 slug + `_experiments.ipynb`」。
它们沿用 [patterns_experiments.ipynb](patterns_experiments.ipynb) 的结构：逐格定义 state 和 questions，调用真实 TypeSafe API，
再由 Python 完成排序、阈值、重建或函数分派。

| 笔记本 | 官方章节 | 其他 |
|---|---|---|
| [consistency_noul_experiments.ipynb](cookbooks/consistency_noul_experiments.ipynb) | [自一致性：Noul](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook) | |
| [consistency_choice_experiments.ipynb](cookbooks/consistency_choice_experiments.ipynb) | [自一致性：Choice](https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook) | |
| [parallel_questions_experiments.ipynb](cookbooks/parallel_questions_experiments.ipynb) | [并行提问](https://docs.typesafe.ai/cookbooks/parallel_questions) | |
| [rerank_typesafe_experiments.ipynb](cookbooks/rerank_typesafe_experiments.ipynb) | [重排序](https://docs.typesafe.ai/cookbooks/rerank_typesafe) | |
| [semantic_find_experiments.ipynb](cookbooks/semantic_find_experiments.ipynb) | [逐行语义搜索](https://docs.typesafe.ai/cookbooks/semantic_find) | |
| [autoformat_experiments.ipynb](cookbooks/autoformat_experiments.ipynb) | [结构恢复](https://docs.typesafe.ai/cookbooks/autoformat) | |
| [function_calling_experiments.ipynb](cookbooks/function_calling_experiments.ipynb) | [函数调用](https://docs.typesafe.ai/cookbooks/function_calling) | |
| [skill_suggestion_experiments.ipynb](cookbooks/skill_suggestion_experiments.ipynb) | [技能推荐](https://docs.typesafe.ai/cookbooks/skill_suggestion) | |
| [entity_alignment_experiments.ipynb](cookbooks/entity_alignment_experiments.ipynb) | [知识图谱实体对齐](https://docs.typesafe.ai/cookbooks/entity_alignment) | |
| [classifying_rag_passages_experiments.ipynb](cookbooks/classifying_rag_passages_experiments.ipynb) | [RAG 段落分类](https://docs.typesafe.ai/cookbooks/classifying_rag_passages) | |
| [citation_check_experiments.ipynb](cookbooks/citation_check_experiments.ipynb) | [引用核查](https://docs.typesafe.ai/cookbooks/citation_check) | |
| [llm_guardrails_experiments.ipynb](cookbooks/llm_guardrails_experiments.ipynb) | [LLM 防护栏](https://docs.typesafe.ai/cookbooks/llm_guardrails) | |
| [sde_cascade_experiments.ipynb](cookbooks/sde_cascade_experiments.ipynb) | [SDE 级联](https://docs.typesafe.ai/cookbooks/sde_cascade) | |
| [date_extraction_experiments.ipynb](cookbooks/date_extraction_experiments.ipynb) | [日期抽取](https://docs.typesafe.ai/cookbooks/date_extraction_cookbook) | |
| [pre_parsed_value_extraction_experiments.ipynb](cookbooks/pre_parsed_value_extraction_experiments.ipynb) | [预解析值抽取](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook) | |
| [hierarchical_classification_experiments.ipynb](cookbooks/hierarchical_classification_experiments.ipynb) | [层级分类](https://docs.typesafe.ai/cookbooks/hierarchical_classification) | |
| [autoresearch_feature_discovery_experiments.ipynb](cookbooks/autoresearch_feature_discovery_experiments.ipynb) | [自动研究特征发现](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) | |
| [classification_using_confidence_experiments.ipynb](cookbooks/classification_using_confidence_experiments.ipynb) | [基于置信度的分类](https://docs.typesafe.ai/cookbooks/classification_using_confidence) | |

前 8 篇由 `generators/build_cookbook_notebooks.py` 统一生成；其余 10 篇各自独立产出，
其单元格编号不再连续编号，直接按官方 slug 命名。

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
.venv/bin/jupyter lab quickstart_experiments.ipynb
```

密钥仅从环境变量读取，请勿写进 Notebook。选择“重启内核并运行全部”，确保不依赖之前的变量。

入门与概念七章默认 `live` 模式，缺少密钥或调用失败即停止；无密钥学习可明确选择离线模式：

```bash
JEV_RUN_MODE=offline .venv/bin/jupyter lab quickstart_experiments.ipynb
```

原有章节可能在鉴权失败时自动使用离线示例，具体以各章说明为准。离线输出均为人工数据，不能视为模型实测结果。

## 目录与维护

```text
notebooks/
├── <章节>_experiments.ipynb  # 按上表选择正式章节
├── cookbooks/              # 官方 18 篇实战指南
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
