"""生成 State 章：格式控制实验与上下文增量实验。"""
from notebook_support import Chapter, sources


def build():
    c = Chapter("state", "03 · TypeSafe 状态实验（State Lab）", "concepts/state",
                "使用字符串、对象和数组表达相同事实，再单独研究订单与政策上下文的作用。",
                "| 1 | 同事实、不同格式 |\n| 2 | 添加订单与政策 |\n| 3 | 字段白名单与避免标签泄漏 |")
    c.prepare()
    c.code('''FORMAT_OFFLINE = [
    {"refund_requested": _FakeAnswer("noul", noul=0.96)},
    {"refund_requested": _FakeAnswer("noul", noul=0.96)},
    {"refund_requested": _FakeAnswer("noul", noul=0.96)},
]
CONTEXT_OFFLINE = [
    {"support": fake_choice({"supported": 0.1, "unsupported": 0.1, "insufficient": 0.8}, 0.76)},
    {"support": fake_choice({"supported": 0.93, "unsupported": 0.03, "insufficient": 0.04}, 0.89)},
]''')
    c.md("""## 📖 理论根基：state 是提供给判断者的材料

state 放内容、事实和相关记录；questions 放评判任务。需要比较的事实放在同一状态里，
例如客户消息、交易记录和退款政策。对象中的具名字段有助于表达各部分关系；简单消息也可以直接用字符串。

state 的数组表达一组材料，不代表多条输入的批量 API。同一请求仍是一个 state，所有问题共享它。
Jev 当前的文本接口不直接接收图片、音频和视频。中文输入的效果需要在本任务上验证。
""" + "\n\n" + sources("primitives") + " · " + sources("models"))
    c.md("""## 1. 控制实验 A：只改变表达格式

原理：固定订单号与消息，分别用字符串、对象、数组表达。不能在对象版额外加入政策，再把结果改善归因于“对象更好”。
三种表达的内容一致，但序列化后的文本仍有差异；一次小样本比较不能推断普遍优劣。
""")
    c.step("### 第一步：固定事实", '''MESSAGE = "订单 A-104 被扣了两次款，请退还重复扣取的那一笔。"
STATE_VARIANTS = {
    "字符串": "订单号：A-104。客户消息：" + MESSAGE,
    "对象": {"order_id": "A-104", "message": MESSAGE},
    "数组": ["订单号：A-104", "客户消息：" + MESSAGE],
}''')
    c.step("### 第二步：固定问题\n\n这里不用只在对象中存在的路径，保证问题文本也一致。", '''FORMAT_QUESTIONS = {
    "refund_requested": Noul(instructions="材料中的客户是否明确要求退还款项？"),
}''', "固定模型、题目与事实，记录格式变化。概率不同并不自动代表某个结果更准确。")
    c.step("### 第三步：逐一调用", '''format_responses = {
    name: ts.call(state, FORMAT_QUESTIONS, FORMAT_OFFLINE[i], "格式对照：" + name)
    for i, (name, state) in enumerate(STATE_VARIANTS.items())
}''')
    c.step("### 第四步：显示实际观测", '''for name, response in format_responses.items():
    print({"格式": name, "退款请求概率": response.nouls["refund_requested"].noul})''',
           "离线预览中人为设成相同数值，不能据此声称模型对格式不敏感。真实实验应原样记录全部返回。")
    c.md("""## 2. 控制实验 B：固定对象格式，再补充事实

### 📖 理论根基

原文展示了包含对话、订单和政策的完整状态。这里沿用重复扣款场景，比较材料不足与材料完整两种情况。
把‘信息不足’作为显式选项，避免让模型必须在支持／不支持之间猜测。
""")
    c.step("先定义不包含政策和支付证据的对象。", '''MINIMAL_STATE = {"ticket": {"message": MESSAGE}, "order_id": "A-104"}''')
    c.step("再补充原文场景中的支持对话、订单和政策。", '''ENRICHED_STATE = {
    "ticket": {
        "message": MESSAGE,
        "support_reply": "我们正在核查扣款记录。",
    },
    "order": {
        "id": "A-104",
        "charges": [
            {"amount_usd": 49, "status": "captured"},
            {"amount_usd": 49, "status": "captured"},
        ],
    },
    "refund_policy": "同一订单的重复扣款可以退还重复部分。",
}''', "新增的是可供判断的证据，不是‘正确答案为 supported’这种评测标签。")
    c.step("两种状态使用同一个问题。", '''CONTEXT_QUESTIONS = {
    "support": Choice(
        instructions="仅按提供的扣款证据和退款政策，能否支持客户的退款请求？不要补造缺失事实。",
        criteria={
            "supported": "必要证据与政策已提供，并支持退款",
            "unsupported": "必要证据与政策已提供，但不支持退款",
            "insufficient": "缺少必要证据或政策，无法完成判断",
        },
    ),
}''')
    c.step("执行上下文对照。", '''context_responses = [
    ts.call(state, CONTEXT_QUESTIONS, CONTEXT_OFFLINE[i], label)
    for i, (state, label) in enumerate([
        (MINIMAL_STATE, "上下文：只有客户消息"),
        (ENRICHED_STATE, "上下文：增加交易与政策"),
    ])
]''', "这是两个状态各发一次请求。不能把两者的差异直接称为结构化格式带来的提升。")
    c.step("查看选项和不确定性。", '''for name, response in zip(["材料不足", "材料完整"], context_responses):
    print(name)
    show(response)''',
           "预期前者更可能选 insufficient，但这只是实验假设。如果真实返回不符合预期，应检查问题边界并记录失败。")
    c.md("""## 3. 字段白名单：模型该看什么

原理：数据库记录常含人工标签、内部备注和无关信息。显式挑选输入字段，让实验的数据边界可检查。
下面是本教程的工程扩展：它补充输入构造方法，不新增模型调用。
""")
    c.step("构造一条含评测答案的教学记录。", '''RAW_RECORD = {
    "message": MESSAGE, "order_id": "A-104",
    "expected_label": "supported", "split": "holdout",
    "internal_note": "用于人工验收的记录，不发送模型",
}''')
    c.step("白名单函数只返回所需事实。", '''def make_state(record):
    return {"message": record["message"], "order_id": record["order_id"]}


filtered_state = make_state(RAW_RECORD)''')
    c.step("检查真正将发送的字段。", '''print(json.dumps(filtered_state, ensure_ascii=False, indent=2))
assert "expected_label" not in filtered_state
assert "split" not in filtered_state''',
           "这是确定性输入检查，适合断言。真实预测是否符合人工标签则应进入评估统计。")
    c.finish("| 对照 | 保持不变 | 改变什么 |\n|---|---|---|\n| A | 事实、问题、模型 | 格式 |\n| B | 对象格式、问题、模型 | 可用事实 |",
             "为至少五条不同消息设计格式对照表；对每条消息保持事实一致。你还需要哪些记录才能让别人复现？",
             "保存完整 state、instructions、criteria、请求模型、实际模型、SDK 版本和运行日期。多样本报告差异；不要只挑最支持结论的一条。",
             "下一章：[原语](04_原语.ipynb)。")
    return c.save()


if __name__ == "__main__":
    print(build())
