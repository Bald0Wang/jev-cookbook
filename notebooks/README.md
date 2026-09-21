# Notebooks

- `patterns_experiments.ipynb` — 《TypeSafe 架构模式实验》：对应官方文档
  [Patterns](https://docs.typesafe.ai/patterns) 章节的可运行实验（推测性扇出 / 置信度门控路由 /
  复合评分 / 意图路由），全部使用中文场景与中文提示词。

## 环境（重要）

官方 `typesafe-sdk` 要求 **Python ≥ 3.10**；macOS 系统自带 python3 是 3.9，装不上。
推荐直接用一键脚本（优先 uv，自动下载 3.12；没有 uv 时找本机 3.10+，或提示安装 uv）：

```bash
./setup_env.sh          # 创建 .venv 并安装 requirements.txt 全部依赖
export TYPESAFE_API_KEY=你的key     # console.typesafe.ai/keys 获取
.venv/bin/jupyter lab patterns_experiments.ipynb
```

- API Key 只从环境变量 `TYPESAFE_API_KEY` 读取，**请勿硬编码进笔记本**。
- Key 无效时笔记本会以「离线示例模式」跑通全部代码路径（输出有 ⚠️ 标注）；
  换上有效 Key 后 Restart & Run All 即得真实实验结果。

- `build_patterns_notebook.py` — 生成本笔记本的脚本（`.venv/bin/python` 运行），
  改完脚本重新生成后需重新执行。
- `requirements.txt` / `setup_env.sh` — 环境依赖清单与一键创建脚本。
