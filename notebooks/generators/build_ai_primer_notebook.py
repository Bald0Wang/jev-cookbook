"""生成 AI 入门章：训练目标、群体校准与小型概率观测。"""
from notebook_support import Chapter, sources


def build():
    c = Chapter("ai_primer", "TypeSafe AI 入门实验（AI Primer Lab）", "introduction/machine-learning-primer",
                "理解文档中的三种训练目标，用手工数据解释校准，并把数学演示与真实模型观测分开。",
                "| 1 | RLHF、RLVR、RLCD 与机器接口 |\n| 2 | 人工概率实验 |\n| 3 | 三条中文消息的 Noul 探针 |")
    c.prepare()
    c.code('''REFUND_OFFLINE = [
    {"refund_requested": _FakeAnswer("noul", noul=0.97)},
    {"refund_requested": _FakeAnswer("noul", noul=0.03)},
    {"refund_requested": _FakeAnswer("noul", noul=0.43)},
]''')
    c.md("""## 1. 📖 理论根基：训练目标与输出契约

机器原生智能是 TypeSafe 对产品方向的描述：软件需要容易解析、检查、测试和记录的输出。
文档关于未来机器交互占比的说法属于愿景，本教程不把它当作已验证的行业统计。

| 方法 | 名称 | 文档强调的优化目标 |
|---|---|---|
| RLHF | 基于人类反馈的强化学习 | 人们偏好的回答 |
| RLVR | 使用可验证奖励的强化学习 | 能由规则或评估器验证的结果 |
| RLCD | 面向校准决策的强化学习 | TypeSafe 描述的决策与概率输出 |

这张表用于理解产品文档，不是断言所有聊天模型都只有一种训练方法。
人类偏好与业务可靠性并不等价；动听、自信的说法仍可能缺少依据。
文档借 mode dropping 说明偏好优化可能缩窄输出多样性，不能由此推断每个 RLHF 模型必然不可靠。
""")
    c.md("""## 2. 数学演示：0.8 到底意味着什么

### 📖 理论根基

考虑一批事件，其中每件事都被预测有 0.8 的概率发生。若长期发生频率也接近 80%，这是校准的证据之一。
单条预测发生或没发生，都不能独立证明整套系统校准或失准。有限样本还会有抽样波动。

下面是**人工构造的数学数据**，不调用 API，不代表 Jev 的测试集或模型效果。
""" + "\n\n" + sources("confidence"))
    c.step("先构造两个概率组，各 20 条事件。1 表示事件发生，0 表示没有发生。",
           '''MATH_GROUPS = {
    0.2: [1] * 4 + [0] * 16,
    0.8: [1] * 16 + [0] * 4,
}''')
    c.step("计算每组的平均预测概率与发生频率。",
           '''calibration_rows = [
    {"预测概率": probability, "样本数": len(labels),
     "发生频率": sum(labels) / len(labels)}
    for probability, labels in MATH_GROUPS.items()
]''', "这两个组被特意构造成频率匹配，目的是解释定义。不能把该结果归功于模型。")
    c.step("显示结果并观察组内仍然存在的失败。", '''print(json.dumps(calibration_rows, ensure_ascii=False, indent=2))
print("预测为 0.8 的这一组，仍有", MATH_GROUPS[0.8].count(0), "次事件没有发生")''',
           "校准良好与单次必然正确是两回事。预测所有事件都为整体基率也可能校准，却不擅长区分个例。")
    c.step("扩展：用 Brier 分数同时观察概率与二元标签的距离。越小越好，但它不是纯校准误差。",
           '''def brier(probabilities, labels):
    if not labels or len(probabilities) != len(labels):
        raise ValueError("概率与标签必须非空且等长")
    return sum((p - y) ** 2 for p, y in zip(probabilities, labels)) / len(labels)


LABELS = MATH_GROUPS[0.2] + MATH_GROUPS[0.8]
PROBABILITIES = [0.2] * 20 + [0.8] * 20
OVERCONFIDENT = [0.01] * 20 + [0.99] * 20''')
    c.step("比较两个手工预测器。", '''print({"匹配组内频率": brier(PROBABILITIES, LABELS),
       "人为推向极端": brier(OVERCONFIDENT, LABELS)})''',
           "同样的事件标签下，把概率推向极端可能更差。真实评测还要报告数据来源、样本量、分组与任务范围。")
    c.md("""## 3. 小型探针：明确、否定与模糊的退款请求

原理：观察同一个命题对不同消息返回什么概率。这里新增三条教学场景，帮助理解 AI 入门中的概率概念。
三条消息不足以评估校准；它们只是接口与行为观察。模糊消息也不保证落入某个置信区间。
""")
    c.step("准备三条中文消息。", '''MESSAGES = [
    "订单扣了两次款，请退还重复扣取的那一笔。",
    "我不需要退款，只想问下一张发票什么时候出。",
    "这个扣款你们看着处理一下吧。",
]''')
    c.step("定义任务：只判断是否明确提出退款，不猜测未表达的意图。", '''REFUND_QUESTIONS = {
    "refund_requested": Noul(instructions="客户是否明确要求退款或退还款项？仅抱怨扣款不算明确请求。"),
}''', "三个输入是三个 state，需要三次调用。它们不是对同一个 state 提三个不同问题。")
    c.step("依次执行探针。", '''refund_responses = [
    ts.call(message, REFUND_QUESTIONS, REFUND_OFFLINE[i], f"退款措辞探针 {i + 1}")
    for i, message in enumerate(MESSAGES)
]''')
    c.step("记录真实返回，不预填‘模型一定降低置信度’的结论。", '''for message, response in zip(MESSAGES, refund_responses):
    print({"消息": message, "退款请求概率": response.nouls["refund_requested"].noul})''',
           "观察明确否定与明确请求是否区分开；模糊消息的数值应原样记录。Noul 的不确定性直接看概率，不能访问不存在的 confidence。")
    c.finish("| 材料 | 可以支持什么结论 |\n|---|---|\n| 人工概率表 | 校准定义与数学计算 |\n| 三条 live 探针 | 本次输入下的实际模型行为 |\n| 独立标注的大样本 | 才适合进一步评估校准与业务效果 |",
             "为什么不能把本章三条消息重复请求一百次，然后声称完成了中文退款意图的校准评估？",
             "重复请求只覆盖三个输入，不能代表业务输入分布。应收集独立样本、定义标注标准、保留未用于调题的测试集，并按概率分组报告样本量和频率。",
             "下一章：[System One](system_one_experiments.ipynb)。数学实验属于教学扩展，不是在训练或复现 RLCD。")
    return c.save()


if __name__ == "__main__":
    print(build())
