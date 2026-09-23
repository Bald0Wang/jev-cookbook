# Notebooks

本目录是「理论 + 真实 API 实验」的中文笔记本集合，与官方文档章节一一对应。
制作规范见 [`../AGENT.md`](../AGENT.md)；每个笔记本由 `generators/` 下的同名脚本生成。

## 目录结构

```
notebooks/
├── patterns_experiments.ipynb        # 架构模式（Patterns）
├── primitives_experiments.ipynb      # 三种原语（Primitives）
├── confidence_experiments.ipynb      # 置信度（Confidence）
├── pi_jev_integration_experiments.ipynb  # Pi + Jev 决策闭环
├── cookbooks/                        # 官方 18 篇实战指南，逐篇一个笔记本
├── generators/                       # 上述笔记本的生成器脚本（改完需重新生成）
├── pi_jev_demo/                      # Pi + Jev 配套的 TypeScript extension 与 skills
├── requirements.txt
└── setup_env.sh                      # 一键环境（Python ≥3.10 + 依赖，优先 uv）
```

## 章节笔记本

| 笔记本 | 对应官方章节 | 内容 |
|---|---|---|
| `patterns_experiments.ipynb` | [Patterns](https://docs.typesafe.ai/patterns) | 推测性扇出 / 置信度门控路由 / 复合评分 / 意图路由 |
| `primitives_experiments.ipynb` | [Primitives](https://docs.typesafe.ai/primitives) | 原语概览 / Choice / Score / Noul / 进阶：结构化；含文档原例与中文版实测对比 |
| `confidence_experiments.ipynb` | [Confidence](https://docs.typesafe.ai/confidence) | confidence 本质 / 三路分流 / 风险调整阈值 / 措辞影响 / 分类层级 fallback |
| `pi_jev_integration_experiments.ipynb` | — | 真实启动 Pi RPC，用 Jev 选择 Skill，并在工具执行前做 gate 判断 |

## Cookbooks 实战指南（18 篇）

`cookbooks/` 覆盖官方全部 18 篇实战指南，命名规则为「官方 slug + `_experiments.ipynb`」。
它们沿用 `patterns_experiments.ipynb` 的结构：逐格定义 state 和 questions，调用真实 TypeSafe API，
再由 Python 完成排序、阈值、重建或函数分派。

| 笔记本 | 官方章节 | 其他 |
|---|---|---|
| `consistency_noul_experiments.ipynb` | [自一致性：Noul](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook) | |
| `consistency_choice_experiments.ipynb` | [自一致性：Choice](https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook) | |
| `parallel_questions_experiments.ipynb` | [并行提问](https://docs.typesafe.ai/cookbooks/parallel_questions) | |
| `rerank_typesafe_experiments.ipynb` | [重排序](https://docs.typesafe.ai/cookbooks/rerank_typesafe) | |
| `semantic_find_experiments.ipynb` | [逐行语义搜索](https://docs.typesafe.ai/cookbooks/semantic_find) | |
| `autoformat_experiments.ipynb` | [结构恢复](https://docs.typesafe.ai/cookbooks/autoformat) | |
| `function_calling_experiments.ipynb` | [函数调用](https://docs.typesafe.ai/cookbooks/function_calling) | |
| `skill_suggestion_experiments.ipynb` | [技能推荐](https://docs.typesafe.ai/cookbooks/skill_suggestion) | |
| `entity_alignment_experiments.ipynb` | [知识图谱实体对齐](https://docs.typesafe.ai/cookbooks/entity_alignment) | |
| `classifying_rag_passages_experiments.ipynb` | [RAG 段落分类](https://docs.typesafe.ai/cookbooks/classifying_rag_passages) | |
| `citation_check_experiments.ipynb` | [引用核查](https://docs.typesafe.ai/cookbooks/citation_check) | |
| `llm_guardrails_experiments.ipynb` | [LLM 防护栏](https://docs.typesafe.ai/cookbooks/llm_guardrails) | |
| `sde_cascade_experiments.ipynb` | [SDE 级联](https://docs.typesafe.ai/cookbooks/sde_cascade) | |
| `date_extraction_experiments.ipynb` | [日期抽取](https://docs.typesafe.ai/cookbooks/date_extraction_cookbook) | |
| `pre_parsed_value_extraction_experiments.ipynb` | [预解析值抽取](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook) | |
| `hierarchical_classification_experiments.ipynb` | [层级分类](https://docs.typesafe.ai/cookbooks/hierarchical_classification) | |
| `autoresearch_feature_discovery_experiments.ipynb` | [自动研究特征发现](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) | |
| `classification_using_confidence_experiments.ipynb` | [基于置信度的分类](https://docs.typesafe.ai/cookbooks/classification_using_confidence) | |

前 8 篇由 `generators/build_cookbook_notebooks.py` 统一生成；其余 10 篇各自独立产出，
其单元格编号不再连续编号，直接按官方 slug 命名。

## 环境

官方 `typesafe-sdk` 要求 **Python ≥ 3.10**；macOS 系统自带 python3 是 3.9，装不上。
推荐直接用一键脚本（优先 uv，自动下载 3.12；没有 uv 时找本机 3.10+，或提示安装 uv）：

```bash
cd notebooks
./setup_env.sh                      # 创建 .venv 并安装 requirements.txt 全部依赖
export TYPESAFE_API_KEY=你的key      # console.typesafe.ai/keys 获取
.venv/bin/jupyter lab patterns_experiments.ipynb
# 或
.venv/bin/jupyter lab primitives_experiments.ipynb
# 或
.venv/bin/jupyter lab confidence_experiments.ipynb
```

- API Key 只从环境变量 `TYPESAFE_API_KEY` 读取，**请勿硬编码进笔记本**。
- Key 无效时笔记本会以「离线示例模式」跑通全部代码路径（输出有 ⚠️ 标注）；
  换上有效 Key 后 Restart & Run All 即得真实实验结果。

## 重新生成

生成器脚本在 `generators/`，从**任意目录**运行都会写回本目录（路径基于脚本自身定位）：

```bash
cd notebooks
.venv/bin/python generators/build_patterns_notebook.py      # 单篇
.venv/bin/python generators/build_cookbook_notebooks.py     # cookbooks/ 前 8 篇
```

| 生成器 | 产出 |
|---|---|
| `build_patterns_notebook.py` | `patterns_experiments.ipynb` |
| `build_primitives_notebook.py` | `primitives_experiments.ipynb` |
| `build_confidence_notebook.py` | `confidence_experiments.ipynb` |
| `build_pi_jev_notebook.py` | `pi_jev_integration_experiments.ipynb` |
| `build_cookbook_notebooks.py` | `cookbooks/` 下 8 篇 |

改完脚本重新生成后需重新执行笔记本。生成会重写 cell `id`，若只想改内容请手工编辑 `.ipynb`。

## 相关目录

- **应用实验**（迷宫 / 移动靶射击 / 浏览器智能体）是可运行的代码工程，不是笔记本，放在
  [`../apps/`](../apps/)。
