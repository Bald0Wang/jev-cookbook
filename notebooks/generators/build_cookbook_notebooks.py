#!/usr/bin/env python3
"""生成截图中 8 篇 Cookbook 的可运行中文实验 notebook。

每本 notebook 都保留同一条学习路径：定义 state → 定义问题 → 调用 TypeSafe →
读取结构化答案 → 在 Python 中完成 Cookbook 的确定性后处理。没有有效 API Key 时，
统一入口会使用内置示例答案，因此学习者仍能完整走通代码路径。
"""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parent.parent   # notebooks/
OUT = ROOT / "cookbooks"


def make_notebook(title, source, purpose, build):
    cells = []

    def md(text):
        cells.append(nbf.v4.new_markdown_cell(text))

    def code(text):
        cells.append(nbf.v4.new_code_cell(text))

    md(f"""# {title}：交互式实验

本 notebook 把中文镜像站中的 [Cookbook]({source}) 改写成可以逐格运行、修改输入并观察结果的最小实验。
{purpose}

运行方式与现有 `07_架构模式.ipynb` 一致：有有效的 `TYPESAFE_API_KEY` 时调用真实的
TypeSafe API；没有 Key 或返回 401 时使用内置的离线示例答案。后续代码不区分两种模式，便于先学习
控制流，再切换到真实模型观察概率和置信度。

> 学习提示：先顺序运行全部单元格，再回到“定义 state”或“定义问题”的单元格修改内容，重新运行后面的单元格。
> API Key 只从环境变量读取，不能写进 notebook。
""")

    md("## 0. 准备")
    md("### 0.1 安装依赖")
    code("%pip install -q -U typesafe-sdk")
    md("### 0.2 创建客户端")
    code("""import os
import statistics
import time
from pprint import pprint

from typesafe_sdk import (
    Choice,
    Score,
    Noul,
    TypeSafeClient,
    TypeSafeAuthenticationError,
)

API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
client = TypeSafeClient(api_key=API_KEY, model="jev-latest") if API_KEY else None
print("客户端已创建：模型=jev-latest，Key=", "已配置" if API_KEY else "未配置（将使用离线示例）")
""")
    md("### 0.3 离线响应与统一调用入口")
    code("""class _FakeAnswer:
    def __init__(self, type_, **values):
        self.type = type_
        for key, value in values.items():
            setattr(self, key, value)


class _FakeResponse:
    def __init__(self, answers):
        self.answers = answers
        self.nouls = {k: v for k, v in answers.items() if v.type == "noul"}
        self.choices = {k: v for k, v in answers.items() if v.type == "choice"}
        self.scores = {k: v for k, v in answers.items() if v.type == "score"}
        self.model = "jev-latest（离线示例）"
        self.usage = _FakeAnswer("usage", input_tokens=0, output_tokens=0)


class TS:
    offline = False
    _warned = False

    @classmethod
    def call(cls, state, questions, offline_answers):
        if client is None:
            cls.offline = True
            if not cls._warned:
                cls._warned = True
                print("⚠️ 未设置有效 TYPESAFE_API_KEY，以下输出使用内置离线示例。")
            return _FakeResponse(offline_answers)
        try:
            return client.system_one(state, questions)
        except TypeSafeAuthenticationError:
            cls.offline = True
            if not cls._warned:
                cls._warned = True
                print("⚠️ 未设置有效 TYPESAFE_API_KEY，以下输出使用内置离线示例。")
            return _FakeResponse(offline_answers)


def answer_line(name, answer):
    if answer.type == "noul":
        return f"{name}: noul={answer.noul:.2f}"
    if answer.type == "choice":
        return f"{name}: choice={answer.choice} confidence={answer.confidence:.2f}"
    return f"{name}: score={answer.score:.2f} confidence={answer.confidence:.2f}"


print("模式：", "离线示例" if TS.offline else "真实 API（首次调用后确定）")
""")
    md("### 0.4 连通性测试")
    code("""if client is None:
    TS.offline = True
    print("⚠️ API Key 未设置，后续单元格使用离线示例。")
else:
    try:
        ping = client.system_one("你好", {"is_greeting": Noul(instructions="这段文字是在打招呼吗？")})
        print("✅ API 连通正常，后续单元格会使用真实结果。")
    except TypeSafeAuthenticationError:
        TS.offline = True
        print("⚠️ API Key 无效，后续单元格使用离线示例。")
""")

    build(md, code)

    md("""## 小结

这本 notebook 的边界很清楚：TypeSafe 只负责受限、可编程的判断；排序、阈值、分组、重建文本和
函数分派都由 Python 代码完成。修改输入或问题后重新运行，就能观察“模型答案 → 确定性代码”的变化。
""")
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python", "version": "3.12"}
    return nb


