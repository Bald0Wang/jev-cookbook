"""01 · 认识 Jev：模型、上手与场景。

合并原 01 简介 / 02 快速开始 / 03 场景地图 / 09 AI 入门四章为单一介绍章节，
结构与官方文档阅读顺序一致（Introduction → Quickstart → Use Case Map → AI Primer），
并补充 jev-cookbook 知识库的社区实测认知。
"""
from notebook_support import Chapter, sources


def build():
    c = Chapter(
        "introduction",
        "01 · 认识 Jev：模型、上手与场景（Introduction Lab）",
        "introduction",
        "一册读完 Jev 是什么、怎么调、用在哪、概率为什么可信，并附社区实测补充与一个综合实验。",
        "| 1 | Jev 是什么：与 LLM 的区别、三种原语 |\n"
        "| 2 | 三分钟上手：亲手发出第一次请求 |\n"
        "| 3 | 场景地图：什么活儿适合交给 Jev |\n"
        "| 4 | 概率为什么可信：训练目标与校准 |\n"
        "| 5 | 社区实测补充（jev-cookbook）|\n"
        "| 6 | 综合实验：赛事指挥台 |",
    )
    c.prepare()

    # ── 1. Jev 是什么 ──────────────────────────────────────────────
    c.md("""## 1. Jev 是什么

一句话：**Jev 是 TypeSafe 的旗舰模型，也是第一个「System One」模型——输入是状态（state）加一组类型化的问题（questions），输出是类型化的答案加概率分布。没有文本生成，也没有解析。**

传统 LLM 为人类阅读写文本；当代码需要做判断时，就得把生成的文字再解析回程序可依赖的形式——这一步既慢又脆。Jev 直接跳过这两步：像 LLM 一样读懂自然语言，但只返回**你问的那几个数**。

### 与 LLM 的区别（官方对比）

| 维度 | 聊天大模型 | Jev（System One） |
|---|---|---|
| 训练目标 | 生成讨人喜欢的回复（RLHF） | 校准决策（RLCD）：概率对齐真实结果 |
| 输出 | 一段自由文本 | 类型化取值 + 概率分布（由你的问题定义） |
| 会做什么 | 写作、代码、解释推理 | 只做判断；不写回复、不解释推理 |
| 适合谁消费 | 人 | 程序：分支、排序、路由 |

两个边界：目前**只接受文本输入**（字符串、JSON、文本数组；图像/音频/视频暂不支持）；名字借自《思考，快与慢》的「系统 1」——快速直觉判断，不是对人类思考的科学复现。

### 三种原语 = 全部词汇

| 原语 | 问题类型 | 示例输出 |
|---|---|---|
| `Choice` | 从选项中选一个 | `choice: "billing"` + 各选项概率 |
| `Score` | 按有序标准打分 | `score: 1.4`（0=平静, 1=沮丧, 2=非常沮丧） |
| `Noul` | 某陈述是否为真 | `noul: 0.95` |

三种问题可以在**一次调用里混用**，每个问题并行、相互独立地对照同一 state 求值——加问题几乎不增加延迟，也没有长上下文「越读越糊」的问题。

**提问纪律：每个问题只问一件专家几秒内能下结论的事（原子判断）。** 复杂判断拆成多个独立问题，在代码里用自有逻辑加权组合——优先级变了只改代码系数，不用改提示词。

### 速度与价格量级

输入 $0.042 / 百万 token，**输出免费**（官方 Models 页）；实测中位延迟约 0.65–0.72 秒（JevBench v1.2）。便宜到可以「投机式地多问」——把不确定用不用得上的问题都塞进同一次调用。

阅读：[官方 Introduction](https://docs.typesafe.ai/introduction) · """ + sources("introduction"))

    # ── 2. 三分钟上手 ─────────────────────────────────────────────
    c.md("""## 2. 三分钟上手

**最快的方式**：打开官方 [Playground](https://console.typesafe.ai/playground)，粘贴任意文本，加一个问题就能看到答案。不想登录也可以直接发 HTTP：

```bash
curl -X POST https://api.typesafe.ai/v1/systemone \\
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"state": "连续三天连不上 Stripe，每天在丢订单，尽快处理！",
       "model": "jev-latest",
       "questions": {"urgency": {"type": "noul", "instructions": "这条消息是否表达了紧迫性？"}}}'
```

下面用 SDK 做同样的事，并在**一次调用**里同时问三种原语——这是 System One 的核心体验：一发请求，三份带概率的答案。离线运行时返回人工构造答案（会打印提示），不代表 Jev 实测。""")
    c.step("### 实验 A：一次调用，三种原语",
           '''EXP_STATE = ("用户：我连续三天没能把 Stripe 账户连上，集成一直失败，"
             "每耽误一天都在丢订单，请尽快处理！")

EXP_QUESTIONS = {
    "urgency": Noul(instructions="这条消息是否表达了紧迫性？"),
    "intent": Choice(instructions="用户的主要诉求是什么？", criteria={
        "troubleshoot": "希望排查或修复连接问题",
        "refund": "要求退款或赔偿",
        "inquiry": "只是咨询，不要求立即处理"}),
    "frustration": Score(instructions="用户的受挫程度如何？", criteria=[
        "平静，仅陈述事实", "有些不满", "强烈不满，有流失风险"]),
}
EXP_OFFLINE = {
    "urgency": _FakeAnswer("noul", noul=0.94),
    "intent": fake_choice({"troubleshoot": 0.82, "refund": 0.03, "inquiry": 0.15}, 0.8),
    "frustration": fake_score({0: 0.05, 1: 0.35, 2: 0.6},
                              ["平静", "有些不满", "强烈不满"], 0.87),
}

resp_a = ts.call(EXP_STATE, EXP_QUESTIONS, EXP_OFFLINE, "实验A·三原语一次调用")
show(resp_a)''')
    c.md("""**观察与理解：** live 模式下三份答案来自**同一次网络往返**；`Choice`/`Score` 带 confidence，`Noul` 的不确定性直接体现在概率靠近 0.5。三个问题相互独立——如果改 `intent` 的措辞会牵动 `urgency` 的数值，说明问题写得不够原子。""")

    # ── 3. 场景地图 ──────────────────────────────────────────────
    c.md("""## 3. 场景地图：什么活儿适合交给 Jev

官方 Use Case Map 整页回答这一个问题。五大类用法：

| 用法 | 人话解释 |
|---|---|
| 自动化软件里的语义判断 | 代码管流程，Jev 出判断；可后台跑上百万次不用人盯 |
| 实时应用 | ~150ms 出答案，快到能进游戏和用户界面 |
| 大数据上的批量判断 | 同一个判断跑一百万次，成本约为大模型调用的百分之一 |
| 万能校验器 | 查幻觉、查引用是否支撑结论、查越狱与违规话术 |
| 给大模型当管家 | 决定哪条请求发给哪个模型；拦住注入与泄露 |

官方归纳的判断形态，每一种都落到三种原语上：

- **是哪一类？** 意图 / 主题 / 风险类型 → `Choice`
- **有没有？** 垃圾 / 欺诈 / 紧迫 / 敏感信息 → `Noul`
- **打几分？** 严重度 / 相关性 / 质量 → `Score`
- **该走哪条路？** 工具选择 / 人工升级 / 队列分派 → `Choice` + 代码分支
- **找最相关的？** 语义搜索 / RAG 上下文 / 排序 → 检索与排序组合
- **核对有没有错？** 引用支持 / 策略违规 → `Noul` 逐条校验
- **抽特征或字段？** 购买意图喂预测模型 / 从文本回填表单 → `Score` / `Choice`

两个边界（从官方用例读出，非官方明文）：各场景几乎都配「不确定就转人工」——法务、理赔、招聘淘汰这类高风险终审不能全交给它；需要长篇写作或开放推理时转交大模型，Jev 在前面把「该走哪条路」快速定下来。

阅读：[官方 Use Case Map](https://docs.typesafe.ai/concepts/use-case-map) · """ + sources("concepts/use-case-map"))

    # ── 4. 训练目标与校准 ─────────────────────────────────────────
    c.md("""## 4. 概率为什么可信：训练目标与校准

预训练模型之后有三条改造路线（官方 AI Primer）：**RLHF** 把模型变成聊天机器人；**RLVR** 造出会推理但更慢更贵的模型；**RLCD**（面向校准决策的强化学习）是 Jev 走的第三条路——训练模型返回**决策和校准概率**，而不是文本。

校准的含义：**按一组预测衡量**。给 0.8 概率的事件，长期发生频率应接近 80%；它不保证任何单次预测正确。""")
    c.step("用 20 条人工数据直观感受「校准」——预测 0.2 的组实际发生 10%，预测 0.8 的组发生 80%，两组都「准」，但组内单次仍会错：",
           '''groups = {0.2: [1] * 2 + [0] * 8, 0.8: [1] * 8 + [0] * 2}
for p, labels in groups.items():
    print(f"预测概率 {p}：{len(labels)} 条，实际发生 {sum(labels) / len(labels):.0%}，"
          f"组内仍有 {labels.count(0)} 次没发生")''',
           "校准好 ≠ 单次必对。工程上正确的用法：用概率做群体决策（路由、排序、抽检），单点高风险动作交给阈值和人工复核。")

    # ── 5. 社区实测补充 ───────────────────────────────────────────
    c.md("""## 5. 知识补充：社区实测认知（jev-cookbook）

以下数字全部来自 [datawhalechina/jev-cookbook](https://github.com/datawhalechina/jev-cookbook) 知识库收录的实验报告：

**JevBench v1.2**（cookbook `15-jevbench`，242 个类型化决策的公开基准）：
- Jev 1.13.0 综合智能分**榜首**（75.4），答案可解析率 **100%**，路由任务 74.1%，中位延迟 **0.65–0.72s**，每千次决策成本约 **$0.04**；
- 稳定性：同一套题隔 16 分钟跑两遍，仅 **1.2%** 的答案变化——端点不是确定性的，读表时约 1 个百分点的差距应视为噪声。

**Jev 能替代 Rerank 吗**（cookbook `18-wechat-rerank-experiment`，80 条 SciFact 查询的精排对照）：
- 相对不做精排，Jev 的 nDCG@10 提升 **+0.0778**，比传统精排还高 **+0.0332**，精排耗时与 token 用量显著更低。固定候选集上的语义重排是 Jev 的甜点区。

**fast-jev-compaction**（cookbook `04`，Claude Code 压缩插件的生产用法）：
- 每次工具调用和结果在**一次快请求里逐条打分**，过期内容丢弃、保留的保持原文——用 Jev 的判断替代有损摘要。

**智能家居**（官方 [demos/smart-home](https://docs.typesafe.ai/demos/smart-home) + 我们的可运行复刻）：
- 模式：**一次调用捆绑 10 个问题**（意图、是否复合、范围、房间、设备类别 + 五类设备动作预判），代码端剪枝无关分支；复合指令再用 noul 判「谁必须先于谁」做串并行编排——「投机式多问 + 原子组合」的完整实战。""")

    # ── 6. 综合实验：赛事指挥台 ───────────────────────────────────
    c.md("""## 6. 综合实验：赛事指挥台

一次夜跑赛事收到三条现场消息。我们让 Jev 在**一次请求**中对每条消息回答三个独立问题（哪类事件 `Choice`、多快处理 `Score`、是否需要人工 `Noul`），再由 Python 按阈值分流——模型管语义，代码管规则。""")
    c.step("### 6.1 定义状态与问题",
           '''INCIDENTS = [
    {"id": "runner_injury", "state": {
        "event": "海湾夜跑 10 公里", "time": "19:12",
        "message": "2.4 公里蓝旗处有跑者脚踝扭伤，无法继续前进，请派人协助。"}},
    {"id": "water_station", "state": {
        "event": "海湾夜跑 10 公里", "time": "19:13",
        "message": "7 号补水站的纸杯用完了，但仓库还有整箱，麻烦补送两箱。"}},
    {"id": "shirt_pickup", "state": {
        "event": "海湾夜跑 10 公里", "time": "19:15",
        "message": "完赛T恤的领取处是先到先得吗？明天早上还能领吗？"}},
]

INCIDENT_QUESTIONS = {
    "incident_type": Choice(instructions="这条赛事消息主要属于哪类事件？", criteria={
        "medical_help": "跑者受伤或需要现场医疗",
        "supplies": "物资补给问题",
        "event_info": "赛事信息咨询"}),
    "priority": Score(instructions="需要多快处理？", criteria=[
        "可赛后处理", "30 分钟内", "10 分钟内", "必须立即"]),
    "requires_human": Noul(instructions="是否需要人工到场介入？"),
}''')
    c.step("### 6.2 逐条调用并由代码分流",
           '''ROUTES = {"medical_help": "现场负责人 / 医疗人员",
           "supplies": "补给组（优先处理）",
           "event_info": "自动回复赛事 FAQ（模拟）"}
LEVELS = ["可赛后", "30分钟", "10分钟", "立即"]
OFFLINE = [
    {"incident_type": fake_choice({"medical_help": 0.9, "supplies": 0.06, "event_info": 0.04}, 0.9),
     "priority": fake_score({0: 0, 1: 0, 2: 0.15, 3: 0.85}, LEVELS, 0.9),
     "requires_human": _FakeAnswer("noul", noul=0.93)},
    {"incident_type": fake_choice({"supplies": 0.88, "medical_help": 0.06, "event_info": 0.06}, 0.85),
     "priority": fake_score({0: 0.1, 1: 0.7, 2: 0.2, 3: 0}, LEVELS, 0.8),
     "requires_human": _FakeAnswer("noul", noul=0.22)},
    {"incident_type": fake_choice({"event_info": 0.9, "supplies": 0.05, "medical_help": 0.05}, 0.9),
     "priority": fake_score({0: 0.8, 1: 0.2, 2: 0, 3: 0}, LEVELS, 0.85),
     "requires_human": _FakeAnswer("noul", noul=0.04)},
]

for inc, off in zip(INCIDENTS, OFFLINE):
    r = ts.call(inc["state"], INCIDENT_QUESTIONS, off, f"指挥台·{inc['id']}")
    t = r.choices["incident_type"].choice
    human = r.nouls["requires_human"].noul >= 0.7   # 阈值是应用政策
    print(f"{inc['id']:14s} → {ROUTES[t]}{'（转人工）' if human else ''}")''')
    c.md("""**观察与理解：** 模型只回答了三个数；「≥0.7 转人工」这条规则完全在代码里——改阈值不重跑模型、不碰提示词。把不可妥协的规则（如医疗类永远转人工）写进确定性代码，正是官方推荐的分工。""")

    c.finish(
        "| 概念 | 一句话 |\n|---|---|\n| System One | 状态+类型化问题 → 带概率的类型化答案 |\n| 三原语 | Choice 选、Score 评、Noul 判 |\n| 原子问题 | 一题只问一件事，组合交给代码 |\n| 校准 | 群体频率对齐，不保证单次正确 |",
        "把「该不该给这条工单升级到人工？」设计成一个合格的问题。它该用哪种原语？什么样的写法违反了原子性？",
        "「升级到人工」混了两个判断：问题严重不严重（Score 或 Noul）+ 当前自动流程能不能处理（Noul/Choice）。合格写法是拆成两个独立问题，由代码组合；一个 noul 同时问两件事，任一因素翻转都会污染概率。"
        "下一章：[System One](02_SystemOne.ipynb) 深入单次调用机制；想先练原语可看[原语](04_原语.ipynb)。",
    )
    return c.save()


if __name__ == "__main__":
    print(build())
