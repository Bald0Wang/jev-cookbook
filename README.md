# jev-docs-zh — Jev 官方文档中文翻译

> **这是 [TypeSafe AI](https://www.typesafe.ai) 旗下 **Jev 模型**的官方使用文档的中文翻译项目。**
> 原文档：**https://docs.typesafe.ai**
>
> **This repository is a Chinese translation of the official documentation for Jev, the
> System One model by TypeSafe AI.** Original docs: https://docs.typesafe.ai
>
> ⚠️ 本项目为**非官方**社区翻译，仅供学习参考。文档内容与商标的版权归原作者
> TypeSafe AI 所有；翻译如有疏漏，以[英文原版](https://docs.typesafe.ai)为准。
> This is an **unofficial** community translation. All original content and trademarks
> belong to TypeSafe AI. In case of discrepancies, refer to the
> [official English documentation](https://docs.typesafe.ai).

## 在线阅读 / Read online

- **中文站（本仓库自动部署）：https://bald0wang.github.io/jev-docs-zh/**
- 原文（英文官方）：https://docs.typesafe.ai
- 本仓库 `dist/` 目录内含构建好的静态站点，可用任意静态服务器直接托管：

```bash
cd dist
python3 -m http.server 8137
# 打开 http://localhost:8137/
```

## 关于 Jev / About Jev

Jev 是 TypeSafe AI 的旗舰模型，也是首个 **System One 模型**：向它发送**状态（state）**和
**类型化问题**（Choice / Score / Noul 三种原语），它返回带有**概率**与**置信度**的结构化答案，
供代码直接消费——不做文本生成，无需解析。

Jev is TypeSafe AI's flagship model and the first **System One model**: send it **state** and
**typed questions** (the Choice / Score / Noul primitives), and it returns **structured answers
with probabilities and confidence** that your code can consume directly.

## 项目结构

```
jev-docs-zh/
├── content/          # 109 页中文翻译（路径与原站 URL 一一对应）
├── assets/           # 站点样式 / 前端脚本 / 原站图片（已本地化）
├── build.py          # 静态站点生成器（仅 Python 标准库，python3 build.py 一键构建）
├── anchor_maps.json  # 跨页锚点的「原文↔译文」映射（构建用数据）
├── dist/             # 构建产物：完整可部署的静态站点
├── notebooks/        # 章节实验笔记本（理论 + 真实 API 实验）+ generators/ 生成器脚本
├── apps/             # Jev 应用实验代码（迷宫 / 移动靶射击 / 浏览器智能体）
└── laya/             # Laya（开源 System 1 决策模型）介绍、Jev 对比与本地调用
```

翻译覆盖原站全部 109 个页面：快速开始、核心概念（System One / State）、三种原语
（Choice / Score / Noul）、置信度、架构模式、18 篇实战指南（Cookbooks）、HTTP API 参考、
Python / JavaScript SDK 全量 API 文档等。

### 章节实验笔记本

`notebooks/` 下每个章节一个笔记本，走「生成器脚本 → 生成 → 执行」三段式，配中文场景实验。
覆盖入门、概念、原语、置信度、架构模式、Pi + Jev、DSH × Jev 学习案例，以及官方
18 篇实战指南。各章状态见 [Notebook 索引](notebooks/README.md)。生成器在 `notebooks/generators/`。
制作规范见 [AGENT.md](AGENT.md)。

### 应用实验

`apps/` 收录 Jev 应用代码；DSH × Jev 另配有从原语到完整任务的中文学习笔记：

| 项目 | 任务 | 结果 |
|---|---|---|
| [`maze/`](apps/maze/) | 迷宫中只看 5×5 局部窗口判断方向 | 50×50 出口 225 次尝试（Jev 2,738 次） |
| [`predict_position/`](apps/predict_position/) | ViZDoom 移动靶射击 | 命中 27/128（Jev 11/128） |
| [`browser-use/`](apps/browser-use/) | Jev Ultrafast 浏览器智能体 | Google Flights 中位 7.07 s（原版 9.45 s） |

新增案例：**[DSH × Jev 决策协作](apps/dsh-jev-decision/docs/LEARNING-CASE.md)**，包含插件、模式、真实成功与失败证据、复现步骤和 [Notebook](notebooks/dsh_jev_decision_experiments.ipynb)。

前三个项目各带可播放的 `final.html` 动态回放，详见 [`apps/README.md`](apps/README.md)。

### Laya：开源 System 1 决策模型

`laya/` 收录 Convai Innovations 的 [Laya](https://github.com/NandhaKishorM/laya) 介绍：
它用与 Jev 相同的 `state + questions` 接口和 Choice / Score / Noul 三类问题，但权重开放
（Apache-2.0，421M / 322M 参数，ModernBERT / mmBERT 编码器），可在本机或端侧运行。
该目录含与 Jev 的异同对照、其他开源同类模型的参数与架构区别、微调与数据构建方案，
以及一个 Jev 形状的本地调用封装（`client.py`）与 HTTP 服务（`serve.py`，暴露
`POST /v1/systemone`）。权重约 2.2 GB 不入库，获取方式见 [`laya/models/README.md`](laya/models/README.md)。

## 重新构建

```bash
python3 build.py     # 生成 dist/，并自动校验内链与资源
```

不需要网络与第三方依赖。功能：Markdown 渲染、Mintlify 组件转换（提示框 / 参数卡片 /
标签页 / 折叠面板 / 卡片网格 / SDK 签名高亮块）、`TypesafeExample` 示例的 Playground
深链（lz-string 压缩，与原站行为一致）、中文标题锚点自动生成与跨页改写、侧边栏导航、
全文搜索（Ctrl/⌘+K）、亮/暗主题、mermaid 图渲染（离线自动降级为源码）。

## 翻译约定

- 产品与术语保留英文：TypeSafe、Jev、Choice、Score、Noul、System One、Playground、RAG、BM25 等
- 常用译名：state→状态、question→问题、answer→答案、confidence→置信度、
  probability→概率、primitives→原语、calibrated→校准、cookbook→实战指南、guardrails→防护栏
- 代码块、字段名、API 签名、URL 一律不译

## 同步与维护

原站内容更新后，可重新抓取变更页面的 `.md`（Mintlify 站点支持 `任意路径.md`）替换
`content/` 中对应文件，再运行 `python3 build.py` 重新生成。

## 授权说明 / License note

译文基于官方文档翻译整理，版权归原作者 TypeSafe AI 所有。若版权方提出要求，本项目将
配合下架。本仓库不包含原站英文文档的存档；如需阅读原文请访问
[docs.typesafe.ai](https://docs.typesafe.ai)。

The translation is derived from the official documentation. Copyright of the original
content belongs to TypeSafe AI. This repository does not redistribute the English
original; please read it at [docs.typesafe.ai](https://docs.typesafe.ai).