def build_consistency_noul(md, code):
    md("""## 1. 自一致性：Noul

对同一份理赔状态重复提问，观察每个布尔判断的概率是否稳定；然后把中间概率标成 `uncertain`，
让业务代码把不确定结果交给人工审核，而不是强行变成 True / False。
""")
    md("### 1.1 定义理赔状态")
    code("""CLAIM = {
    "claim_type": "车险理赔",
    "description": "车辆在雨天打滑撞上护栏，车门凹陷但仍可缓慢行驶。保单刚过等待期。",
    "photos": "已提交车辆侧面和现场照片",
}
print("state 已定义：车险理赔，字段数=", len(CLAIM))
""")
    md("### 1.2 定义 Noul 评分量表")
    code("""QUESTIONS = {
    "covered": Noul(instructions="这份理赔是否属于保单承保范围？"),
    "repairable": Noul(instructions="车辆是否仍然可以维修，而不是必须报废？"),
    "fraud_flag": Noul(instructions="这份理赔是否存在明显的欺诈信号？"),
    "rental_eligible": Noul(instructions="客户是否符合租车替代服务的条件？"),
    "manual_review": Noul(instructions="这份理赔是否应该交给人工审核？"),
}
print("questions 已定义：", len(QUESTIONS), "个 Noul 问题")
""")
    md("### 1.3 重复调用并收集概率")
    code("""OFFLINE_RUNS = [
    {"covered": .84, "repairable": .93, "fraud_flag": .09, "rental_eligible": .47, "manual_review": .56},
    {"covered": .82, "repairable": .92, "fraud_flag": .11, "rental_eligible": .51, "manual_review": .59},
    {"covered": .85, "repairable": .94, "fraud_flag": .08, "rental_eligible": .49, "manual_review": .54},
    {"covered": .83, "repairable": .91, "fraud_flag": .10, "rental_eligible": .53, "manual_review": .58},
    {"covered": .84, "repairable": .92, "fraud_flag": .09, "rental_eligible": .50, "manual_review": .57},
]
N_RUNS = len(OFFLINE_RUNS)
runs = []
for index in range(N_RUNS):
    offline = {name: _FakeAnswer("noul", noul=value) for name, value in OFFLINE_RUNS[index].items()}
    response = TS.call(CLAIM, QUESTIONS, offline)
    sample = {name: answer.noul for name, answer in response.nouls.items()}
    runs.append(sample)
    print(f"第 {index + 1} 次：", " | ".join(f"{k}={v:.2f}" for k, v in sample.items()))
""")
    md("### 1.4 统计稳定性与不确定区间")
    code("""def noul_decision(probability):
    if 0.30 <= probability <= 0.70:
        return "uncertain"
    return "yes" if probability > 0.70 else "no"


for name in QUESTIONS:
    values = [sample[name] for sample in runs]
    deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    mean = statistics.mean(values)
    print(f"{name:18} mean={mean:.2f}  stdev={deviation:.3f}  decision={noul_decision(mean)}")
""")
    md("观察：`noul` 是“为真”的概率本身，没有额外的 confidence 字段。阈值是业务策略，不是模型返回的事实；把 0.30–0.70 留给人工审核，能保留模型的“不确定”信号。")


