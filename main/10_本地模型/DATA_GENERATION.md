# Laya 微调数据构造指南

本指南从一份任务规范出发，使用 DeepSeek API 并发生成中文或其他语言的 Laya JSONL **候选数据**，检查标签分布并导出人工审核表。配套 Notebook：[`notebooks/zh_dataset_construction.ipynb`](notebooks/zh_dataset_construction.ipynb)。

生成器负责构造 state 和伪标签，并验证 JSON 结构、题型和标签范围；它不能证明内容真实、标签正确或数据适合训练。新数据始终保留 `train_candidate` / `needs_human_review`，审核通过后再由团队另行标记和划分。

## 1. 准备项目和任务规范

先从 [`data_generation/spec.example.json`](data_generation/spec.example.json) 复制任务规范。它演示客服路由场景；改成自己的任务时，至少逐项审定：

| 配置 | 要写清楚什么 |
|---|---|
| `task_family`、`policy_version` | 任务族和规则版本；规则有变化就更新版本 |
| `task_description` | 在什么时点，根据哪些信息做什么决定 |
| `state_requirements` | state 必需字段、允许内容与信息边界；明确要求合成内容，不带真实身份信息 |
| `questions` | 唯一 `id`、题型、问题 `ins`、有序候选 `crit` 和判标签的规则 |
| `generation_guidance` | 常见、边界、易混淆和缺证据情况；不要要求模型为了类别均衡扭曲标签 |
| `examples` | 可选的少量人工核验样例；覆盖规则边界，不要放入待评估集内容 |

三种题型的标签写法：

| 题型 | 候选格式 | 生成标签格式 | 写入 Laya 的 `y` |
|---|---|---|---|
| `choice` | 保持顺序的 JSON 对象 | 候选 key 字符串 | key 在对象中的零起始位置 |
| `noul` | 必须含 `false` 与 `true` | JSON 布尔值 | `false=0`，`true=1` |
| `score` | 从低到高排列的数组 | 零起始整数 | 与等级顺序相同；不要打乱等级 |

一个 state 可包含多个问题。生成器会按规范建立 `id`、`split`、`source_group_id`、`task_family`、`lang`、`state`、`qs` 和审计 metadata。它不生成 `soft` 概率目标：模型不能代替重复标注结果来制造可信的概率分布。

## 2. 安装环境并配置 API 密钥

生成脚本只依赖 Python 标准库，通过 HTTPS 调用 API；Python 3.9 或更新版本即可。Jupyter Notebook 与 CLI 使用同一个 `DEEPSEEK_API_KEY` 环境变量。

在启动 Jupyter 或运行 Python 的终端中设置变量。不要把 key 放在 Notebook 单元格、任务规范、命令行参数或仓库文件里；Notebook 只检查变量是否存在，不会显示其值。

PowerShell 当前会话可以用隐藏输入设置：

```powershell
$secret = Read-Host "DeepSeek API key" -AsSecureString
$ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $env:DEEPSEEK_API_KEY = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
```

也可以在操作系统用户环境变量中预先设置，再从该会话启动 Jupyter。训练完成后清理当前终端：

```powershell
Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
```

Linux/macOS 当前 shell：

```bash
read -rsp "DeepSeek API key: " DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
printf '\n'
```

如果密钥曾公开粘贴到聊天、代码库、工单或 shell 历史，先到服务控制台撤销并轮换，再继续使用。不要在 Notebook 输出中打印环境变量。

## 3. 先验证任务规范

从仓库根目录运行；工作副本和生成数据保存在 `.gitignore` 已排除的 `laya/data_generation/generated/` 下：

```powershell
New-Item -ItemType Directory -Force .\laya\data_generation\generated | Out-Null
Copy-Item .\laya\data_generation\spec.example.json `
  .\laya\data_generation\generated\my_task_spec.json
```

编辑 `my_task_spec.json` 中的规则，再小批生成。修改标签定义后要同步修改每道题的 `labeling_policy`，并更新 `policy_version`。先让标注者阅读规范和示例，确认不同人对边界样本会做出一致判定。

## 4. 并发生成 JSONL

先用 20 条样本试跑，逐条抽查后再扩大批次：

```powershell
py -3 .\laya\generate_synthetic_data.py `
  --spec .\laya\data_generation\generated\my_task_spec.json `
  --count 20 `
  --batch-size 4 `
  --workers 4 `
  --model deepseek-flash `
  --out .\laya\data_generation\generated\train_candidate.jsonl
