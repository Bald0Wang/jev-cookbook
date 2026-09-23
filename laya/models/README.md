# models/

Laya 权重（约 2.2 GB）**不入库**，本目录只保留推理所需的两个上游模块：

| 文件 | 来源 | 说明 |
|---|---|---|
| `rl_agent_api.py` | ModelScope `convaiinnovations/laya` | `RLAgent`：加载 checkpoint 并执行 `system_one(state, questions)` |
| `rl_common.py` | 同上 | 模型构建、序列拼接、置信度与温度等公共实现 |

`client.py` 通过把本目录加入 `sys.path` 来 `from rl_agent_api import RLAgent`，因此这两个文件必须留在
`models/` 下，checkpoint 目录（含 `model.safetensors` / `rl_agent_config.json` / `encoder/` /
`tokenizer/`）也放在这里。

## 获取权重

```bash
modelscope download --model convaiinnovations/laya --local_dir ./models
```

或用 Hugging Face 镜像：

```bash
huggingface-cli download convaiinnovations/laya --local-dir ./models
```

三个 checkpoint 在同一仓库内：仓库根为英文版，`multilingual/`（中文等多语言，默认使用）、
`typed-decisions/` 为子目录。下载后目录结构应为：

```text
models/
├── model.safetensors            # 英文版（可只下需要的 checkpoint）
├── rl_agent_config.json
├── encoder/  tokenizer/
├── rl_agent_api.py              # 已入库
├── rl_common.py                 # 已入库
├── multilingual/                # 中文场景使用这一个
│   ├── model.safetensors
│   ├── rl_agent_config.json
│   └── encoder/  tokenizer/
└── typed-decisions/
    └── ...
```

## 校验

权重可用 ModelScope registry 公布的 SHA256 核对（截至 2026-09-23）：

| 文件 | SHA256 |
|---|---|
| `model.safetensors` | `891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c` |
| `multilingual/model.safetensors` | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| `typed-decisions/model.safetensors` | `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e` |

```bash
shasum -a 256 models/multilingual/model.safetensors
```

## 许可

权重与上述两个模块来自 Convai Innovations 的 Laya 项目，Apache-2.0。本目录只做搬运与说明，
未修改上游代码；修改项仅在本仓库 `laya/` 外的 `client.py`（Jev 形状的调用封装）与 `serve.py`
（HTTP 服务）中，见上级目录 README。
