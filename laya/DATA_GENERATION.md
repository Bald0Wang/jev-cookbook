# 用 DeepSeek 生成 Laya 微调数据草稿

本工具调用 DeepSeek API，按任务规范合成状态与标签，输出 Laya `encode_record()` 可读的 JSONL。它**只生成待审核的数据草稿**：不是 Laya trainer，也不是通过 DeepSeek API 微调 DeepSeek 模型。API 返回 JSON 格式正确，并不表示场景真实或标签正确。

## 1. 先把任务规则写清楚

从 [`data_generation/spec.example.json`](data_generation/spec.example.json) 复制一份任务规范，再按自己的业务修改：

- `task_family` 和 `policy_version`：任务族与规则版本；规则改动就升版本。
- `task_description`、`state_requirements`：模型能看见哪些信息、状态要有哪些字段、不能包含什么。
- `questions`：每题的 `id`、类型 `t`、指令 `ins`、候选 `crit` 和 `labeling_policy`。
- `examples`：可选的少量人工核对样例，格式为 `state` 加每题的 `labels`。示例要覆盖代表性规则，不能把待判定的验证集贴进来。
- `generation_guidance`：希望覆盖的场景、边界例和易混淆例。不要指示模型为了类别均衡而违反标签规则。

三种题型的标签输入约定：

| 类型 | 规范中的候选 | `examples.labels` 和模型生成标签 |
|---|---|---|
| `choice` | `crit` 是有序 JSON 对象 | 候选 key 字符串，例如 `"billing"`；写入 Laya 时会转换成对应位置的零起始 `y` |
| `noul` | `crit` 必须含 `false` 和 `true` | JSON 布尔值 `false` / `true`；Laya 固定将 `y=0` 映射为 false、`y=1` 映射为 true |
| `score` | `crit` 是从低到高排列的数组 | 零起始等级整数，例如 3 档中的 `0`、`1`、`2`；等级顺序不能随机打乱 |

生成器会检查这些类型与范围，并构造 `id / split / source_group_id / task_family / lang / state / qs / metadata` 字段。输出的 `split` 是 `train_candidate`，审核接受后再复制到正式训练文件并改为 `train`；不会生成 `soft` 概率目标，因为模型不能凭空制造可信的概率分布。

## 2. 准备 Python 和 API 密钥

脚本只用 Python 标准库发 HTTPS 请求，不需要额外安装 OpenAI SDK。Python 3.9 或更新版本即可。密钥只从进程环境变量 `DEEPSEEK_API_KEY` 读取，不要写入任务规范、脚本、命令参数或数据文件。

Windows PowerShell 可用隐藏输入临时设置密钥：

```powershell
$secret = Read-Host "DeepSeek API key" -AsSecureString
$ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $env:DEEPSEEK_API_KEY = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
```

运行结束后清理当前 PowerShell 会话中的环境变量：

```powershell
Remove-Item Env:DEEPSEEK_API_KEY
```

如果密钥曾贴在聊天、代码库、工单或 shell 历史中，请先在服务控制台撤销并轮换，再使用新密钥。

## 3. 生成 JSONL

在项目根目录先少量生成并抽查：

```powershell
py -3 .\laya\generate_synthetic_data.py `
  --spec .\laya\data_generation\spec.example.json `
  --count 20 `
  --batch-size 4 `
  --workers 4 `
  --out .\laya\data_generation\generated\train_candidate.jsonl
```

脚本默认调用模型 `deepseek-flash`，这是 DeepSeek 官方当前用于 DeepSeek-V4.1-Flash 的 API 名称。默认接口地址为 `https://api.deepseek.com`，使用 Chat Completions 和 JSON Output。`--batch-size` 控制每个请求的样本数，`--workers` 控制同时进行的请求数（默认 4，允许 1–16）；脚本按波次并发，主线程负责去重和顺序写盘。结束时会报告耗时、平均生成速度、token 用量和标签计数。可调模型名、接口地址、温度和输出 token 上限。接口可用模型名可能变化，使用前请查看 [DeepSeek 更新记录](https://api-docs.deepseek.com/updates/) 和 [Chat Completions 文档](https://api-docs.deepseek.com/api/create-chat-completion/)。

每行是一个 JSON 对象。以下是结构示意，输出中的记录会额外带 `metadata` 审计信息：

