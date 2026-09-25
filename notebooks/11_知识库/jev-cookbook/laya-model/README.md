# Laya：模型介绍、Jev 对比与本地调用

资料整理：2026-09-23。模型说明以 [ModelScope 模型卡](https://modelscope.cn/models/convaiinnovations/laya) 和 [Laya 源码仓库](https://github.com/NandhaKishorM/laya) 为主；横向评测采用当前知识库里的 JevBench v1.2。用户给的三篇公众号文章已从本地知识库 `../19-wechat-laya-architecture/`、`20-wechat-laya-oss-release/`、`21-wechat-laya-hf-trending/` 读取，并在文中区分作者主张、社区设备实测和独立基准结果。

## 1. Laya 是什么

Laya 是 Convai Innovations 发布的开源、非自回归类型化决策模型。输入由两部分组成：一份共享的 `state`，以及一个或多个带类型的问题。模型一次前向计算并行回答 `choice`、`score`、`noul`，返回概率分布和预测值，不生成一段文本供程序解析。

这与“把普通聊天模型的输出限制成 JSON”不是同一做法。Laya 的输出头直接给运行时提供的候选项打分：候选项前放置专属 `[MASK]` 标记，在标记位置读取分数，对同一问题的候选项做 softmax。增加一套业务标签通常只需在请求中定义 schema，不需要为每个标签新建分类头或重新训练。

ModelScope 当前模型卡标注 Apache-2.0、PyTorch、Safetensors，仓库约 2.37 GB，三个 checkpoint 合并在同一个仓库中。英语基础版约 4.21 亿参数；另有多语言版和面向四种类型化决策工作流微调的版本。

### Checkpoint 怎么选

| Checkpoint | 参数 / 主干 | 上下文上限（默认） | 适合用途 |
|---|---|---:|---|
| `laya/models/` | 4.21 亿；ModernBERT-large + 决策头 | 512 | 英语输入 |
| `laya/models/multilingual/` | 3.22 亿；mmBERT-base（22 层）+ 决策头 | 1,024；模型卡称骨干可到 8,192 | 中文和多语言，本项目默认使用 |
| `laya/models/typed-decisions/` | 4.21 亿；ModernBERT-large + 决策头 | 1,024 | 模型卡所述四种决策工作流的专门微调 |

注意，`typed-decisions` 不是通用能力更强的“Pro 版”。模型卡报告它在特定四类工作流上的微调结果；基础英文和多语言 checkpoint 在同一 typed-decisions 零样本集上的准确率分别为 0.362 和 0.342，低于多数类基线 0.461。应按自己的任务验证并校准，而不是直接把模型卡的微调分数当作开箱即用能力。

模型卡对 multilingual checkpoint 的跨语言测试称，在 51 种共享测试语言中有 45 种超过随机基线三倍以上；这不是“所有语言都能可靠分类”的保证。中文等非英文输入应选 multilingual 权重，再用目标领域样例实测。

## 2. 与 Jev 的共同点和区别

| 维度 | 共同点 | Jev | Laya |
|---|---|---|---|
| 编程接口 | `state + questions`；问题按 ID 对齐；三类 typed decisions | `Choice`、`Score`、`Noul`，托管 API / SDK | 同样的三类问题；开源权重，可在本机执行 |
| 输出 | 不靠自由文本生成和 JSON 解析；可取完整概率分布 | 返回概率、选择或期望分数；云端处理 | 候选 marker logits 经 softmax/sigmoid，返回概率和 typed answer |
| 多问题调用 | 代码管理流程，模型只回答语义问题；一次请求中并行处理多个独立问题 | 服务侧并行处理 | 一个模型前向中打包同一 state 的多个问题 |
| 模型权重 / 架构 | 专用决策模型，不是传统聊天模型 API 的 JSON 包装 | 商业闭源；公开资料未给出参数量和完整拓扑。知识库研究材料记录其为 Transformer-based，但层数、宽度、参数数目和 sampler 细节未公开 | Apache-2.0 开放权重；公开 ModernBERT / mmBERT 主干和两层决策头等结构 |
| 语言与上下文 | 都能接收文本或结构化 state | 以托管模型支持范围为准 | 英文根模型不适合非拉丁文字；中文应显式使用 multilingual checkpoint。英文默认 512 token，多语言默认 1,024 token |
| 运行与成本 | 低延迟判断可放进程序热路径 | API key、网络和服务价格 | 本地部署，无逐请求 API 费用；自己承担机器、常驻内存和维护 |
| 可靠性边界 | 概率可用于阈值路由和人工复核 | 类型正确不等于语义正确 | 同样如此；非生成式只消除了自由文本格式错误，不会消除误分类。概率需用目标领域验证、校准 |

两者的核心相同点是**决策接口与程序流程分离**。核心区别不是“一个聪明、一个小”，而是开放程度和实现边界：Jev 是托管服务，具体模型规模和架构没有公开；Laya 的模型权重、编码器和决策头都可本地检查、微调与部署，但基础 checkpoint 的零样本能力受领域、语言和选项数影响。

### 性能数字怎么读

- ModelScope 模型卡报告：multilingual checkpoint 在 Tesla T4 上单问题 32.8 ms，10 题批量 72.3 ms。该数值来自模型方的测量，属于预加载后的 GPU 推理结果。
- 知识库 JevBench v1.2：Laya 综合分 70.1，Jev 1.13.0 为 75.4，openJev Verdict 1.4 为 72.5。Laya 这一行使用英文 checkpoint，在 Ryzen 5 3600 四线程 CPU 上测量，原始 p50 0.79 秒；综合分还计入校准、速度和估算成本，不是准确率。
- 模型卡自己的 Jev 对比使用不同来源的 Jev 测量，不同样本与提示词；模型卡明确说明 Jev 数值没有由作者在同一运行中复测。不要把“快 7.8 倍”写成同条件结论，也不要拿 T4 的 32.8 ms 与 CPU JevBench 的整请求延迟直接相除。

## 3. 其他开源 Jev-like 模型

参数量不是架构。下表按决策计算方式区分“编码器 + 决策头”“生成式骨干 + 指针 / 读出头”和“借用分类模型”；数字来自知识库收录的模型说明与评测快照（2026-09-20 至 2026-09-23），研究预览、作者测量和统一评测应分开看。

| 模型 / 代表参数量 | 架构与决策路径 | 与 Laya 的差别 |
|---|---|---|
| **Laya**：421M 英文 / typed；322M multilingual | ModernBERT-large 或 mmBERT-base 双向编码器 + 两层 Transformer 决策头；运行时 `[MASK]` 选项标记并行打分 | 约 0.3–0.4B 的专用非自回归决策架构；三种问题类型在一次前向中处理 |
| **openJev Verdict**：151M | ModernBERT-base 级编码器 + RLCD 决策头；非自回归概率输出 | 参数更少，仍是 encoder + decision head；知识库 JevBench 版本 1.4 综合分 72.5，但该值包含基准中的校准、速度、成本项 |
| **NanoJev**：0.6B | Qwen3-0.6B 骨干 + decision heads；Choice 用集合注意力和 softmax，Boolean 用 sigmoid，Score 输出有序档位分布；训练目标面向多任务游戏决策 | Qwen decoder 骨干比 Laya encoder 更大，训练目标与公开示例更集中在游戏策略；权重、训练代码和数据均随项目发布 |
| **kev**：0.5B、0.6B、4B、8B | Qwen2.5 / Qwen3 骨干 + LoRA + pointer head，直接读选项指针概率，不需要逐 token 生成答案 | 可换不同尺寸的生成式骨干；0.5B 为公开版，其余在当前评测说明中标为 research preview |
| **Decider**：2B | Qwen3.5-2B-Base 微调 + 一次前向的 typed-decision readout | 规模大于 Laya；同属一次性 typed-decision 输出，但模型主干仍是生成式 decoder 家族 |
| **LitJev**：27B | Qwen3.8-27B 语言模型读取候选答案 token logits；无专门训练也可跑 Jev-like schema | 使用大型生成式语言骨干，显存和延迟显著更高；知识库评测记录其默认概率未校准 |
| **GLiNER2.5 small / multi**：74M / 287M | 面向分类、实体抽取等任务的 encoder 分类模型；按标签映射做单标签 softmax | 是相邻的轻量分类基线，不是完整 Jev 原语复刻；choice 可映射，score / noul 需要额外约定与输出转换 |

另外，`laya-mlx` 是把同一 Laya checkpoint 移植到 Apple MLX 的运行时，不是新模型或新参数规模。知识库收录的 CPU/GPU 数值来自各作者和不同设备，适合选候选，不构成统一榜单；选型时应统一 state、schema、切分集、校准集、硬件和并发重新比较。

### 三篇本地归档文章的补充与证据边界

- 《Laya 开源：比Jev快4倍！421M 参数，33 毫秒完成 System 1 决策》（`../19-wechat-laya-architecture/article.md`）解释了 ModernBERT-large、`[MASK]` 候选标记、双层决策头与 RLCD 训练。标题和文中的“快 4 倍”是作者按不同来源延迟作出的宣传性比较，不是同一硬件、同一网络路径的复现实验。
- 《4.6k star，开源版Jev悄悄发布》（`../20-wechat-laya-oss-release/article.md`）引用的模型卡宣传对比包括快 7.8 倍、准确率高 3.9 个百分点、校准好 3 倍；同文也说明 Jev 数据来自第三方、不是同一环境复测。限制数据包括：英语 / 多语言基础 checkpoint 在 typed-decisions 零样本集准确率 0.362 / 0.342，低于多数类基线 0.461；微调后 0.766 来自该基准的训练切分；Banking77 高基数分类 Jev 0.870、Laya 0.425；软分布匹配 Jev 0.580、Laya 0.471；英语 checkpoint 在高棉语曾报告 0 准确率、0.952 置信度。应把这些数看成特定数据与测量口径下的风险提示，而不是统一排名。
- 《「开源版Jev」登上Hugging Face热榜第一》（`../21-wechat-laya-hf-trending/article.md`）汇总了 `laya-mlx` 社区报告：设备内存约 1 GB；M3 Max 贪吃蛇最高 60 次决策 / 秒；Core ML 功耗最高降低 64%；另一组蛇游戏报告 Laya 86.5 次 / 秒、P50 9 ms，Jev 3.2 次 / 秒、API 往返约 317 ms；M5 Pro 中位数 15.3 ms 对 298.1 ms；俄罗斯方块约 11 倍。这些是特定硬件、任务和 MLX / Core ML 运行时的社区结果；不能直接等同于本项目 PyTorch MPS 服务的吞吐，也不能视为同模型同部署条件的质量比较。

## 4. 微调与数据构建

当前工作区含 Laya checkpoint 与推理/部分数据编码代码，但没有完整 trainer、数据集和可复现训练清单。若要做领域适配，先按 [《Laya 微调与数据构建方案》](FINETUNING.md) 建立来源分组、独立 gold、train/dev/calibration/test 与 OOD 数据，再从冻结 encoder 的头部微调基线开始；文档也说明了与上游 RLCD 路线的区别和复现缺项。本机 MPS 只验证过推理，未验证训练。

## 5. 本地部署状态

ModelScope 的约 2.2 GB checkpoint 不放在此文档包中。先从 [ModelScope 模型仓库](https://modelscope.cn/models/convaiinnovations/laya) 下载 multilingual checkpoint，再把环境变量指向其本地目录：

```text
laya/models/model.safetensors                         # 英文，约 803 MiB
laya/models/multilingual/model.safetensors            # 多语言，约 614 MiB
laya/models/typed-decisions/model.safetensors         # 微调版，约 781 MiB
```

本目录中的 `client.py` 在已下载的 checkpoint 上提供 `LayaClient.system_one(...)`；`serve.py` 在本机提供兼容 Jev 的 `POST /v1/systemone`。默认加载 multilingual checkpoint，且只监听 `127.0.0.1`。

安装项目内依赖并在 Apple Silicon 上显式使用 PyTorch MPS：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
USE_TF=0 LAYA_DEVICE=mps LAYA_MODEL_DIR="/absolute/path/to/laya/multilingual" \
  PYTHONPATH=code .venv/bin/python -m laya.serve --host 127.0.0.1 --port 8811
```

`LAYA_DEVICE` 可设置为 `mps`、`cuda` 或 `cpu`；未设置时按 CUDA、Apple MPS、CPU 的顺序选择。首次启动会把整份权重载入内存，后续请求复用该实例。健康检查：`GET http://127.0.0.1:8811/healthz`；模型列表：`GET /v1/models`。

本次已在 Mac 上通过 PyTorch MPS 启动服务；`/healthz` 返回 `{"status":"ok","model":"laya-multilingual","device":"mps"}`。并以中文账单工单请求同时调用 `choice`、`noul`、`score`，得到“billing”、`0.7106`、`1.5505`。这是一次 smoke request，确认接口和 MPS 路径可用，不代表准确率、校准质量或性能基准。

### Windows 启动（PowerShell）

Windows 不使用 Apple MPS。服务会优先选择可用的 CUDA，再回退到 CPU；需要 CUDA 时，先按显卡驱动和目标 CUDA 版本安装兼容的 PyTorch CUDA wheel，参考 [PyTorch 安装选择器](https://pytorch.org/get-started/locally/)。

解压知识库后，在 laya-model 目录打开 PowerShell：

```powershell
Set-Location "C:\path\to\jev-cookbook\laya-model"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt

$env:USE_TF = "0"
$env:LAYA_MODEL_DIR = "D:\path\to\laya\models\multilingual"
Remove-Item Env:LAYA_DEVICE -ErrorAction SilentlyContinue # 自动选择 CUDA 或 CPU
.\.venv\Scripts\python.exe -c "import torch; print('CUDA available:', torch.cuda.is_available())"
$env:PYTHONPATH = ".\code"
.\.venv\Scripts\python.exe -m laya.serve --host 127.0.0.1 --port 8811
```

如需固定设备，将自动选择那行替换为 `$env:LAYA_DEVICE = "cuda"` 或 `$env:LAYA_DEVICE = "cpu"`。只有 CUDA 版 PyTorch 且 `torch.cuda.is_available()` 返回 `True` 时才能指定 `cuda`；Windows 不支持 `mps`。模型权重目录应包含 `model.safetensors`、`rl_agent_config.json`、`encoder` 和 `tokenizer`。启动后沿用同一个 `/healthz` 和 `/v1/systemone` 接口。

### 和 Jev 相同形状的请求

```bash
curl http://127.0.0.1:8811/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "laya-multilingual",
    "state": {"subject": "重复扣款", "body": "三月账单扣了两次，请退回多收的款项。"},
    "questions": {
      "department": {
        "type": "choice",
        "instructions": "这张工单应分配给哪个部门？",
        "criteria": {"billing": "付款、账单、退款", "technical": "产品故障", "other": "其他问题"}
      },
      "urgent": {
        "type": "noul",
        "instructions": "用户是否明确要求尽快处理？",
        "criteria": {"true": "明确要求立刻处理", "false": "没有时间要求"}
      },
      "severity": {
        "type": "score",
        "instructions": "评估问题紧急程度。",
        "criteria": ["低：可等待", "中：近期处理", "高：阻塞或有明确期限"]
      }
    }
  }'
```

响应沿用 `model / answers / usage` 顶层字段，`answers` 以问题 ID 为键：

```json
{
  "model": "laya-multilingual",
  "answers": {
    "department": {"type": "choice", "choice": "billing", "probabilities": {"billing": 0.994, "technical": 0.0023, "other": 0.0036}, "confidence": 0.9631},
    "urgent": {"type": "noul", "noul": 0.7106},
    "severity": {"type": "score", "score": 1.5505, "legend": {"0": "低：可等待", "1": "中：近期处理", "2": "高：阻塞或有明确期限"}, "probabilities": {"0": 0.0078, "1": 0.4339, "2": 0.5583}, "confidence": 0.3396}
  },
  "usage": {"input_tokens": 196, "output_tokens": 0}
}
```

示例响应来自上述 MPS smoke request。正式使用时仍要在自己的校准集上测量 ECE / Brier 等指标。高风险动作应由确定性业务规则和人工复核兜底。服务默认无鉴权并绑定 loopback；不要直接改成 `0.0.0.0` 暴露给局域网或公网。

## 6. 参考与证据边界

- [ModelScope：convaiinnovations/laya](https://modelscope.cn/models/convaiinnovations/laya) — checkpoint、参数、许可、架构、接口示例及作者测量。
- [Laya 源码与基准说明](https://github.com/NandhaKishorM/laya) — 推理和训练实现、作者给出的限制。
- [Jev API 文档](https://docs.typesafe.ai/api) — `POST /v1/systemone` 请求结构。
- [NanoJev](https://github.com/TianyuCodings/NanoJev)、[kev](https://github.com/jaredpalmer/kev)、[openJev Verdict 2.0](https://github.com/Heman10x-NGU/openJev-verdict-2.0)、[Decider](https://github.com/Mapika/decider)、[LitJev](https://github.com/zhengxuyu/litjev) — 其他开源模型与实现。
- 本地评测：[JevBench v1.2](../15-jevbench/RESULTS-v1.2.md) 与 [测量方法 / 系统映射](../15-jevbench/docs/v1.2-additions.md)。分数为综合评分，仓库内备注区分硬件、来源、研究预览与估算成本。
- 三篇公众号文章的用户原始链接：[ModelScope 社区的架构介绍](https://mp.weixin.qq.com/s/9SJf3nhK25rZcZwQNTg7mw)、[PaperAgent 的开源发布与限制梳理](https://mp.weixin.qq.com/s/KgBXK1PEuswkfk4xXcrN0A)、[机器之心的社区热度及 Apple 运行时测试](https://mp.weixin.qq.com/s/39esHoH-GVpfdXjunng1oA)。正文快照保存在 Jev 知识库的 `19`、`20`、`21` 目录；上述“本地归档文章”小节对它们作了来源归属和证据级别说明。