def build_consistency_choice(md, code):
    md("""## 1. 自一致性：Choice

对一条处于临界状态的审核帖子重复运行多个 Choice 问题。先观察标签是否稳定，再要求最高概率达到
`0.60` 才允许自动动作，否则返回 `uncertain`。
""")
    md("### 1.1 定义帖子和审核问题")
    code("""POST = {
    "author": "用户 1842",
    "text": "有人说这个功能会泄露数据，我没有证据，但大家最好先别用了。",
    "reports": 3,
}

QUESTIONS = {
    "moderation": Choice(
        instructions="这条帖子最适合采取哪种审核动作？",
        criteria={"keep": "保留帖子", "remove": "删除帖子", "escalate": "升级给人工审核"},
    ),
    "queue": Choice(
        instructions="这条帖子应该进入哪个队列？",
        criteria={"general": "普通队列", "threat": "潜在威胁队列", "spam": "垃圾内容队列"},
    ),
    "severity": Choice(
        instructions="这条帖子的风险等级是什么？",
        criteria={"low": "低风险", "medium": "中风险", "high": "高风险"},
    ),
}
print("state/questions 已定义：字段数=", len(POST), "，问题数=", len(QUESTIONS))
""")
    md("### 1.2 重复调用并保留完整概率")
    code("""OFFLINE_RUNS = [
    {"moderation": ("escalate", .58), "queue": ("threat", .64), "severity": ("medium", .57)},
    {"moderation": ("escalate", .62), "queue": ("threat", .61), "severity": ("medium", .55)},
    {"moderation": ("escalate", .59), "queue": ("general", .52), "severity": ("medium", .58)},
    {"moderation": ("keep", .51), "queue": ("threat", .60), "severity": ("medium", .56)},
    {"moderation": ("escalate", .60), "queue": ("threat", .63), "severity": ("medium", .59)},
]
runs = []
for row in OFFLINE_RUNS:
    offline = {}
    for name, (choice, confidence) in row.items():
        offline[name] = _FakeAnswer(
            "choice", choice=choice, confidence=confidence,
            probabilities={choice: confidence, "other": 1 - confidence},
        )
    response = TS.call(POST, QUESTIONS, offline)
    runs.append(response.choices)
    print(" | ".join(answer_line(name, answer) for name, answer in response.choices.items()))
""")
    md("### 1.3 置信度门控自动动作")
    code("""def choice_decision(answer, threshold=0.60):
    return answer.choice if answer.confidence >= threshold else "uncertain"


for run_number, answers in enumerate(runs, 1):
    actions = {name: choice_decision(answer) for name, answer in answers.items()}
    print(f"第 {run_number} 次：", actions)
""")
    md("观察：Choice 的标签可以跨次变化，尤其是接近的概率分布。把 `confidence` 作为自动动作的门槛，会把临界答案明确转交人工。")


def build_parallel(md, code):
    md("""## 1. 并行提问

把相互独立的问题放入一次 `system_one` 请求，再与逐条调用比较。批量请求的答案按 ID 返回，代码可以
只消费当前分支真正需要的字段。
""")
    md("### 1.1 定义文章状态与问题集合")
    code("""ARTICLE = '公司宣布下季度把客服、退款和安全审计流程统一到一个工作台。'
QUESTIONS = {
    "about_refund": Noul(instructions="这段文字是否提到退款？"),
    "about_security": Noul(instructions="这段文字是否提到安全审计？"),
    "topic": Choice(
        instructions="这段文字的主要主题是什么？",
        criteria={"product": "产品变化", "operations": "运营流程", "policy": "政策公告"},
    ),
    "urgency": Score(
        instructions="这段文字表达的紧迫程度",
        criteria=["没有紧迫性", "需要近期关注", "需要立即处理"],
    ),
}
print("state/questions 已定义：文章长度=", len(ARTICLE), "，问题数=", len(QUESTIONS))
""")
    md("### 1.2 一次请求回答全部问题")
    code("""OFFLINE = {
    "about_refund": _FakeAnswer("noul", noul=.81),
    "about_security": _FakeAnswer("noul", noul=.74),
    "topic": _FakeAnswer("choice", choice="operations", confidence=.72, probabilities={"operations": .72}),
    "urgency": _FakeAnswer("score", score=1.15, confidence=.68, probabilities={0: .15, 1: .70, 2: .15}),
}
batch_start = time.perf_counter()
batch = TS.call(ARTICLE, QUESTIONS, OFFLINE)
batch_elapsed = time.perf_counter() - batch_start
for name, answer in batch.answers.items():
    print(answer_line(name, answer))
print(f"批量请求耗时（离线时仅供参考）：{batch_elapsed * 1000:.1f} ms")
""")
    md("### 1.3 逐条调用对照")
    code("""if TS.offline:
    print("当前为离线模式，跳过逐条网络计时；批量答案已经完整展示。")
else:
    single_start = time.perf_counter()
    for name, question in QUESTIONS.items():
        single = client.system_one(ARTICLE, {name: question})
        print(answer_line(name, single.answers[name]))
    single_elapsed = time.perf_counter() - single_start
    print(f"逐条调用耗时：{single_elapsed * 1000:.1f} ms")
""")
    md("观察：并行提问并不要求代码使用每个答案。先一次取回独立判断，再在 Python 中按业务分支消费结果，通常比串行追问更快。")