```

默认 API 为 `https://api.deepseek.com`，模型名 `deepseek-flash` 当前对应 DeepSeek-V4.1-Flash；默认开启 JSON Output，要求模型按指定 JSON 结构返回。模型名和接口后续可能变化，生成前可查看 [DeepSeek 更新日志](https://api-docs.deepseek.com/zh-cn/updates/)、[Chat Completions 文档](https://api-docs.deepseek.com/api/create-chat-completion/)和 [JSON Output 说明](https://api-docs.deepseek.com/zh-cn/guides/json_mode/)。

参数含义：

| 参数 | 默认值 | 用途 |
|---|---:|---|
| `--count` | 20 | 本次想新增的唯一样本数 |
| `--batch-size` | 4 | 单个 API 请求要求生成的条数，范围 1–20 |
| `--workers` | 4 | 并发 API 请求数，范围 1–16 |
| `--model` | `deepseek-flash` | API 模型名 |
| `--temperature` | 0.7 | 生成随机度 |
| `--max-tokens` | 4096 | 每个请求的输出 token 上限 |
| `--timeout` | 120 | 单请求超时秒数 |

脚本以波次并发发起请求；每个请求返回后打印完成进度，主线程负责校验、去重和写文件。当前使用非流式 Chat Completions，因此进度按已完成的请求更新，不会逐 token 刷新。结尾会汇总 token 用量、耗时、速度和逐题标签计数。

输出文件已存在时，脚本拒绝覆盖。要追加样本或从部分成功的批次续跑，复用相同 `--out` 并明确加 `--append`：

```powershell
py -3 .\laya\generate_synthetic_data.py `
  --spec .\laya\data_generation\generated\my_task_spec.json `
  --count 20 --batch-size 4 --workers 4 `
  --out .\laya\data_generation\generated\train_candidate.jsonl `
  --append
```

追加时脚本读取旧文件并跳过重复 state；成功批次会先落盘。遇到 API 错误时，检查终端错误和文件已有行数，修正问题后再用 `--append` 续跑。`--count` 表示这次要新增的唯一样本数。

## 5. 用 Notebook 跑完整构造流程

打开 [`notebooks/zh_dataset_construction.ipynb`](notebooks/zh_dataset_construction.ipynb)，逐格完成：

1. 定位仓库与忽略目录中的任务规范副本。
2. 查看并校验 task family、问题 schema、候选顺序和标注规则。
3. 确认 `DEEPSEEK_API_KEY` 已配置；不打印密钥。
4. 设定条数、batch size 与并发数，再显式启用 API 生成。
5. 读取 JSONL，检查 ID/state 重复、split、审核状态和标签分布。
6. 导出逐题 CSV 审核表，供人工填写审核标签、审核人和理由。

Notebook 默认关闭会产生 API 用量的生成单元格。先配置 key、读懂任务规范，再把 `RUN_GENERATION` 改成 `True`；首次建议 10–20 条、`workers=4`。它使用无缓冲子进程输出生成器的批次进度。生成输出和审核 CSV 都留在 Git 忽略目录，不会自动晋升为 train。

## 6. 检查与人工审核

JSONL 每行包含一条记录，示例：

```json
{
  "id": "synthetic-...-000001",
  "split": "train_candidate",
  "source_group_id": "synthetic-...-000001",
  "task_family": "support-routing-v1",
  "lang": "zh",
  "state": {"subject": "导出报错", "body": "导出报表一直失败。"},
  "qs": [{
    "id": "department", "t": "choice", "ins": "应由哪个部门处理？",
    "crit": {"billing": "账单问题", "technical": "产品故障", "other": "其他"},
    "y": 1
  }],
  "metadata": {
    "label_source": "deepseek_pseudo_label",
    "review_status": "needs_human_review",
    "review_evidence": {"department": "用户报告导出持续失败。"}
  }
}
```
* **id**: 样本的唯一标识符（本例中为合成数据生成的独立 ID）。
* **split**: 数据集的初始划分状态。`train_candidate` 表示这目前是训练集的候选数据，在人工审核通过前不会直接投入训练。
* **source_group_id**: 来源组标识。用于控制数据划分，确保来源于同一组的相似数据在切分时不会跨越不同集合（例如避免同时出现在训练集和测试集中，防止数据泄露）。
* **task_family**: 任务族或场景类型。`support-routing-v1` 标明这是一个用于“客服路由”的 v1 版本任务规范。
* **lang**: 语种。`zh` 代表该样本使用的是中文。
* **state**: 模型的输入特征或当前状态。在这里模拟了客服工单的内容，包含 `subject`（工单标题）和 `body`（工单正文）。
* **qs**: 题目列表（Questions），包含基于上述 `state` 需要模型做出决策的具体问题：
* **id**: 该题的唯一标识符（如 `department`，即部门分配）。
* **t**: 题型。`choice` 代表单项选择题。
* **ins**: 具体的任务指令或提问（Instruction）。
* **crit**: 候选字典（Criteria），按顺序列出了所有可选的分类标签及其含义定义（账单、技术、其他）。
* **y**: 模型的预测标签或标注答案。在 `choice` 题型中，这里使用的是**零起始索引**。`1` 代表选中了 `crit` 字典中的第 2 项，即 `technical`（产品故障）。