```json
{
  "id": "synthetic-...-000001",
  "split": "train_candidate",
  "source_group_id": "synthetic-...-000001",
  "task_family": "support-routing-v1",
  "lang": "zh",
  "state": {"subject": "重复扣款", "body": "本月账单扣款两次。"},
  "qs": [
    {
      "id": "department",
      "t": "choice",
      "ins": "这张工单应分配给哪个部门？",
      "crit": {"billing": "账单问题", "technical": "产品故障", "other": "其他"},
      "y": 0
    }
  ]
}
```

同名输出文件默认不会覆盖；需要继续补样本时显式加 `--append`。脚本会跳过完全重复的 state，并打印每道题的标签计数。输出目录 `laya/data_generation/generated/` 已加入 Git 忽略规则，避免误提交客户数据或大体积样本。

## 4. 人工审核，再划分数据

生成器完成的是**格式校验和标签类型校验**，不是事实核验。输出记录会带：

- `metadata.label_source = "deepseek_pseudo_label"`
- `metadata.review_status = "needs_human_review"`
- 每题简短 `review_evidence`，只作审核线索，不代表结论正确

推荐流程：

1. 先抽查 10–20 条，逐题核对 state、候选定义、标签和 `review_evidence` 是否符合任务规则；不符合就先修规范，不要盲目增大生成量。
2. 按题型、语言、任务族和每个候选检查计数，查看模型是否漏掉边界案例、复制示例或产生冲突状态。删除错误数据，或由有权限的标注者更正标签并留下审核人、时间和规则版本。
3. 接受的记录复制到独立的审核后文件；保留生成来源，明确记录标签是否由人工裁决。不要把未审核的伪标签混入人工 gold。
4. 合成样本只进入训练集。开发集、概率校准集、锁定测试集和 OOD 集应从真实、独立、人工审核的数据建立；不能用同一规范模板的改写版跨集合，也不能把生成器示例拆到评估集。
5. 如果要训练 `soft` 分布，只使用真实重复结果或独立标注计数，并保存原始票数；不要让生成模型猜一个看似精确的概率。

### GPU 小样本微调

如果只是评估流程，可以明确将样本标为 `assistant_reviewed_pilot`，保留 `metadata.reviewer` 和“非人工 gold”的说明；训练时必须显式加 `--allow-assistant-reviewed-pilot`。正式训练请改用人工审核状态 `approved` / `human_reviewed`，不要加此开关。JSONL 必须同时含按 `source_group_id` 隔离的 `train` 和 `dev`：

```powershell
py -3 .\laya\finetune_reviewed_jsonl.py `
  --data .\laya\data_generation\generated\reviewed_train_dev.jsonl `
  --model-dir .\laya\models\multilingual `
  --output-dir F:\jev\laya-runs\zh-head-tuned-v1
```

脚本只在 CUDA 上运行，冻结 encoder，只更新决策头；以 `dev` soft cross-entropy 早停并保存新目录，不改基座权重。它拒绝 `train_candidate` 和未审核数据。每个 epoch 会追加 `training_log.csv`、`training_log.jsonl`，训练结束生成 `experiment.json`。可把这些日志做成自包含 HTML 图表：

```powershell
py -3 .\laya\visualize_training.py --run-dir F:\jev\laya-runs\zh-head-tuned-v1
```

输出目录中的 `training_report.html` 展示基座 / 微调后 Dev 指标、逐 epoch 损失和各题型准确率，方便团队讨论。助手抽检的小样本若加了 `--allow-assistant-reviewed-pilot`，结果只用来检验 GPU 流程，不能当成有业务泛化能力的 checkpoint。

本仓库提供一份可复核的[中文 112 条 GPU 试跑记录](experiments/zh-pilot-112/README.md)，包含 train/dev JSONL、逐轮日志和离线 HTML 图表。数据是合成伪标签，尚未经人工金标审核；发布这份记录是为了透明讨论，不代表正式业务评估。

不要把未经脱敏和授权的真实工单、个人信息、客户秘密或受限制内容发送到第三方 API。需要业务真实感时，优先在本地抽取去标识化结构，再只向 API 发送已获准的最少字段，或让它按虚构要求生成数据。

## 5. 质量边界

自动校验能抓到格式错、非法题型、标签不在候选范围内和重复 state；它不能保证样本分布像真实业务、规则解释正确、合成标签无偏或模型微调后会泛化。伪标签比例过高会把生成器偏差教给 Laya。保存任务规范、模型名、生成批次、数据哈希和审核记录，并与真实数据的 head-only 基线分开评估。
