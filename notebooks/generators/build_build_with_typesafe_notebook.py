"""生成构建章：复刻官方工作流及结构化问题示例。"""
from notebook_support import Chapter, sources


def build():
    c = Chapter("build_with_typesafe", "TypeSafe 应用构建实验（Application Building Lab）",
                "concepts/how-to-build-with-system-one",
                "复刻官方客服分流，拆解凭据信号，记录每个分支的覆盖情况，并练习结构化问题。",
                "| 1 | 架构与确定性规则 |\n| 2 | 中文客服工单的七个问题 |\n| 3 | 多场景探针与分支覆盖 |\n| 4 | 航班、嵌套状态、候选记录、虚拟卡与工具轨迹 |")
    c.prepare()
    c.code('''def workflow_fixture(topic, confidence=0.93, risk=0.02, frustration=0):
    other_p = (1 - confidence) / 2
    return {
        "topic": fake_choice({k: confidence if k == topic else other_p
                              for k in ["billing", "orders", "account"]}, confidence),
        "requests_credentials": _FakeAnswer("noul", noul=risk),
        "sender_identity_mismatch": _FakeAnswer("noul", noul=risk),
        "unexpected_reward": _FakeAnswer("noul", noul=risk),
        "refund_requested": _FakeAnswer("noul", noul=0.94 if topic == "billing" else 0.03),
        "mentions_open_order": _FakeAnswer("noul", noul=0.95 if topic == "orders" else 0.04),
        "frustration": fake_score({i: float(i == frustration) for i in range(3)},
            ["平静且客观", "不满但保持礼貌", "非常愤怒或威胁离开"], 0.93),
    }


WORKFLOW_OFFLINE = {
    "closed": workflow_fixture("billing"),
    "billing": workflow_fixture("billing"),
    "orders": workflow_fixture("orders"),
    "account_normal": workflow_fixture("account"),
    "account_high": workflow_fixture("account", frustration=2),
    "quarantine": workflow_fixture("account", risk=0.96),
    "review_spam": workflow_fixture("account", risk=0.5),
    "review_topic": workflow_fixture("billing", confidence=0.42),
}''')
    c.md("这些人工答案特意覆盖代码的八条路径。真实探针不保证命中相同路径；本章末尾会列出实际观察到和未观察到的分支。")
    c.code('''FLIGHT_OFFLINE = {"policy_supports_refund": _FakeAnswer("noul", noul=0.97)}
NESTED_OFFLINE = {
    "duplicate_charge": _FakeAnswer("noul", noul=0.95),
    "password_reset_supported": _FakeAnswer("noul", noul=0.96),
}
RECORD_OFFLINE = {"same_as_record_18": _FakeAnswer("noul", noul=0.94)}
CARD_OFFLINE = {"card_help_topic": fake_choice({
    "get_disposable_virtual_card": 0.03, "disposable_card_limits": 0.97}, 0.95)}
TRACE_OFFLINE = {key: _FakeAnswer("noul", noul=probability) for key, probability in {
    "geocode_tool_is_relevant": 0.98, "geocode_location_matches": 0.98,
    "geocode_arguments_match_schema": 0.98, "geocode_result_matches_call": 0.98,
    "weather_tool_is_relevant": 0.98, "weather_arguments_match_schema": 0.97,
    "weather_uses_geocoded_coordinates": 0.98, "weather_date_matches": 0.98,
    "weather_unit_matches": 0.02,
}.items()}''')
    c.md("""## 1. 📖 理论根基：三种架构与八条设计建议

| 架构 | 谁组织下一步 | 本章联系 |
|---|---|---|
| 传统软件 | 预先编写的分支 | 日期、状态、金额比较直接计算 |
| LLM 智能体 | 模型参与选择动作与工具 | 开放任务中可用，但需要监督与约束 |
| AI 驱动的软件 | 代码组织，模型提供狭窄判断 | 下面的客服工作流 |

依次实践：能用代码就用代码；只送相关上下文；给输入命名；分解问题；
必要时结构化 instructions 和 criteria；批量提出独立问题；代码组合；按不确定性路由。

结构化、并行、可比较是接口与架构能力。重复稳定性、具体速度和中文表现需要实测，不能用文档的宣传性数字代替本项目记录。
""")
    c.step("### 先运行确定性规则\n\n复刻逾期发票例子：日期差不用询问模型。只返回标签，不触发实际催收。",
           '''from datetime import date

TODAY = date(2026, 9, 22)
INVOICE_DUE = date(2026, 8, 1)
days_overdue = (TODAY - INVOICE_DUE).days
invoice_route = "collections_review" if days_overdue > 30 else "normal"''')
    c.step("显示确定性结果。", '''print({"逾期天数": days_overdue, "建议路径": invoice_route})''',
           "若真实系统已有规则，应直接调用规则。这里固定日期是为了可复现，不表示程序获取了当前业务日期。")
    c.md("""## 2. 复刻完整客服分流

### 原理与理论根基

沿用原文的 billing、orders、account 三类和七个问题：主题、索要凭据、发件身份不匹配、意外奖励、退款请求、开放订单引用、不满程度。
垃圾信息风险由三个 Noul 在代码中加权得到；它是应用分数，不是已校准的垃圾概率。
只有当前路径用得上的答案才参与后续处理，例如 billing 使用退款信号，orders 使用订单引用信号。
""" + "\n\n" + sources("concepts/how-to-build-with-system-one"))
    c.step("### 第一步：准备客户资料\n\n订单状态是系统枚举；模型只收到仍未送达的订单。",
           '''CUSTOMER = {
    "plan": "团队版",
    "orders": [
        {"id": "A-104", "status": "processing", "description": "办公用品订单"},
        {"id": "A-090", "status": "delivered", "description": "已送达的历史订单"},
    ],
}
STANDARD_SENDER = {"display_name": "客户王小明", "email": "xiaoming@customer.example"}''')
    c.step("定义正常业务消息。", '''TICKETS = [
    {"id": "closed", "status": "closed", "message": "退款问题已经解决。"},
    {"id": "billing", "status": "open", "message": "我被重复扣款，请退还多扣的金额。"},
    {"id": "orders", "status": "open", "message": "请问我的订单 A-104 什么时候发货？"},
    {"id": "account_normal", "status": "open", "message": "请告诉我怎样重置账户密码。"},
    {"id": "account_high", "status": "open", "message": "账号又无法登录！投诉多次没人处理，再不解决我就注销账户！"},
]''')
    c.step("增加原文凭据与意外奖励场景，以及用于寻找复核分支的模糊消息。", '''TICKETS += [
    {"id": "quarantine", "status": "open",
     "sender": {"display_name": "Acme 薪资部门", "email": "rewards@claim-bonus.example"},
     "message": "恭喜您获得意外奖金！请今天回复您的薪资账户密码领取。"},
    {"id": "review_spam", "status": "open",
     "sender": {"display_name": "薪资服务", "email": "notice@service.example"},
     "message": "你可能有一笔奖励待确认，请尽快处理账户验证。"},
    {"id": "review_topic", "status": "open", "message": "那个问题还是没好，行，就按你说的办。"},
]''', "id 是记录标识，不是会发送的标准答案；真实模型可能把模糊消息判得很确定，也可能走其他路径。")
    c.step("用白名单构造相关上下文。", '''def build_ticket_state(ticket, customer):
    return {
        "ticket": {
            "message": ticket["message"],
            "sender": ticket.get("sender", STANDARD_SENDER),
            "links": ticket.get("links", []),
        },
        "customer": {
            "plan": customer["plan"],
            "open_orders": [x for x in customer["orders"] if x["status"] != "delivered"],
        },
        "policy": {"sensitive_credentials": ["密码", "安全验证码", "API 密钥"]},
    }''')
    c.md("### 第二步：原子问题与结构化定义\n\ncriteria 采用相同字段说明涵盖内容和排除项，减少账单、订单和账户主题混淆。模型看的是完整描述。")
    c.step("先定义主题分类。", '''WORKFLOW_QUESTIONS = {
    "topic": Choice(
        instructions={"question": "哪个团队应处理 `ticket.message`？", "focus": "只按主要诉求分类。"},
        criteria={
            "billing": {"what": "扣款、发票、退款或订阅", "not_for": "订单跟踪或登录"},
            "orders": {"what": "订单状态、配送、取消或退货", "not_for": "账单或登录"},
            "account": {"what": "登录、个人资料、权限或账户安全", "not_for": "扣款或配送"},
        },
    ),
}''')
    c.step("加入凭据请求：使用 NoulCriteria 区分索要密码与指导重置密码。", '''WORKFLOW_QUESTIONS["requests_credentials"] = Noul(
    instructions={"question": "消息是否要求披露敏感凭据本身？",
                  "compare": ["`ticket.message`", "`policy.sensitive_credentials`"]},
    criteria=NoulCriteria(
        true={"what": "要求收件人提供列出的敏感凭据", "examples": ["请回复你的密码"]},
        false={"what": "没有要求披露凭据", "examples": ["请使用重置链接修改密码"]},
    ),
)''', "不要把出现‘密码’两个字一律当作索要凭据。这正是狭窄语义判断比关键词规则更值得试验的地方。")
    c.step("加入其他相互独立的 Noul。", '''WORKFLOW_QUESTIONS.update({
    "sender_identity_mismatch": Noul(instructions=(
        "`ticket.sender.display_name` 声称的机构与 `ticket.sender.email` 的域名是否明显冲突？")),
    "unexpected_reward": Noul(instructions=(
        "`ticket.message` 是否宣称收件人获得未申请的意外奖金或奖品？已知退款不算。")),
    "refund_requested": Noul(instructions=(
        "客户在 `ticket.message` 中是否明确要求退款或账户抵扣？仅抱怨扣款不算。")),
    "mentions_open_order": Noul(instructions=(
        "`ticket.message` 是否用编号或可辨认细节提到了 `customer.open_orders` 中的订单？")),
})''')
    c.step("最后加入不满程度量表。", '''WORKFLOW_QUESTIONS["frustration"] = Score(
    instructions="客户在 `ticket.message` 中表达了多大程度的不满？判断情绪，不判断故障严重程度。",
    criteria=["平静且客观", "不满但保持礼貌", "非常愤怒或威胁离开"],
)''', "所有问题看到同一份 state。哪个答案参与决策由后面的代码决定。")
    c.md("### 第三步：在代码中组合\n\n沿用参考示例的权重与阈值以便对照；这些不是本项目验证出的最佳值。真实应用需要独立标签来选择阈值。")
    c.step("先写风险分数组合。", '''def spam_score(response):
    return (
        0.45 * response.nouls["requests_credentials"].noul
        + 0.30 * response.nouls["sender_identity_mismatch"].noul
        + 0.25 * response.nouls["unexpected_reward"].noul
    )''')
    c.step("再写有限且可观察的路由。", '''def decide_route(response):
    topic = response.choices["topic"]
    risk = spam_score(response)
    if 0.4 < risk < 0.6:
        return {"route": "review_spam", "risk": risk}
    if topic.confidence < 0.75:
        return {"route": "review_topic", "risk": risk}
    if risk >= 0.6:
        return {"route": "quarantine", "risk": risk}
    if topic.choice == "billing":
        return {"route": "billing", "refund_requested": response.nouls["refund_requested"].noul >= 0.7}
    if topic.choice == "orders":
        return {"route": "orders", "mentions_open_order": response.nouls["mentions_open_order"].noul >= 0.7}
    frustration = response.scores["frustration"]
    high = frustration.confidence >= 0.7 and frustration.score >= 1.5
    return {"route": "account_high" if high else "account_normal"}''',
           "退款信号只传给账单队列，不能触发真实退款。网络错误会停止实验；本章不把失败请求算成模型低置信度。")
    c.step("已关闭的工单先跳过 API，其余工单构造状态并请求。", '''def triage_ticket(ticket):
    if ticket["status"] == "closed":
        return {"route": "no_action"}, None
    state = build_ticket_state(ticket, CUSTOMER)
    response = ts.call(state, WORKFLOW_QUESTIONS, WORKFLOW_OFFLINE[ticket["id"]], ticket["id"])
    return decide_route(response), response''')
    c.md("## 3. 执行探针并核对覆盖\n\n这里选择可读的消息观察行为，而不是把这八条当作准确率基准。用于修改提示词的样例属于开发数据。")
    c.step("运行八个案例；closed 不调用 API，因此发起七次业务请求。", '''workflow_results = {ticket["id"]: triage_ticket(ticket) for ticket in TICKETS}''')
    c.step("逐条显示路由和模型信号，保留与预想不一致的结果。", '''for case_id, (decision, response) in workflow_results.items():
    print("案例：", case_id, "结果：", decision)
    if response is not None:
        show(response)''',
           "离线模式覆盖所有分支是因为数据被人工设计过。live 运行若缺少复核分支，必须报告未观察到。")
    c.step("计算真实观察到的路径集合。", '''EXPECTED_ROUTES = {
    "no_action", "review_spam", "review_topic", "quarantine",
    "billing", "orders", "account_normal", "account_high",
}
observed_routes = {decision["route"] for decision, _ in workflow_results.values()}
COVERAGE = {
    "expected": sorted(EXPECTED_ROUTES), "observed": sorted(observed_routes),
    "missing": sorted(EXPECTED_ROUTES - observed_routes),
    "source": "live" if all(x["source"] == "live" for x in CALL_LOG) else "offline",
}''')
    c.step("显示覆盖报告。", '''print(json.dumps(COVERAGE, ensure_ascii=False, indent=2))''',
           "缺失路径需要追加有记录的探针或如实保留缺口；调整阈值需说明理由，不能把离线输出混进 live 补齐。")
    c.md("""## 4. 原文其他设计建议的小配方

下面复刻航班退款、嵌套路径、候选记录去重、虚拟卡分类与天气工具轨迹五个示例。
每个只做一次请求。它们帮助理解输入和问题的设计，不展开其他作者负责的完整架构模式。
""")
    c.step("### 4.1 只送相关上下文：航班退款", '''FLIGHT = {
    "ticket_message": "我的航班取消了，可以退款吗？",
    "refund_policy": "取消的航班可申请全额退款。",
}''')
    c.step("问题明确要求按给定政策判断。", '''FLIGHT_QUESTIONS = {
    "policy_supports_refund": Noul(instructions="提供的 refund_policy 是否支持 ticket_message 中请求的退款？"),
}''')
    c.step("调用。", '''flight_response = ts.call(FLIGHT, FLIGHT_QUESTIONS, FLIGHT_OFFLINE, "航班退款政策")''')
    c.step("观察。", '''show(flight_response)''', "给定政策是本例事实；不能凭模型记忆替代最新的公司政策。")
    c.step("### 4.2 嵌套输入：明确引用不同消息与记录", '''NESTED_STATE = {
    "support": {"tickets": [
        {"message": "订单 A-104 被扣了两次款。"},
        {"message": "怎样重置我的密码？"},
    ]},
    "commerce": {"orders": [{"id": "A-104", "charges": [
        {"amount_usd": 49, "status": "captured"},
        {"amount_usd": 49, "status": "captured"},
    ]}]},
    "account": {"security": {"password_reset": "向已登记邮箱发送密码重置链接。"}},
}''')
    c.step("用反引号路径消除引用歧义。", '''NESTED_QUESTIONS = {
    "duplicate_charge": Noul(instructions=(
        "`support.tickets[0].message` 与 `commerce.orders[0].charges` 是否表明重复扣款？")),
    "password_reset_supported": Noul(instructions=(
        "`account.security.password_reset` 能否解决 `support.tickets[1].message` 中的请求？")),
}''')
    c.step("调用。", '''nested_response = ts.call(NESTED_STATE, NESTED_QUESTIONS, NESTED_OFFLINE, "嵌套状态路径")''')
    c.step("观察。", '''show(nested_response)''', "反引号路径是给模型的文字指引，不是客户端执行的数据库查询。")
    c.step("### 4.3 把代码中的候选记录放进 instructions", '''RESUME = {"resume": {
    "name": "约翰·史密斯", "location": "加利福尼亚州奥克兰",
    "summary": "有八年 Python 和 Go 经验的后端工程师",
    "experience": [
        {"employer": "Google", "title": "高级后端工程师", "years": "2021-2025"},
        {"employer": "Microsoft", "title": "软件工程师", "years": "2017-2021"},
    ],
}}''')
    c.step("候选记录独立具名，不需要拼接长提示词。", '''RECORD_QUESTIONS = {
    "same_as_record_18": Noul(instructions={
        "potential_duplicate": {"name": "约翰·史密斯", "location": "加州奥克兰", "last_employer": "Google"},
        "question": "简历和 potential_duplicate 是否很可能描述同一个人？",
    }),
}''')
    c.step("调用。", '''record_response = ts.call(RESUME, RECORD_QUESTIONS, RECORD_OFFLINE, "候选记录比较")''')
    c.step("观察。", '''show(record_response)''', "返回的是匹配信号，不能单凭同名自动合并真实人员档案。")
    c.step("### 4.4 对比式 Choice criteria：虚拟卡的申请与限制", '''CARD_MESSAGE = "我每天最多能创建多少张一次性虚拟卡？"''')
    c.step("每个选项使用一致字段说明涵盖与排除范围。", '''CARD_QUESTIONS = {
    "card_help_topic": Choice(
        instructions={"question": "用户询问哪种一次性虚拟卡主题？", "focus": "按用户想获得的信息分类。"},
        criteria={
            "get_disposable_virtual_card": {
                "what": "用途、资格或开通方式", "not_for": "数量、交易或商户限制",
                "examples": ["怎样申请一次性虚拟卡？", "一次性卡有什么用途？"],
            },
            "disposable_card_limits": {
                "what": "数量、交易或商户限制", "not_for": "用途、资格或开通方式",
                "examples": ["每天可以创建多少张？", "哪些商户可以使用？"],
            },
        },
    ),
}''')
    c.step("调用。", '''card_response = ts.call(CARD_MESSAGE, CARD_QUESTIONS, CARD_OFFLINE, "虚拟卡主题")''')
    c.step("观察。", '''show(card_response)''', "标签应定位到数量限制；这是待验证预期，不是对任何一次请求的强制断言。")
    c.md("### 4.5 分解工具调用轨迹\n\n复刻原文的西雅图天气查询。请求要华氏度，轨迹却使用摄氏度。这里只检查提供的轨迹，没有调用真实天气工具。")
    c.step("准备用户请求与工具定义。", '''TRACE_STATE = {
    "request": {"text": "请查西雅图 2026 年 9 月 3 日的天气，使用华氏度。",
                "location": "西雅图", "date": "2026-09-03", "unit": "fahrenheit"},
    "available_tools": {
        "geocode_city": {"description": "把城市解析为经纬度", "parameters": {"city": "string"}},
        "get_weather": {"description": "查询指定日期和坐标的天气", "parameters": {
            "latitude": "number", "longitude": "number", "date": "YYYY-MM-DD",
            "unit": ["fahrenheit", "celsius"],
        }},
    },
}''')
    c.step("加入已记录的调用轨迹。", '''TRACE_STATE["trace"] = {
    "tool_calls": [
        {"id": "call_1", "name": "geocode_city", "arguments": {"city": "西雅图"}},
        {"id": "call_2", "name": "get_weather", "arguments": {
            "latitude": 47.6062, "longitude": -122.3321,
            "date": "2026-09-03", "unit": "celsius",
        }},
    ],
    "tool_results": [{"tool_call_id": "call_1", "output": {"latitude": 47.6062, "longitude": -122.3321}}],
}''')
    c.step("九个独立命题定位各类错误。", '''TRACE_PROMPTS = {
    "geocode_tool_is_relevant": "第一个工具是否适合解析 request.location 的地理坐标？",
    "geocode_location_matches": "第一个调用的城市是否与 request.location 匹配？",
    "geocode_arguments_match_schema": "第一个调用参数是否符合 geocode_city 参数定义？",
    "geocode_result_matches_call": "tool_results[0].tool_call_id 是否与第一个调用的 id 匹配？",
    "weather_tool_is_relevant": "第二个工具是否适合回答 request.text 的天气查询？",
    "weather_arguments_match_schema": "第二个调用参数是否符合 get_weather 参数定义？",
    "weather_uses_geocoded_coordinates": "第二个调用坐标是否与第一个工具结果匹配？",
    "weather_date_matches": "第二个调用日期是否与 request.date 匹配？",
    "weather_unit_matches": "第二个调用单位是否与 request.unit 匹配？",
}
TRACE_QUESTIONS = {key: Noul(instructions=value) for key, value in TRACE_PROMPTS.items()}''',
           "精确的日期、枚举和 schema 校验可以直接用代码。这里保留原文的原子判断演示，帮助定位宽泛‘轨迹正确吗’背后的因素。")
    c.step("调用。", '''trace_response = ts.call(TRACE_STATE, TRACE_QUESTIONS, TRACE_OFFLINE, "工具轨迹九问")''')
    c.step("观察各项，再用确定性规则确认单位。", '''show(trace_response)''', "预期单位一致性的概率低。如果模型漏检，记录漏检；不让模型覆盖已知的确定性事实。")
    c.step("补上可以精确执行的检查。", '''unit_matches = TRACE_STATE["trace"]["tool_calls"][1]["arguments"]["unit"] == TRACE_STATE["request"]["unit"]
print({"代码检查单位一致": unit_matches})
assert unit_matches is False''', "这是确定性数据中的已知错误，因此可以断言。业务验收仍要分别评价其他语义检查。")
    c.finish("| 设计动作 | 本章实现 |\n|---|---|\n| 保留代码规则 | 逾期、closed、单位比较 |\n| 狭窄语义判断 | 七问分流、九问轨迹 |\n| 结构化定义 | 候选记录、虚拟卡 criteria |\n| 覆盖核对 | 自动列出 observed / missing |",
             "查看 COVERAGE：哪些路径实际没有命中？为一条缺失路径提出新措辞，先写假设、再运行并记录。另想一个测试集应该如何独立于这些探针。",
             "保留所有尝试及真实返回，不只保留命中的样例。调过问题或阈值后，用另一批未参与调整的标注工单评估覆盖率与误分；不得强改 API 数值填补路径。",
             "下一章：[应用场景地图](use_case_map_experiments.ipynb)。更完整的扇出、门控与组合评分见团队其他章节。")
    return c.save()


if __name__ == "__main__":
    print(build())