* **metadata**: 数据的审计与流程控制元数据：
* **label_source**: 标签的生成来源。`deepseek_pseudo_label` 说明目前的 `y` 值是 API 生成的伪标签。
* **review_status**: 人工审核状态。`needs_human_review` 标记该条数据正等待人工复核确认其正确性。
* **review_evidence**: 模型做出该预测的线索或证据，专供人工审核时快速核对依据，并不作为模型的直接输入。

推荐检查顺序：

1. 逐题核对 state 是否满足规范、标签是否真由文本证据支持，审核 `review_evidence`；该字段只是模型给出的线索。
2. 按题型与候选统计标签分布，找遗漏类别、矛盾 state、重复/模板化样本和边界错误；不要只看总体计数。
3. 由有权限的审核者在 CSV 或标注系统记录通过/拒绝、纠正标签、审核者、规则版本和理由；不要改写原始生成文件，保留审计来源。
4. 审核通过后复制到单独的审核后文件，将 `review_status` 标记为 `approved` 或 `human_reviewed`，记录 reviewer，并按来源组切分。真实验证、校准、锁定 test 和 OOD 数据必须独立收集，不得从同一套合成模板随机抽出。
5. 合成伪标签只建议进入 train。需要 `soft` target 时，使用真实重复标注/观测计数，而不是请求生成模型猜概率。

生成器会自动标记 `split=train_candidate` 与 `review_status=needs_human_review`，检查重复 state、问题 ID、题型与标签范围。它不会替团队做语义审核、授权判定、train/dev 划分或概率校准。`laya/data_generation/generated/` 已加入 Git 忽略；正式提交代码时不要强行添加业务数据或密钥。

## 7. 进入微调

人工审核后，用独立数据集构造 `train` 和 `dev` JSONL，并确保 `source_group_id` 不跨 split。CUDA head-only 试跑命令、数据字段和曲线解读见[微调实操指南](FINETUNING.md)；训练器会拒绝候选数据和未通过审核的数据。小样本流程只用于排查链路，不是生产质量结论。

不要把未经授权或脱敏的真实工单、个人信息、客户秘密发送到第三方 API。优先使用虚构内容；确需业务样本时，先在本地按授权规则去标识化，并只发送获准的最少字段。

## 8. 从公开对话构造决策辅助数据

[`notebooks/zh_dataset_construction.ipynb`](notebooks/zh_dataset_construction.ipynb) 在原有合成候选流程后新增了 ModelScope ShareGPT 中文对话分支；原有 112 条 [`zh-pilot-112`](experiments/zh-pilot-112/) 及其训练流程保留不动。构造脚本为 [`data_generation/build_sharegpt_laya.py`](data_generation/build_sharegpt_laya.py)，规则在 [`data_generation/sharegpt_policy_v2.json`](data_generation/sharegpt_policy_v2.json)，v2 加入了开问直接回答、澄清一致性和高风险边界示例。

这是**对话决策辅助数据**：输入是当前 user 轮次及其之前最多 7 条会话上下文；输出是回答策略、主题、澄清需求、外部核验需求和推理深度五类结构化决策，不学习源数据中的 assistant 回复。每个原始会话最多取一个样本，并按 `source_group_id` 隔离数据组。默认计划 1,200 train / 200 dev / 100 calibration / 400 test，共 1,900 cases 和约 9,500 道决策题。

### 构造步骤

