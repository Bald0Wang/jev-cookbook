"""生成快速开始章：Playground、HTTP 与 SDK 的同一个中文场景。"""
from notebook_support import Chapter, sources


def build():
    c = Chapter("quickstart", "02 · TypeSafe 快速开始实验（Quickstart Lab）", "introduction/quickstart",
                "把官方 Stripe 连接故障场景从 Playground 迁移到 HTTP 和 Python SDK，并正确读取三种答案。",
                "| 1 | Playground 与最小 Noul |\n| 2 | HTTP 请求体与环境变量 |\n| 3 | Python 混合三个原语 |")
    c.prepare()
    c.code('''URGENCY_OFFLINE = {"urgency": _FakeAnswer("noul", noul=0.96)}
MIXED_OFFLINE = {
    "department": fake_choice({"billing": 0.12, "technical": 0.86, "sales": 0.02}, 0.79),
    "frustration": fake_score({0: 0.08, 1: 0.85, 2: 0.07},
        ["平静地陈述事实", "沮丧但保持礼貌", "非常愤怒或使用强烈措辞"], 0.84),
    "is_urgent": _FakeAnswer("noul", noul=0.96),
}''')
    c.md("""## 📖 理论根基：一次请求里有什么

状态是客户消息；问题描述你需要的判断；模型字段选择处理请求的模型。
同一段消息可以同时被用于分类、评分和是非判断。返回的是对象，无需从聊天文本中提取 JSON。
模型提供判断，程序仍要检查调用失败、输出结构和业务结果。

本章实际执行两次业务请求，再加准备部分的一次连通性请求。下方 cURL 仅作为等价入口展示，
不会由 Notebook 自动执行；若自己运行它，会增加一次请求。
""" + "\n\n" + sources("api") + " · " + sources("sdk/python/usage"))
    c.md("""## 1. 在 Playground 建立直觉

打开 [Playground](https://console.typesafe.ai/playground)，把下一格的中文文本粘贴到 state。
添加 Noul，问题写“这条消息是否表达紧迫性或时间压力？”，然后执行并观察概率。
接着添加部门 Choice 和不满程度 Score，与第 3 节保持同一套定义。

这是手动体验路线；本教程不会替你登录控制台或安装文档内提及的 agent 技能。
""")
    c.step("### 第一步：官方示例的中文版本", '''TICKET = "你好，我尝试连接 Stripe 账户已经三天了，集成一直失败，正在损失销售额。请尽快帮忙。"''')
    c.step("### 第二步：只提一个明确问题", '''URGENCY_QUESTIONS = {
    "urgency": Noul(instructions="这条消息是否表达紧迫性或时间压力？"),
}''', "Noul 给出的数值是命题成立的概率，不要使用 bool(概率) 来代替阈值判断。")
    c.step("### 第三步：发起请求", '''urgency_response = ts.call(TICKET, URGENCY_QUESTIONS, URGENCY_OFFLINE, "Stripe 紧迫性")''')
    c.step("### 第四步：读取结果", '''show(urgency_response)''',
           "官方页面中的示例数字不是你这次调用的标准答案。记录实际数值，比较含义与字段即可。")
    c.md("""## 2. 看懂等价 HTTP 请求

请求为 `POST https://api.typesafe.ai/v1/systemone`。认证头读取环境变量，不能把真实值粘贴到教程或输出。
下面先构造不含密钥的请求体。SDK 最终也使用这种请求模型。
""")
    c.step("构造最小请求体；这里用 Python 字典演示接口结构。", '''HTTP_BODY = {
    "model": MODEL,
    "state": TICKET,
    "questions": {
        "urgency": {"type": "noul", "instructions": "这条消息是否表达紧迫性或时间压力？"},
    },
}''')
    c.step("显示可以发送的 JSON。认证头不进入输出。", '''print(json.dumps(HTTP_BODY, ensure_ascii=False, indent=2))''',
           "把该 JSON 保存到 request.json 后，可使用下一段终端命令；它与上面的 SDK 请求是两个可选入口。")
    c.md('''```bash
curl --fail-with-body --max-time 30 https://api.typesafe.ai/v1/systemone \\
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \\
  -H "Content-Type: application/json" \\
  --data-binary @request.json
```

`TYPESAFE_API_KEY` 应由你的本地环境管理方式设置。不要把带真实密钥的命令保存到公开文件中。
如果只创建 `.env` 文件而没有加载到启动 Jupyter 的进程，这里仍然读不到变量。''')
    c.md("""## 3. 一次请求混用三个原语

原理：工单部门、不满程度与紧迫性都能直接从同一条消息独立判断。
三个问题不需要知道彼此的结果。criteria 中的 key 英文、解释中文。
""")
    c.step("定义 Choice 的标签边界。", '''DEPARTMENTS = {
    "billing": "付款、账单或订阅问题",
    "technical": "故障或集成问题",
    "sales": "价格或购买账户的咨询",
}
FRUSTRATION_LEVELS = ["平静地陈述事实", "沮丧但保持礼貌", "非常愤怒或使用强烈措辞"]''')
    c.step("定义完整问题。", '''MIXED_QUESTIONS = {
    "department": Choice(instructions="哪个团队应处理这条消息的主要诉求？",
                         criteria=DEPARTMENTS),
    "frustration": Score(instructions="客户在措辞中表达了多大程度的不满？",
                         criteria=FRUSTRATION_LEVELS),
    "is_urgent": Noul(instructions="消息是否表达紧迫性或时间压力？"),
}''', "‘损失销售额’不自动意味着应该路由 sales；分类应看客户正在请求解决什么。")
    c.step("发送三个问题。", '''mixed_response = ts.call(TICKET, MIXED_QUESTIONS, MIXED_OFFLINE, "Stripe 三种原语")''')
    c.step("查看结构化结果。", '''show(mixed_response)''', "先看实际 department，再看其 confidence；不满程度与问题严重程度是不同的量表。")
    c.step("核对 Score 的含义：从概率重新计算期望。", '''frustration = mixed_response.scores["frustration"]
expected_score = sum(int(level) * p for level, p in frustration.probabilities.items())
print({"返回分数": frustration.score, "加权期望": expected_score,
       "绝对差": abs(frustration.score - expected_score)})''',
           "SDK 中等级通常是整数；原始 JSON 的对象键是字符串。使用 int(level) 兼容两种展示。")
    c.md("""### 常见问题

| 现象 | 检查与处理 |
|---|---|
| 找不到 SDK | 确认安装环境与当前内核一致 |
| 缺少密钥 | 配置启动进程的环境变量，重启内核 |
| 401 / 403 | 核对密钥、账户权限；严格 live 停止 |
| 429、连接失败、超时 | 记录错误，核对额度或网络；不要改成假的低 confidence |
| 数值与教程不同 | 记录实际模型与输入，比较语义和字段，不强求逐位相同 |
""")
    c.finish("| 原语 | 本章问题 |\n|---|---|\n| Choice | 处理部门 |\n| Score | 不满程度 |\n| Noul | 是否紧迫 |",
             "把 TICKET 改为一条平静的价格咨询，再重跑业务部分。先写下预期部门和原因，后记录实际结果。",
             "可以使用‘请问团队版每个月多少钱？我想比较几个方案。’预期更接近 sales；这只是待验证假设，不能在真实调用中断言概率固定。",
             "下一章：[场景地图](03_场景地图.ipynb)。")
    return c.save()


if __name__ == "__main__":
    print(build())
