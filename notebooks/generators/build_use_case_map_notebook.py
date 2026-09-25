"""生成应用地图章：任务卡、候选相关性与引用支撑检查。"""
from notebook_support import Chapter, sources


def build():
    c = Chapter("use_case_map", "TypeSafe 应用场景实验（Use Case Map Lab）", "concepts/use-case-map",
                "按输入、问题、输出、动作、验证定义新任务，并实现候选相关性与引用支撑两个小配方。",
                "| 1 | 应用类别与决策形态 |\n| 2 | 搜索与检索：候选相关性 |\n| 3 | 科研核验：证据是否支持论断 |\n| 4 | 自己的任务卡 |")
    c.prepare()
    c.code('''RELEVANCE_OFFLINE = {
    "candidate_0": fake_score({0: 0.02, 1: 0.03, 2: 0.95},
        ["无关", "相关但不能直接回答", "直接回答查询"], 0.93),
    "candidate_1": fake_score({0: 0.97, 1: 0.02, 2: 0.01},
        ["无关", "相关但不能直接回答", "直接回答查询"], 0.95),
    "candidate_2": fake_score({0: 0.08, 1: 0.85, 2: 0.07},
        ["无关", "相关但不能直接回答", "直接回答查询"], 0.82),
}
EVIDENCE_OFFLINE = {
    "claim_0_supported": _FakeAnswer("noul", noul=0.96),
    "claim_1_supported": _FakeAnswer("noul", noul=0.04),
}''')
    c.md("""## 1. 📖 理论根基：用输入与动作约束想法

用例地图提供头脑风暴方向，不表示模型已在这些行业通过业务验收。
自动化软件、实时应用、大数据 Map Reduce、通用验证与 Harness 工程，是文档列出的五类应用形态。
共同点是把语言理解接入代码；是否满足吞吐、成本、时延和质量要求，仍要测量。

| 决策形态 | 问题与输出 | 后续动作 | 最小验证 |
|---|---|---|---|
| 分类 | Choice 类别 | 分类存储 | 混淆矩阵、other 比例 |
| 检测 | Noul 属性概率 | 标记或复核 | 漏检、误报与阈值 |
| 评分 | Score 有序等级 | 排优先级 | 与人工量表对照 |
| 路由 | 分类与不确定性 | 选择代码路径 | 覆盖率、错误路径 |
| 搜索 | 查询与候选的关系 | 选出匹配候选 | 候选集召回与命中 |
| 检索 | 上下文相关性 | 送入下一阶段 | 证据覆盖、遗漏 |
| 排序 | 相关性分数或比较 | 对候选排序 | 人工排序对照 |
| 核验 | 具体命题是否成立 | 接受、修改、复核 | 错误类型检出情况 |
| ML 特征提取 | 语义属性概率 | 输入下游模型 | 独立标签上的增益 |
| 结构化提取 | 有限候选的字段判断 | 填入业务记录 | 字段准确率、缺失率 |

TypeSafe 的有限答案原语不等同于任意文本抽取器。未知姓名、日期等开放字段通常还需要候选生成或提取流程。
""")
    c.md("""### 从行业回到具体判断

| 行业或场景 | 可以先定义的一项判断 |
|---|---|
| 科学发现 | 段落是否满足综述纳入标准 |
| 模型路由 | 请求属于哪个领域、难度等级 |
| LLM 防护栏 | 输入或工具调用是否违反明确规则 |
| 语义代码检查 | 变更是否符合一条写作或代码规范 |
| 招聘 | 材料是否提供岗位所需经验的证据 |
| 销售线索 | 公司档案是否匹配客户画像 |
| 客户支持 | 主诉属于哪个支持队列 |
| 保险理赔 | 材料是否缺少指定信息 |
| 金融犯罪调查 | 描述中是否存在指定的可疑信号 |
| 法律与合规 | 材料是否包含指定条款 |
| 电商市场 | 商品属于哪个预定义类别 |
| 内容审核 | 是否违反给定社区政策 |
| 广告 | 文案与落地页信息是否一致 |
| 游戏 | 玩家举报属于哪类问题 |
| 风险评估 | 报告中某个风险信号是否存在 |
| 需求预测 | 文本是否表达购买意图 |
| 图与知识图谱 | 给定两条记录是否相互矛盾 |

每项都需要相应上下文和人工标准。下面只实现“搜索与检索”和“科学发现中的引用核验”两个低依赖示例。
""")
    c.md("""## 2. 配方 A：为候选段落打相关性分

### 原理与理论根基

对应原文搜索与检索条目：先有候选集，再评价查询与候选之间的关系。本例不实现全库索引或完整 RAG。
三个问题共享一个 state，每个问题明确引用自己的候选。
""" + "\n\n" + sources("concepts/use-case-map") + " · " + sources("primitives/score"))
    c.step("### 第一步：准备查询与候选", '''SEARCH_STATE = {
    "query": "订单被重复扣款应该怎么处理？",
    "candidates": [
        {"id": "D1", "text": "如同一订单被重复扣款，请提交订单编号与扣款凭证，客服核查后可退还重复部分。"},
        {"id": "D2", "text": "更改登录密码请进入账户设置，选择安全与密码。"},
        {"id": "D3", "text": "账单可在每月结算后下载，页面列出每笔扣款金额。"},
    ],
}''')
    c.step("### 第二步：明确‘相关’的等级", '''RELEVANCE_LEVELS = ["无关", "相关但不能直接回答", "直接回答查询"]
RELEVANCE_QUESTIONS = {
    f"candidate_{i}": Score(
        instructions=f"`candidates[{i}].text` 与 `query` 有多相关？只评价这一个候选。",
        criteria=RELEVANCE_LEVELS,
    )
    for i in range(len(SEARCH_STATE["candidates"]))
}''', "‘提到扣款’与‘回答重复扣款怎么办’的相关程度不同，量表要体现这一区别。")
    c.step("### 第三步：一次请求所有候选判断", '''search_response = ts.call(SEARCH_STATE, RELEVANCE_QUESTIONS, RELEVANCE_OFFLINE, "候选相关性")''')
    c.step("### 第四步：查看原始分数与分布", '''show(search_response)''', "Score 不是概率。归一化后的 Score 也不是‘答案正确概率’。")
    c.step("### 第五步：排序并保留‘没有合适候选’出口", '''ranked = sorted(
    [{"id": item["id"], "score": search_response.scores[f"candidate_{i}"].score,
      "confidence": search_response.scores[f"candidate_{i}"].confidence}
     for i, item in enumerate(SEARCH_STATE["candidates"])],
    key=lambda row: row["score"], reverse=True,
)
selected = [row for row in ranked if row["score"] >= 1.5 and row["confidence"] >= 0.75]''')
    c.step("显示排序与筛选结果。", '''print(json.dumps({"排序": ranked, "送往下一阶段": selected or "无合适候选，继续检索或复核"},
                 ensure_ascii=False, indent=2))''',
           "阈值只是教学值；即使 top-1 排得出来，也可能整个候选集都无关。评估排序前还应检查候选集是否覆盖答案。")
    c.md("""## 3. 配方 B：证据是否支持论断

### 原理与理论根基

对应原文科学发现与通用验证条目。给定证据和候选论断，逐项问证据是否足以支持。
本例使用一项虚构课堂试验，不涉及真实研究结论。没有支持不一定意味着论断本身为假。
""")
    c.step("准备证据与两个论断。", '''EVIDENCE_STATE = {
    "evidence": "课堂小组在同一台电脑上做了十次测试。方法甲的平均耗时为 12 秒，方法乙为 9 秒。未测试其他设备。",
    "claims": [
        "这十次测试中，方法乙的平均耗时比方法甲短。",
        "方法乙在所有设备和所有任务上都优于方法甲。",
    ],
}''')
    c.step("问题要求只按所给证据判断，避免外部常识补造支撑。", '''EVIDENCE_QUESTIONS = {
    f"claim_{i}_supported": Noul(instructions=(
        f"仅根据 `evidence`，它是否充分支持 `claims[{i}]` 的完整论断？不要用外部知识补充证据。"))
    for i in range(len(EVIDENCE_STATE["claims"]))
}''', "第二条增加了‘所有设备和所有任务’的范围，重点观察模型是否注意到证据的适用范围。")
    c.step("调用。", '''evidence_response = ts.call(EVIDENCE_STATE, EVIDENCE_QUESTIONS, EVIDENCE_OFFLINE, "引用支撑")''')
    c.step("逐条查看概率。", '''for i, claim in enumerate(EVIDENCE_STATE["claims"]):
    print({"论断": claim, "给定证据支持的概率": evidence_response.nouls[f"claim_{i}_supported"].noul})''',
           "两条合成输入只能检查示例行为。真实引用核验还需包含部分支持、矛盾、遗漏和不同表述方式的独立样本。")
    c.md("""## 4. 用任务卡定义你的下一个配方

| 字段 | 本章相关性配方 | 你需要填写的内容 |
|---|---|---|
| 输入 | 查询与候选段落 | 只列判断所需事实 |
| 问题 | 候选是否直接回答查询 | 一个明确属性 |
| 输出 | 0–2 的 Score 与分布 | 答案空间与量表 |
| 动作 | 排序、筛选或继续检索 | 由代码实施的动作 |
| 验证 | 人工相关性、排序与遗漏 | 样本、标签、错误成本 |
| 不确定出口 | 无合适候选 | 复核、补充信息或停止 |

原先的学习社区工单与 FAQ 教程保留在项目 `docs/` 和 `examples/`，作为迁移练习；它们的人工响应不计入本系列真实结果。
""")
    c.finish("| 小配方 | 模型做什么 | 程序做什么 |\n|---|---|---|\n| 相关性 | 按量表判断 | 排序、筛选与空结果处理 |\n| 引用支撑 | 判断论断与证据关系 | 记录、复核或请求修改 |",
             "从行业表选一个任务，填写任务卡；给出一个明确正例、一个明确反例和一个材料不足的例子。说明哪种错误代价更高。",
             "例如课程答疑：输入问题与 FAQ 候选，问题为候选能否直接回答，输出相关性 Score，动作是显示候选或交助教；漏掉合适答案与展示错误答案要分别统计。材料不足时允许空结果。",
             "延伸阅读：" + sources("cookbooks/citation_check") + " · " + sources("cookbooks/rerank_typesafe"))
    return c.save()


if __name__ == "__main__":
    print(build())