def build_rerank(md, code):
    md("""## 1. 重排序（Re-ranking）

对每个“查询–候选”对提出一个 Noul 问题，直接按返回概率排序。这里不把概率粗暴地变成固定阈值，
而是保留相对顺序。
""")
    md("### 1.1 定义查询和候选段落")
    code("""QUERY = "如何撤销一笔尚未结算的转账？"
CANDIDATES = [
    "你可以在转账详情页点击撤销；已结算的转账需要联系客服。",
    "银行卡挂失后，请在安全中心重新设置登录密码。",
    "退款通常会在五个工作日内原路返回。",
    "如果转账已经结算，收款方需要主动退回资金。",
]
print("查询已定义：候选数=", len(CANDIDATES))
""")
    md("### 1.2 为每个候选构造问题并调用")
    code("""scores = []
for index, passage in enumerate(CANDIDATES):
    question = {"relevant": Noul(instructions="这段候选内容是否直接回答用户的问题？")}
    offline_value = [0.93, 0.07, 0.19, 0.78][index]
    response = TS.call({"query": QUERY, "candidate": passage}, question,
                       {"relevant": _FakeAnswer("noul", noul=offline_value)})
    probability = response.nouls["relevant"].noul
    scores.append((probability, passage))
    print(f"候选 {index + 1}: relevance={probability:.2f}  {passage}")
""")
    md("### 1.3 排序并设置展示门槛")
    code("""ranked = sorted(scores, key=lambda item: item[0], reverse=True)
for rank, (probability, passage) in enumerate(ranked, 1):
    label = "推荐" if probability >= 0.50 else "低相关"
    print(f"{rank}. {label} {probability:.2f}  {passage}")
""")
    md("观察：排序使用概率的相对大小；`0.50` 这里只是决定是否展示的应用阈值，不改变排名。")


def build_semantic_find(md, code):
    md("""## 1. 逐行语义搜索

把文档拆成行，先判断每行是否回答查询，再把最高概率的行作为结果。第二个 Noul 用来判断“文档里是否
根本存在答案”，这让空结果和低相关结果可以分开处理。
""")
    md("### 1.1 定义查询和文档行")
    code("""QUERY = "如何修改账单邮箱？"
LINES = [
    "你可以在个人资料页修改姓名和头像。",
    "账单邮箱位于设置 → 通知 → 账单中，修改后会立即生效。",
    "发票下载链接会发送到当前账单邮箱。",
    "安全邮箱用于接收登录提醒，不等同于账单邮箱。",
]
print("查询和文档已定义：行数=", len(LINES))
""")
    md("### 1.2 逐行判断语义相关性")
    code("""OFFLINE = [0.08, 0.94, 0.51, 0.18]
matches = []
for line, offline_value in zip(LINES, OFFLINE):
    response = TS.call({"query": QUERY, "line": line},
                       {"matches": Noul(instructions="这一行是否直接回答查询？")},
                       {"matches": _FakeAnswer("noul", noul=offline_value)})
    probability = response.nouls["matches"].noul
    matches.append((probability, line))
    print(f"{probability:.2f}  {line}")
""")
    md("### 1.3 判断是否存在答案并选出最佳行")
    code("""best_probability, best_line = max(matches)
answer_exists = best_probability >= 0.50
print("文档中存在答案：", answer_exists)
if answer_exists:
    print(f"最佳匹配（{best_probability:.2f}）：{best_line}")
else:
    print("没有足够相关的行，转交更广泛的搜索或人工处理。")
""")
    md("观察：把“哪一行最相关”和“是否存在答案”拆成两个判断，代码就能区分命中、弱命中和真正的空结果。")


