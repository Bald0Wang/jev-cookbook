# 笔记本维护与验证

阅读入口和环境配置见 [README](README.md)，制作规范见 [项目手册](../AGENT.md)。
本页集中记录生成、检查和待完成的真实实验，避免在章节目录中重复说明。

## 重新生成

生成器位于 `generators/`，输出路径基于脚本位置，可以从任意工作目录调用。
以下命令以 `notebooks/` 为工作目录，使用 README 中配置的环境：

```bash
.venv/bin/python generators/build_introduction_notebook.py # 单章示例（合并版介绍章）
.venv/bin/python generators/build_foundations_notebooks.py # 入门与概念七章
```

| 生成器 | 产出 |
|---|---|
| [build_introduction_notebook.py](generators/build_introduction_notebook.py) | 简介 |
| [build_system_one_notebook.py](generators/build_system_one_notebook.py) | System One |
| [build_state_notebook.py](generators/build_state_notebook.py) | 状态 |
| [build_primitives_notebook.py](generators/build_primitives_notebook.py) | 原语 |
| [build_confidence_notebook.py](generators/build_confidence_notebook.py) | 置信度 |
| [build_patterns_notebook.py](generators/build_patterns_notebook.py) | 架构模式 |
| [build_build_with_typesafe_notebook.py](generators/build_build_with_typesafe_notebook.py) | 应用构建 |
| [build_pi_jev_notebook.py](generators/build_pi_jev_notebook.py) | Pi + Jev 集成 |
| [build_cookbook_notebooks.py](generators/build_cookbook_notebooks.py) | `04_实战指南/` 前 8 篇（含知识补充注入；后 10 篇独立成稿于同目录） |
| 第六章 `06_模型评测/` | 来自 PR #6（Micheal024）：正文在 `laya/benchmark/notebooks/laya_vs_jev.ipynb`，章节副本含系列头；`tasks/public_all.jsonl` 为本地再生数据（gitignore，脚本见 `laya/benchmark/scripts/`） |
| [build_foundations_notebooks.py](generators/build_foundations_notebooks.py) | 认识 Jev（合并四章）、System One、状态、应用构建 |

修改生成器 → 重新生成 → 执行验证，不直接修改 `.ipynb`。生成会覆盖已有输出，历史实验请先另存。
仅修改 Notebook 不需要重建文档站点。

## 入门与概念章节验证

以下执行器和检查覆盖上述七章。公共准备代码由 [notebook_support.py](generators/notebook_support.py) 和 [模板](generators/templates/tutorial.ipynb) 生成，每本 Notebook 均自带完整代码，可独立运行。
依赖版本范围保存在 [constraints-foundations.txt](generators/constraints-foundations.txt)，安装方式统一见 README。

### 离线检查

```bash
.venv/bin/python generators/execute_foundations_notebooks.py --mode offline
.venv/bin/python -m unittest discover -s tests -p 'test_foundations_notebooks.py' -v
```

执行器逐章启动全新内核，在空工作目录运行，并在离线模式中移除 API 密钥。
离线输出写入 [validation/offline_previews](validation/offline_previews/)，正式文件保留未执行代码。
执行记录见 [foundations-offline.json](validation/foundations-offline.json)。预览中的数值均为人工示例，不能证明模型表现。

已完成的本地检查：

- 七章共 176 个代码单元执行通过，未调用远程 API。
- 四项检查通过，覆盖 27 个业务请求的 SDK 序列化和响应解析、鉴权失败、服务端失败、结构及密钥导出检查。
- 应用构建实验的八条路径均被人工数据覆盖，真实分支覆盖仍待观察。

### 真实执行

先配置启动进程的 `TYPESAFE_API_KEY` 环境变量，然后选择单章试跑：

```bash
.venv/bin/python generators/execute_foundations_notebooks.py --mode live --chapter introduction
```

需要完整验收时，执行七章：

```bash
.venv/bin/python generators/execute_foundations_notebooks.py --mode live
```

一次完整运行包含 **27 次业务请求 + 7 次连通性请求**，不自动重试。全量运行会再次执行已试跑的章节。
默认模型配置为 `jev-1.13.0`，可通过 `TYPESAFE_DEFAULT_MODEL` 更换；以实际响应和末尾执行记录为准。

执行器默认 `live`；缺少密钥会在启动内核前停止，也不会自动读取 `.env`。
真实执行失败即停止，不能以离线答案填补。交互教学中的 `auto` 模式仅对缺密钥或 401 显式回退，不用于验收。

成功执行会将真实输出写回正式 Notebook，生成 `validation/foundations-live.json`；单章报告名带章节后缀。
执行器检查输出错误、调用来源和密钥泄漏，语义结论仍需逐格人工核对。

## 真实 API 验收记录

**当前七章均待真实 API 验收。** 离线执行完成不表示真实模型实验已通过。

| 章节 | 待核对的行为 | 当前记录 |
|---|---|---|
| 简介 | 三个维度与权重组合是否可解释 | 待真实运行 |
| 快速开始 | 三种原语与量表是否匹配 | 待真实运行 |
| AI 入门 | 明确请求、否定与模糊措辞的实际概率 | 待真实运行；三例不构成校准评测 |
| System One | 退款三问、组合路径、改 ID 的实际差值 | 待真实运行 |
| 状态 | 等事实格式对照；缺事实与有政策的区别 | 待真实运行 |
| 应用构建 | 八条路径、补充示例、工具单位漏检 | 待真实运行；不假设分支必被命中 |
| 应用场景 | 相关性排序、空结果出口、过度泛化论断 | 待真实运行 |

每个发现记录日期、实际模型、state、问题版本、输出、解释及是否要修改问题；各章末尾 JSON 保留实际调用来源。

若 `COVERAGE.missing` 仍有分支：先写下预期与理由，再追加几句试句，保留每次返回；仍未出现就记为“本次样本未观察到”。
修改措辞或阈值后需重新生成并执行。按返回结果挑选的试句不能再作为无偏准确率测试集；准确率、漏检和覆盖率需要独立标注的留出数据。

正式验收需同时满足：真实调用数为正、离线调用数和错误输出为零，输出与解释一致，公开文件不含密钥。

## 贡献说明

简介、快速开始、AI 入门、System One、状态、应用构建及应用场景七章由**荞麦**编写，来源于 `jev-cookbook-qiaomai`。
合入后统一使用本仓库的目录与章节样式，保留原有教学案例、学习目标、练习和来源引用。
