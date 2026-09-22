# Notebooks

- `patterns_experiments.ipynb` — 《TypeSafe 架构模式实验》：对应官方文档
  [Patterns](https://docs.typesafe.ai/patterns) 章节的可运行实验（推测性扇出 / 置信度门控路由 /
  复合评分 / 意图路由），全部使用中文场景与中文提示词。
- `primitives_experiments.ipynb` — 《TypeSafe 原语实验》：对应官方文档
  [Primitives](https://docs.typesafe.ai/primitives) 章节的可运行实验（原语概览 / Choice / Score / Noul /
  进阶：结构化），全部使用中文场景与中文提示词。包含文档原例与中文版的实测对比。
- `confidence_experiments.ipynb` — 《TypeSafe 置信度实验》：对应官方文档
  [Confidence](https://docs.typesafe.ai/confidence) 章节的可运行实验（confidence 本质 / 三路分流 /
  风险调整阈值 / 措辞影响 / 分类层级 fallback），借鉴 cookbook 的核心思想：信心高报细类、信心低报粗类。

## 环境（重要）

官方 `typesafe-sdk` 要求 **Python ≥ 3.10**；macOS 系统自带 python3 是 3.9，装不上。
推荐直接用一键脚本（优先 uv，自动下载 3.12；没有 uv 时找本机 3.10+，或提示安装 uv）：

```bash
./setup_env.sh          # 创建 .venv 并安装 requirements.txt 全部依赖
export TYPESAFE_API_KEY=你的key     # console.typesafe.ai/keys 获取
.venv/bin/jupyter lab patterns_experiments.ipynb
# 或
.venv/bin/jupyter lab primitives_experiments.ipynb
# 或
.venv/bin/jupyter lab confidence_experiments.ipynb
```

- API Key 只从环境变量 `TYPESAFE_API_KEY` 读取，**请勿硬编码进笔记本**。
- Key 无效时笔记本会以「离线示例模式」跑通全部代码路径（输出有 ⚠️ 标注）；
  换上有效 Key 后 Restart & Run All 即得真实实验结果。

- `build_patterns_notebook.py` / `build_primitives_notebook.py` / `build_confidence_notebook.py` —
  生成对应笔记本的脚本（`.venv/bin/python` 运行），改完脚本重新生成后需重新执行。
- `requirements.txt` / `setup_env.sh` — 环境依赖清单与一键创建脚本。
