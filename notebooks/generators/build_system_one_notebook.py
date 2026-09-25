"""生成 System One 章：退款场景中的独立判断与代码组合。"""
from notebook_support import Chapter, sources


def build():
    c = Chapter("system_one", "TypeSafe System One 实验（System One Lab）", "concepts/system-one",
                "复刻消息、交易、政策的退款例子，理解共享状态、独立问题和确定性检查的边界。",
                "| 1 | 三个退款判断 |\n| 2 | 代码组合与人工复核 |\n| 3 | 只改 ID 的对照实验 |")
    c.prepare()
    c.code('''REFUND_OFFLINE = {
    "refund_requested": _FakeAnswer("noul", noul=0.98),
    "duplicate_charge": _FakeAnswer("noul", noul=0.94),
    "policy_supports_refund": _FakeAnswer("noul", noul=0.95),
}
RENAMED_OFFLINE = {"q1": REFUND_OFFLINE["refund_requested"]}''')
    c.md("""## 📖 理论根基：聚焦判断与组合

System One 强调快速、受约束的判断。模型理解文本，但不会替本例生成退款解释或执行支付操作。
名称借用了“系统 1”的直觉判断概念；这不是对人的思考过程的科学复现声明。

原文退款流程是：构造客户消息、相关交易、退款政策；一起提出独立问题；由代码结合确定性检查再路由。
每个问题必须独立读完 state 就能回答，不能把“上一个问题为真”作为隐含前提。
Noul 返回概率，不返回独立 confidence。
""" + "\n\n" + sources("primitives") + " · " + sources("concepts/state"))
    c.md("""## 1. 复刻退款场景

### 原理

客户是否要求退款、是否存在重复收费的证据、政策是否支持退款，是三个不同属性。
把证据放在一起，让每个问题各自检查；支付权限和交易唯一性则由程序核验。
""")
    c.step("### 第一步：准备状态\n\n字段中的 captured 是交易系统状态码，保留英文；消息与政策使用中文。",
           '''REFUND_STATE = {
    "message": "订单 A-104 被扣了两次款，请退还重复扣取的那一笔。",
    "order": {
        "id": "A-104",
        "charges": [
            {"id": "C-1", "amount_usd": 49, "status": "captured"},
            {"id": "C-2", "amount_usd": 49, "status": "captured"},
        ],
    },
    "refund_policy": "同一订单的重复扣款可以退还重复部分。",
}''')
    c.step("### 第二步：每个问题直接引用证据", '''REFUND_QUESTIONS = {
    "refund_requested": Noul(instructions="客户在 `message` 中是否明确要求退款？"),
    "duplicate_charge": Noul(instructions="`message` 与 `order.charges` 是否表明同一订单被重复扣款？"),
    "policy_supports_refund": Noul(instructions=(
        "根据 `message`、`order.charges` 与 `refund_policy`，政策是否支持退还本案重复扣款？")),
}''', "第三问直接看事实与政策，没有引用前两问的预测。这就是同一次请求里的独立性。")
    c.step("### 第三步：一次调用", '''refund_response = ts.call(REFUND_STATE, REFUND_QUESTIONS, REFUND_OFFLINE, "退款三问")''')
    c.step("### 第四步：逐项观察", '''show(refund_response)''',
           "三个概率都高不等于可以立即转账。金额、权限、幂等记录及支付接口约束仍是业务系统的责任。")
    c.md("""## 2. 在代码中组合

### 📖 理论根基

能精确计算的条件直接用代码。下面只核对本例所需的基础记录，并输出处理建议，
不连接支付系统，也不声称覆盖真实退款的全部业务条件。
0.8 是教学阈值，需要用真实业务标签与错误成本另行评估。
""")
    c.step("先定义确定性检查。", '''def basic_record_check(state):
    charges = state["order"]["charges"]
    return (
        len(charges) == 2
        and len({x["id"] for x in charges}) == 2
        and all(x["status"] == "captured" for x in charges)
        and charges[0]["amount_usd"] == charges[1]["amount_usd"]
    )


DECISION_THRESHOLD = 0.8''')
    c.step("组合函数只接受已返回的答案。", '''def refund_recommendation(state, response):
    if not basic_record_check(state):
        return {"route": "review", "reason": "交易记录需要核对"}
    probabilities = [response.nouls[key].noul for key in REFUND_QUESTIONS]
    if all(p >= DECISION_THRESHOLD for p in probabilities):
        return {"route": "refund_review", "reason": "建议进入退款审核流程"}
    return {"route": "review", "reason": "至少一个语义判断未达到教学阈值"}''',
           "多个概率的乘积不自动成为总体成功概率；问题被独立评估不代表这些事件在统计上相互独立。")
    c.step("应用组合函数。", '''recommendation = refund_recommendation(REFUND_STATE, refund_response)''')
    c.step("显示建议与触发原因。", '''print(json.dumps(recommendation, ensure_ascii=False, indent=2))''',
           "如果实际概率未达到阈值，应保留复核结果。不能为了展示‘通过’而改写模型返回。")
    c.md("""## 3. 问题 ID 的对照实验

原理：ID 用来匹配结果。完整语义必须放进 instructions。
先前请求中的 `refund_requested` 改名为 `q1`，问题文本保持不变。
这是两次服务请求的观察；即使出现数值差异，也不能只凭一对结果认定 ID 改变了模型语义。
""")
    c.step("只更换问题 ID。", '''RENAMED_QUESTIONS = {"q1": REFUND_QUESTIONS["refund_requested"]}''')
    c.step("发送对照请求。", '''renamed_response = ts.call(REFUND_STATE, RENAMED_QUESTIONS, RENAMED_OFFLINE, "问题 ID 对照")''')
    c.step("比较字段映射和实际差值。", '''original_p = refund_response.nouls["refund_requested"].noul
renamed_p = renamed_response.nouls["q1"].noul
print({"原 ID 概率": original_p, "新 ID 概率": renamed_p,
       "绝对差": abs(original_p - renamed_p),
       "实际返回 ID": list(renamed_response.answers)})''',
           "不要在真实实验中断言两个浮点数必须完全相等。本例验证访问方式，并用于记录重复请求的实际行为。")
    c.finish("| 工作 | 负责方 |\n|---|---|\n| 解读消息与政策 | 模型的原子问题 |\n| 核对金额、交易 ID、权限 | 确定性代码 |\n| 组合与路由 | 应用程序 |",
             "如果第三个问题必须根据第一个问题的答案改写，应该怎样实现？为什么不能写‘如果 refund_requested 为真就……’？",
             "先执行第一轮请求，在 Python 中读取答案，再构造第二轮 state 与问题。同请求的 ID 不会把一个问题的答案传给另一个问题。",
             "下一章：[State](state_experiments.ipynb)。")
    return c.save()


if __name__ == "__main__":
    print(build())