1. 从 [ModelScope `AI-ModelScope/sharegpt_gpt4`](https://modelscope.cn/datasets/AI-ModelScope/sharegpt_gpt4) 下载 `sharegpt_zh_38K_format.jsonl` 到 `laya/data_generation/generated/sharegpt_zh_38k/raw/`。ModelScope 卡片显示 CC-BY-4.0，并说明沿用 ShareGPT 许可；对外发布前还要核对上游 ShareGPT 的适用条款和署名要求。
2. 本地筛选对话轮次、去重并过滤邮箱、手机号、身份证样式号码、URL 和疑似密钥。默认输出 `cases.jsonl`，状态只截止到当前 user 消息；同一原始会话只进入一个 split。
3. 使用 DeepSeek API 对每条 case 做 3 轮独立标注。key 可通过 `DEEPSEEK_API_KEY` 环境变量提供；Notebook 也把现有 `.env` **路径**传给脚本，脚本只在内存读取 `DEEPSEEK_API_KEY` 或 `deepseek_apikey`，不回显或持久化 key。API 请求关闭推理，只返回结构化标签以限制冗长输出。断点续跑会按 case ID 和轮次跳过已成功结果。
4. `assemble` 将多数票写入 Laya `y`，投票频率写入 `soft`，同时导出 `human_review.csv`。投票频率只是同一教师模型产生的软标签代理，不是人类重复标注分布，也不能作为校准结论。全部行都保留 `split=train_candidate` 和 `review_status=needs_human_review`。
5. 逐题人工审核并记录 `decision`、`corrected_label`、`reviewer`、`review_note`。审核完成后再按预先分配的 `planned_split` 生成正式 train/dev/calibration/test；评估集要独立审核，不能用伪标签结果支撑泛化或校准结论。

在仓库根目录下可直接运行：

```bash
python laya/data_generation/build_sharegpt_laya.py extract \
  --raw laya/data_generation/generated/sharegpt_zh_38k/raw/sharegpt_zh_38K_format.jsonl \
  --policy laya/data_generation/sharegpt_policy_v2.json \
  --out laya/data_generation/generated/sharegpt_zh_38k/v2/cases.jsonl \
  --manifest laya/data_generation/generated/sharegpt_zh_38k/v2/manifest.json

python laya/data_generation/build_sharegpt_laya.py annotate \
  --cases laya/data_generation/generated/sharegpt_zh_38k/v2/cases.jsonl \
  --policy laya/data_generation/sharegpt_policy_v2.json \
  --votes-out laya/data_generation/generated/sharegpt_zh_38k/v2/deepseek_votes.jsonl \
  --batch-size 10 --workers 4 --votes 3

python laya/data_generation/build_sharegpt_laya.py assemble \
  --cases laya/data_generation/generated/sharegpt_zh_38k/v2/cases.jsonl \
  --policy laya/data_generation/sharegpt_policy_v2.json \
  --votes laya/data_generation/generated/sharegpt_zh_38k/v2/deepseek_votes.jsonl \
  --out laya/data_generation/generated/sharegpt_zh_38k/v2/laya_candidates.jsonl \
  --review-csv laya/data_generation/generated/sharegpt_zh_38k/v2/human_review.csv \
  --manifest laya/data_generation/generated/sharegpt_zh_38k/v2/manifest.json
```

人工完成审核 CSV 后，只有五道题都给出接受/拒绝决策且每题填了审核人，记录才会进入审核后目录；修正标签时 `corrected_label` 填候选 key、`true/false` 或 score 索引。该命令不会覆盖候选文件：

```bash
python laya/data_generation/build_sharegpt_laya.py promote \
  --candidates laya/data_generation/generated/sharegpt_zh_38k/v2/laya_candidates.jsonl \
  --review-csv laya/data_generation/generated/sharegpt_zh_38k/v2/human_review.csv \
  --out-dir laya/data_generation/generated/sharegpt_zh_38k/v2/reviewed
```

`reviewed/train-dev.jsonl` 可传给当前 Head-only trainer；另有独立 train、dev、calibration、test 文件。未完成审核或拒绝的记录不会进入训练输出。

当前仓库提供 CUDA Head-only SFT、LoRA-SFT 和 RLCD-style 三个训练入口；全量 v2 的逐步训练、显式伪标签开关、并行启动和留出评估见 [`notebooks/full_v2_finetuning.ipynb`](notebooks/full_v2_finetuning.ipynb) 与[微调实操指南](FINETUNING.md)。RLCD-style 是本项目的实验实现，并非上游完整复现。候选集仍需人工审核后才能用于正式业务训练；要进行伪标签研究实验，必须显式开启相应参数且保留 `needs_human_review` 状态。生成数据默认在 Git 忽略目录，不要把未经授权的原始语料、候选标注或 `.env` 提交到仓库。
