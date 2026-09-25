# 06 · 模型评测

第六章回答一个问题：**怎么公平地评测一个判断模型？** 本章包含三个部分，全部来自 [Micheal024](https://github.com/Micheal024) 的评测工作（[PR #6](https://github.com/datawhalechina/jev-cookbook/pull/6) 及其后续演进，按原样收录）：

| 内容 | 说明 |
|---|---|
| [`01_模型评测.ipynb`](01_模型评测.ipynb) | 教程册：Laya vs Jev，231 道 JevBench 公开题四维对比（准确率 / 多数类底线 / Brier / ECE）；评测纪律——无重试、无回退、不修补答案、预算记账 |
| [`benchmark/`](benchmark/) | 上一册的配套套件：runner 账本、Laya 本地与 Jev 两个适配器、JevBench 公开题集（`tasks/`，本地再生）与预置演示产物（`runs/notebook-demo/`） |
| [`llm_eval/`](llm_eval/) | 通用多供应商评测框架：`deepseek / doubao / glm / moonshot / qwen / stepfun / xiaomi / openai_compat / typesafe / mock` 等十余个适配器，配套 [`jevbench_intro.ipynb`](llm_eval/notebooks/jevbench_intro.ipynb) 入门教程与 7 个运行/转换脚本 |

**运行环境**：`benchmark/requirements.txt`；题目集由 `benchmark/scripts/fetch_public_tasks.sh` + `convert_jevbench.py` 生成 `tasks/public_all.jsonl`（gitignore，本地再生）。无 Laya 服务 / 无 Key 时，分析部分使用仓库自带演示产物照样可读。

**与教程的关系**：第一章讲"概率为什么可信"（校准），本章给出把这话量化检验的完整方法——Brier 与 ECE 怎么算、底线（多数类准确率）为什么必须报、成本与延迟怎么记账。第十章微调出的本地模型，就用本章的框架来验收。