def build_autoformat(md, code):
    md("""## 1. 结构恢复

判断相邻文本行之间的换行是否切断了同一句话，用 Noul 得到连接概率，再按阈值重建段落。
""")
    md("### 1.1 定义被错误换行的文本")
    code("""LINES = [
    "TypeSafe 返回结构化答案，",
    "代码可以直接消费这些答案。",
    "每个问题都应当足够窄，",
    "让模型在一秒内完成判断。",
    "这是一个新的段落。",
]
print("待恢复文本已定义：行数=", len(LINES))
""")
    md("### 1.2 判断每个相邻行是否属于同一句")
    code("""JOIN_PROBABILITIES = [.91, .87, .78, .12]
joins = []
for index in range(len(LINES) - 1):
    pair = {"left": LINES[index], "right": LINES[index + 1]}
    response = TS.call(pair,
                       {"same_sentence": Noul(instructions="换行是否把同一个句子切开了？")},
                       {"same_sentence": _FakeAnswer("noul", noul=JOIN_PROBABILITIES[index])})
    probability = response.nouls["same_sentence"].noul
    joins.append(probability)
    print(f"{probability:.2f}  {LINES[index]} + {LINES[index + 1]}")
""")
    md("### 1.3 根据概率重建段落")
    code("""paragraphs = [LINES[0]]
for index, probability in enumerate(joins):
    if probability >= 0.50:
        paragraphs[-1] += LINES[index + 1]
    else:
        paragraphs.append(LINES[index + 1])

print("\\n\\n".join(paragraphs))
""")
    md("观察：模型只判断相邻两行是否属于同一句，拼接和分段仍由代码控制。调高阈值会产生更多段落，调低阈值会更激进地合并。")


def build_function_calling(md, code):
    md("""## 1. 函数调用

先用 Choice 选择确定的函数，再由代码校验参数并调用本地函数。模型不会直接执行副作用。
""")
    md("### 1.1 定义用户请求和函数目录")
    code("""REQUEST = "请查询订单 TS-2048 的物流状态，并告诉我预计送达日期。"
FUNCTIONS = {
    "lookup_order": lambda order_id: f"订单 {order_id}：运输中，预计周五送达。",
    "refund_order": lambda order_id: f"订单 {order_id}：退款申请已创建。",
    "update_address": lambda order_id: f"订单 {order_id}：地址修改需要人工确认。",
}
QUESTIONS = {
    "function": Choice(
        instructions="用户最想执行哪个函数？",
        criteria={
            "lookup_order": "查询订单物流或状态",
            "refund_order": "申请订单退款",
            "update_address": "修改订单收货地址",
        },
    ),
    "needs_confirmation": Noul(instructions="执行这个函数前是否需要用户再次确认？"),
}
print("函数目录和问题已定义：函数数=", len(FUNCTIONS), "，问题数=", len(QUESTIONS))
""")
    md("### 1.2 调用并让代码完成分派")
    code("""OFFLINE = {
    "function": _FakeAnswer("choice", choice="lookup_order", confidence=.96,
                             probabilities={"lookup_order": .96}),
    "needs_confirmation": _FakeAnswer("noul", noul=.08),
}
response = TS.call(REQUEST, QUESTIONS, OFFLINE)
for name, answer in response.answers.items():
    print(answer_line(name, answer))

selected = response.choices["function"].choice
if selected not in FUNCTIONS:
    raise ValueError(f"模型返回了未注册函数：{selected}")
if response.nouls["needs_confirmation"].noul >= 0.50:
    print("→ 先请求用户确认，不执行副作用。")
else:
    print("→ 确定性代码执行：", FUNCTIONS[selected]("TS-2048"))
""")
    md("观察：Choice 只决定“调用哪个已注册函数”，函数本身、参数校验和副作用都留在 Python 代码中。")


