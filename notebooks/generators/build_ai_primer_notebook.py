"""生成开篇 AI Primer：认识 Jev，并把类型化决策接入一段小流程。"""
from notebook_support import Chapter, sources


def build():
    c = Chapter(
        "ai_primer",
        "先认识 Jev：从聊天文本到软件决策（AI Primer Lab）",
        "introduction/machine-learning-primer",
        "先说明 Jev 与 System One 的关系，再用一次赛事调度实验连接类型化答案、概率和代码控制流。",
        "| 1 | Jev 是什么：Introduction 与 AI Primer 的主张 |\n"
        "| 2 | 赛事指挥台：Choice、Score、Noul 如何组成一次分流 |\n"
        "| 3 | 概率属于一组预测：用小数据读懂校准 |",
    )
    c.prepare()
    c.code('''PRIORITY_LEVELS = [
    "可在赛事结束后处理",
    "尽量在 30 分钟内处理",
    "需要在 10 分钟内处理",
    "必须立即处理",
]''')
    c.code('''INCIDENTS = [
    {"id": "runner_injury", "state": {
        "event": "海湾夜跑 10 公里",
        "time": "19:12",
        "message": "2.4 公里蓝旗处有跑者脚踝扭伤，无法继续前进，请派人协助。",
    }},
    {"id": "water_station", "state": {
        "event": "海湾夜跑 10 公里",
        "time": "19:12",
        "message": "3 号补水点只剩两箱水，下一批跑者约两分钟后到。",
    }},
    {"id": "shirt_pickup", "state": {
        "event": "海湾夜跑 10 公里",
        "time": "19:12",
        "message": "完赛纪念衫在哪个窗口领取？我刚到终点。",
    }},
]''')
    c.code('''INCIDENT_OFFLINE = [
    {
        "incident_type": fake_choice({"medical_help": .92, "resource_shortage": .03,
                                       "event_information": .03, "other": .02}, .92),
        "urgency": fake_score({0: 0, 1: 0, 2: .2, 3: .8}, PRIORITY_LEVELS, .82),
        "requires_human": _FakeAnswer("noul", noul=.98),
    },
    {
        "incident_type": fake_choice({"medical_help": .02, "resource_shortage": .84,
                                       "event_information": .10, "other": .04}, .84),
        "urgency": fake_score({0: 0, 1: .1, 2: .8, 3: .1}, PRIORITY_LEVELS, .73),
        "requires_human": _FakeAnswer("noul", noul=.74),
    },
    {
        "incident_type": fake_choice({"medical_help": .01, "resource_shortage": .01,
                                       "event_information": .94, "other": .04}, .94),
        "urgency": fake_score({0: .8, 1: .15, 2: .05, 3: 0}, PRIORITY_LEVELS, .82),
        "requires_human": _FakeAnswer("noul", noul=.04),
    },
]''')
    c.md("""## 1. 先回答一个问题：Jev 是什么？

官方 **Introduction** 把 Jev 定义为 TypeSafe 的旗舰模型，也是第一个 **System One** 模型。TypeSafe 是平台；Jev 是模型；System One 描述的是一类面向软件、快速回答窄问题的模型。

一次请求把业务材料放进 `state`，再用 `Choice`、`Score` 或 `Noul` 写出要判断的问题。Jev 返回有类型的答案和概率，Python 直接读取字段并决定下一步；它不先写一段给人看的文字，再让程序猜其中的 JSON。

这也不是“让模型接管整个应用”。下面由 Jev 判断赛事消息，阈值、人工转交和队列分派仍由普通代码控制。Notebook 只打印模拟分流，不会联系工作人员或执行现场动作。

阅读：[官方 Introduction](https://docs.typesafe.ai/introduction) · [本地知识库 Introduction](../dist/introduction/index.html) · {sources("introduction")}""")
    c.md("""## 2. AI Primer 补充了什么？

AI Primer 解释 TypeSafe 为什么把模型训练目标放在**可校准的决策概率**上。文档用 RLHF（偏好回答）、RLVR（可验证奖励）和 RLCD（面向校准决策的强化学习）对照不同目标，并将机器可读、可测试的输出称为 Machine Native Intelligence。

这是 TypeSafe 对自身方向的说明，不是对所有聊天模型的概括，也没有公开足以复现 RLCD 的完整训练配方。这里先看 Jev 的输入/输出契约；不会从训练目标直接推导某个业务任务一定准确。

![官方图示：预训练模型之后的 RLHF、RLVR 与 RLCD 路径](../assets/images/images/ai-primer/training-paths-light.webp)

校准也不是“这一次有 80% 把握就必然正确”。它描述很多次预测组成的群体：被赋予 0.8 概率的事件，长期发生频率应大致接近 80%。下方实验把这个定义变成能运行的分流流程。

阅读：[官方 AI Primer](https://docs.typesafe.ai/introduction/machine-learning-primer) · [本地知识库 AI Primer](../dist/introduction/machine-learning-primer/index.html) · {sources("introduction/machine-learning-primer")} · {sources("confidence")}""")
    c.md("""## 3. 实验：海湾夜跑的赛事指挥台

三条现场消息都放进相同形状的 `state`。我们让 Jev 在一次请求中各回答三个**互相独立**的问题：属于哪类事件、需要多快处理、是否需要人工介入。之后由 Python 组合结果。

| 问题 | 原语 | 代码将怎样使用 |
|---|---|---|
| 事件类别 | `Choice` | 选现场医疗、补给、赛事信息或其他 |
| 处理时限 | `Score` | 按 0–3 的有序等级安排优先级 |
| 是否要人工介入 | `Noul` | 读取命题概率；高风险直接交给现场负责人 |

**接口边界：** `Choice` 和 `Score` 返回 `confidence` 与概率分布；`Noul` 返回 `noul` 概率，没有独立的 `confidence` 字段。阈值是应用政策，正式使用前需要独立标注数据来选择和验证。""")
    c.step("### 3.1 写出原子问题\n\n每题只判断一个维度；问题描述写清标准，不能指望 ID 名称代替 instructions。",
           '''INCIDENT_QUESTIONS = {
    "incident_type": Choice(
        instructions="这条赛事消息主要属于哪类事件？",
        criteria={
            "medical_help": "跑者受伤或需要现场医疗协助",
            "resource_shortage": "补水、物资或现场设施问题",
            "event_information": "路线、时间或领取点等赛事信息问题",
            "other": "其他情况或现有信息无法归类",
        },
    ),
    "urgency": Score(
        instructions="仅根据消息判断处理时限；不要把类别本身当作紧急程度。",
        criteria=PRIORITY_LEVELS,
    ),
    "requires_human": Noul(
        instructions="在自动处理前，这条消息是否需要现场人员核实或介入？",
    ),
}''',
           "三个问题共享一份 state，但答案通过各自的 ID 取回；一次调用不会让某题先读到另一题答案。")
    c.step("### 3.2 一次请求回答三题\n\n每条消息各发一次请求；总计 3 次实验请求，另有准备区的 1 次连通性请求。",
           '''incident_responses = [
    ts.call(incident["state"], INCIDENT_QUESTIONS, offline, incident["id"])
    for incident, offline in zip(INCIDENTS, INCIDENT_OFFLINE)
]''',
           "离线模式使用上面的人工答案，只检验流程。Live 模式才会请求 Jev；不同措辞或模型版本可能给出不同结果。")
    c.step("### 3.3 看模型返回的类型化答案\n\n逐条查看答案类型、概率和 confidence；不要只看最终队列。",
           '''for incident, response in zip(INCIDENTS, incident_responses):
    print("事件:", incident["id"])
    show(response)
    print()''')
    c.step("### 3.4 用代码决定是否自动分流",
           '''HUMAN_REVIEW_THRESHOLD = 0.75

def dispatch(response, human_threshold=HUMAN_REVIEW_THRESHOLD):
    incident = response.choices["incident_type"]
    urgency = response.scores["urgency"]
    requires_human = response.nouls["requires_human"].noul
    if incident.choice == "medical_help" or requires_human >= human_threshold:
        return "现场负责人 / 医疗人员"
    if incident.confidence < 0.60 or urgency.confidence < 0.60:
        return "值班台补充信息"
    if incident.choice == "resource_shortage" and urgency.score >= 1.5:
        return "补给组（优先处理）"
    if incident.choice == "event_information" and urgency.score < 1.0:
        return "自动回复赛事 FAQ（模拟）"
    return "普通运维队列"''',
           "医疗类总是转给现场人员；其他类先检查人工介入概率和 confidence，再由代码应用各自的处理规则。")
    c.step("输出指挥台结果。分流只是本地字符串，不会真的派工。",
           '''routes = [dispatch(response) for response in incident_responses]
for incident, response, route in zip(INCIDENTS, incident_responses, routes):
    print(f"{incident['id']:<16} → {route}")

observed_live = {
    route for route, log in zip(routes, CALL_LOG) if log["source"] == "live"
}
COVERAGE = {
    "live_routes_observed": sorted(observed_live),
    "offline_routes_are_model_evidence": False,
}''',
           "若 live 返回没有命中某条路径，把它记为本次未观察到；不要改写模型答案来凑齐分支。")
    c.step("### 3.5 同一答案，改一条政策阈值",
           '''resource_response = incident_responses[1]
for threshold in (0.70, 0.75):
    print({
        "人工介入阈值": threshold,
        "结果": dispatch(resource_response, human_threshold=threshold),
    })''',
           "这里复用同一组答案，只改 Python 阈值。若路由改变，改变的是应用政策，不是 Jev 的输出。0.70/0.75 只是演示值，不是生产阈值。")
    c.md("""## 4. 一张小表读懂校准

这组数据是人工构造的数学演示，不是 Jev 结果。每个概率桶各有 10 条记录，刻意让实际频率与预测概率相等。""")
    c.step("构造两个概率桶。1 表示事件发生，0 表示没有发生。",
           '''CALIBRATION_GROUPS = {
    0.2: [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    0.8: [1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
}''')
    c.step("比较预测概率与每组实际发生率。",
           '''calibration_table = [
    {"预测概率": probability, "样本数": len(labels),
     "实际频率": sum(labels) / len(labels)}
    for probability, labels in CALIBRATION_GROUPS.items()
]''')
    c.step("打印结果，并数一数 0.8 组里有几次没发生。",
           '''print(json.dumps(calibration_table, ensure_ascii=False, indent=2))
print("0.8 概率组中的未发生次数:", CALIBRATION_GROUPS[0.8].count(0))''',
           "这组 10 条中仍有 2 条未发生。校准描述群体频率，不会保证某一条预测正确；10 条也太少，不能据此评估真实模型。")
    c.finish(
        "| 组件 | 在实验中的职责 |\n|---|---|\n"
        "| Jev / System One | 对同一 state 回答窄而明确的 typed questions |\n"
        "| 概率与 confidence | 暴露不确定性信号；不能替代业务验证 |\n"
        "| Python | 设置阈值、组合结果、控制分支和人工出口 |",
        "如果主办方决定：任何医疗消息都不能自动关闭工单，你会把这条规则放进问题措辞，还是放进 Python 控制流？为什么？",
        "应把不可妥协的安全规则写进确定性控制流；Jev 可以帮助识别医疗类消息，代码确保该类始终交给现场人员。之后仍要用有标签的独立数据检查识别漏报。",
        "下一步：[快速开始实验](quickstart_experiments.ipynb)带你亲手发出一次请求；之后可看[简介实验](introduction_experiments.ipynb)练习组合判断。训练目标与实现细节以官方 [AI Primer](https://docs.typesafe.ai/introduction/machine-learning-primer) 为准。",
    )
    return c.save()


if __name__ == "__main__":
    print(build())
