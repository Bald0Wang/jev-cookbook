# models/

Laya 权重（约 2.2 GB）**不入库**，本目录只保留推理所需的两个上游模块：

| 文件 | 来源 | 说明 |
|---|---|---|
| `rl_agent_api.py` | ModelScope `convaiinnovations/laya` | `RLAgent`：加载 checkpoint 并执行 `system_one(state, questions)` |
| `rl_common.py` | 同上 | 模型构建、序列拼接、置信度与温度等公共实现 |

`client.py` 通过把本目录加入 `sys.path` 来 `from rl_agent_api import RLAgent`，因此这两个文件必须留在
`models/` 下，checkpoint 目录（含 `model.safetensors` / `rl_agent_config.json` / `encoder/` /
`tokenizer/`）也放在这里。

## 从魔搭社区下载权重

模型仓库：[`convaiinnovations/laya`](https://modelscope.cn/models/convaiinnovations/laya)。仓库公开可下载；
推荐使用 ModelScope Hub CLI。以下命令都从 **Jev Cookbook 仓库根目录**运行，下载位置是
`laya/models/`，与项目的加载路径对应。

### 只下载中文等多语言版（推荐）

先在项目虚拟环境安装 CLI，再下载 `multilingual/` checkpoint：

```powershell
py -3 -m venv laya\.venv
.\laya\.venv\Scripts\python.exe -m pip install --upgrade pip modelscope-hub
.\laya\.venv\Scripts\ms-hub.exe download convaiinnovations/laya --local-dir .\laya\models --include "multilingual/**"
```

下载完成后，权重应位于 `laya/models/multilingual/`。加载时把
`LAYA_MODEL_DIR` 指向这个目录（见 [Laya 加载与服务说明](../README.md#5-本地部署状态)）。

### 下载仓库内全部 checkpoint

不加文件筛选参数时会下载仓库的英文、多语言和 typed-decisions 权重，约 2.2 GB：

```powershell
.\laya\.venv\Scripts\ms-hub.exe download convaiinnovations/laya --local-dir .\laya\models
```

三个 checkpoint 在同一仓库内：仓库根为英文版，`multilingual/`（中文等多语言，默认使用）、
`typed-decisions/` 为子目录。只下中文版本时，目录应为：

```text
laya/models/
├── rl_agent_api.py              # 已入库
├── rl_common.py                 # 已入库
├── multilingual/                # 中文场景使用这一个
│   ├── model.safetensors
│   ├── rl_agent_config.json
│   └── encoder/  tokenizer/
```

下载全部 checkpoint 时，还会有英文版和 typed-decisions：

```text
laya/models/
├── model.safetensors            # 英文版
├── rl_agent_config.json
├── encoder/  tokenizer/
├── rl_agent_api.py              # 已入库
├── rl_common.py                 # 已入库
├── multilingual/
│   ├── model.safetensors
│   ├── rl_agent_config.json
│   └── encoder/  tokenizer/
└── typed-decisions/
    ├── model.safetensors
    ├── rl_agent_config.json
    └── encoder/  tokenizer/
```

可用下面的命令检查多语言权重是否已下载：

```powershell
Test-Path .\laya\models\multilingual\model.safetensors
```

## 校验

权重可用 ModelScope registry 公布的 SHA256 核对（截至 2026-09-23）：

| 文件 | SHA256 |
|---|---|
| `model.safetensors` | `891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c` |
| `multilingual/model.safetensors` | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| `typed-decisions/model.safetensors` | `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e` |

```powershell
Get-FileHash .\laya\models\multilingual\model.safetensors -Algorithm SHA256
```

ModelScope Hub CLI 的安装和下载参数见[官方说明](https://github.com/modelscope/modelscope_hub)。

## 许可

权重与上述两个模块来自 Convai Innovations 的 Laya 项目，Apache-2.0。本目录只做搬运与说明，
未修改上游代码；修改项仅在本仓库 `laya/` 外的 `client.py`（Jev 形状的调用封装）与 `serve.py`
（HTTP 服务）中，见上级目录 README。