def build_skill_suggestion(md, code):
    md("""## 1. 技能推荐

先对技能名册中的每一项做廉价的相关性判断，再从候选中选出最合适的技能。推荐结果仍由代码根据
置信度决定是否展示。
""")
    md("### 1.1 定义用户请求和技能名册")
    code("""REQUEST = "帮我把本周会议纪要整理成行动项，并安排下周跟进会议。"
SKILLS = {
    "calendar": "创建和修改日历日程，查询忙闲和会议室",
    "meeting_summary": "整理会议纪要，提取决定、行动项和负责人",
    "task": "创建待办任务，分配成员并跟踪状态",
    "mail": "搜索、起草、回复和发送邮件",
}
print("技能名册已定义：技能数=", len(SKILLS))
""")
    md("### 1.2 先做宽召回：每个技能一个 Noul")
    code("""OFFLINE = {"calendar": .88, "meeting_summary": .94, "task": .79, "mail": .18}
ranked = []
for name, description in SKILLS.items():
    response = TS.call({"request": REQUEST, "skill": description},
                       {"relevant": Noul(instructions="这个技能是否可能帮助完成用户请求？")},
                       {"relevant": _FakeAnswer("noul", noul=OFFLINE[name])})
    probability = response.nouls["relevant"].noul
    ranked.append((probability, name))
    print(f"{probability:.2f}  {name}: {description}")
ranked.sort(reverse=True)
SHORTLIST = [name for _, name in ranked[:3]]
print("候选前三名：", SHORTLIST)
""")
    md("### 1.3 在候选中选择主技能")
    code("""criteria = {name: SKILLS[name] for name in SHORTLIST}
question = {"best_skill": Choice(instructions="哪个候选技能最适合先处理请求？", criteria=criteria)}
offline_choice = SHORTLIST[1] if len(SHORTLIST) > 1 else SHORTLIST[0]
response = TS.call({"request": REQUEST, "shortlist": criteria}, question,
                   {"best_skill": _FakeAnswer("choice", choice=offline_choice, confidence=.86,
                                              probabilities={offline_choice: .86})})
answer = response.choices["best_skill"]
print(f"推荐技能：{answer.choice}（confidence={answer.confidence:.2f}）")
if answer.confidence < 0.60:
    print("→ 置信度不足，交给人工选择。")
else:
    print("→ 先加载技能：", SKILLS[answer.choice])
""")
    md("观察：宽召回使用 Noul 判断“是否值得考虑”，候选重排使用 Choice 做相对选择；两者回答的是不同问题。")


BUILDERS = {
    "consistency_noul": ("自一致性：Noul", "/cookbooks/consistency_noul_cookbook/", "重复 Noul 量表并显式处理不确定概率。", build_consistency_noul),
    "consistency_choice": ("自一致性：Choice", "/cookbooks/consistency_choice_cookbook/", "重复 Choice 审核标签并用置信度门控自动动作。", build_consistency_choice),
    "parallel_questions": ("并行提问", "/cookbooks/parallel_questions/", "比较一次批量提问与逐条提问，并观察按 ID 取答案。", build_parallel),
    "rerank_typesafe": ("重排序（Re-ranking）", "/cookbooks/rerank_typesafe/", "用 Noul 概率对候选内容进行语义相关性排序。", build_rerank),
    "semantic_find": ("逐行语义搜索", "/cookbooks/semantic_find/", "逐行找答案并区分命中与空结果。", build_semantic_find),
    "autoformat": ("结构恢复", "/cookbooks/autoformat/", "判断换行边界并从纯文本重建段落。", build_autoformat),
    "function_calling": ("函数调用", "/cookbooks/function_calling/", "用 Choice 选择注册函数，再由代码执行分派。", build_function_calling),
    "skill_suggestion": ("技能推荐", "/cookbooks/skill_suggestion/", "先用 Noul 宽召回，再用 Choice 选择主技能。", build_skill_suggestion),
}


def main():
    OUT.mkdir(exist_ok=True)
    for slug, (title, source, purpose, builder) in BUILDERS.items():
        notebook = make_notebook(title, source, purpose, builder)
        path = OUT / f"{slug}_experiments.ipynb"
        with path.open("w", encoding="utf-8") as handle:
            nbf.write(notebook, handle)
        print(f"written: {path} | cells: {len(notebook.cells)}")


if __name__ == "__main__":
    main()
