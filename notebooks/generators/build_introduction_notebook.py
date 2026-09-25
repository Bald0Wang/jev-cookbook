"""生成简介章：模型定位、完整理论速览、创业路演的原子评分。"""
from notebook_support import Chapter, sources


def build():
    c = Chapter("introduction", "TypeSafe 简介实验（Introduction Lab）", "introduction",
                "区分 TypeSafe、Jev 与 System One，并将多个原子分数组合成可检查的结果。",
                "| 1 | 理论速览：请求、原语、概率、控制流 |\n| 2 | 复刻创业路演的三个独立维度 |")
    c.prepare()
    c.code('''PITCH_OFFLINE = {
    "market_size": fake_score({0: 0.1, 1: 0.3, 2: 0.6},
        ["需求范围有限", "需求有一定规模", "广泛且明确的需求"], 0.71),
    "technical_feasibility": fake_score({0: 0.05, 1: 0.15, 2: 0.8},
        ["关键能力尚不可行", "有部分实现证据", "主要能力已可运行"], 0.83),
    "differentiation": fake_score({0: 0.4, 1: 0.5, 2: 0.1},
        ["与已有方案接近", "局部差异", "有明确且难替代的差异"], 0.57),
}''')
    c.md("""## 1. 📖 理论速览

TypeSafe 是提供 API 与 SDK 的平台；Jev 是其模型；System One 是文档给这类聚焦判断模型的名称。
请求送入 `state + questions`，返回类型化答案；Python 根据答案执行 `if`、排序或路由。
它适合处理“归哪一类”“符合条件吗”“量表几分”，不负责生成长回复、代码或思维过程。

“一秒判断”是设计问题时的尺度：给一位了解上下文的人，能否迅速判断一个明确属性？
这不是本教程对 API 时延的承诺。复杂任务应拆解，已有确定性规则继续由代码执行。
""")
    c.md("""### 状态、问题和答案的关系

`state` 是待判断材料，可用字符串、对象或文本数组；本系列聚焦文本，不直接传图像、音频或视频。
`instructions` 写完整判断任务；`criteria` 描述可选答案；问题 ID 供代码取回答案。

同一次请求的所有问题看到同一个 state，并独立评估。一个问题不能引用同请求另一个问题尚未返回的答案。
若确实有依赖，先在代码中取回结果，再决定是否构造下一次请求。

问题 ID 在 HTTP 请求中用于映射，但不会作为语义提示发送给模型；例如 `refund_requested` 这个名字不能代替完整 instructions。
此规则不表示 state 中的订单号也会被隐藏。

| 原语 | 适合的判断 | 主要返回值 |
|---|---|---|
| Choice | 从定义好的选项中选一项 | choice、probabilities、confidence |
| Score | 按有序等级评价一个属性 | score、legend、probabilities、confidence |
| Noul | 一个明确命题是否成立 | noul，范围 0–1；没有独立 confidence |
""" + "\n\n" + sources("concepts/state") + " · " + sources("primitives"))
    c.md("""### 概率和 confidence 怎样读

Score 是等级的概率加权期望，所以可以有小数：`0×0 + 1×0.57 + 2×0.43 = 1.43`。
Choice 的低 confidence 往往提示选项之间难以区分；Score 的不确定性还与概率落在相邻还是相距较远的等级有关。
confidence 是分布信息的压缩摘要，不能统一当成最大类别概率。

校准描述一组预测中概率与实际发生频率的关系。模型给某件事 0.8 的概率，不保证这件事一定发生；
高 confidence 的个例也可能错。“我不知道”或转人工是有用的业务出口。
对中文任务要在自己的样本上验证，不承诺中文与英语效果相同。
""" + "\n\n" + sources("confidence") + " · " + sources("models"))
    c.md("""### 谁决定下一步

| 架构 | 判断与控制流怎样分工 | 适用提醒 |
|---|---|---|
| 传统软件 | 规则与分支都由代码定义 | 可计算的条件直接写规则 |
| LLM 智能体 | 模型参与选择下一步动作 | 需要适当的工具约束与监督 |
| AI 驱动的软件 | 代码定流程，模型回答狭窄问题 | 本教程采用这种结构 |

这是参考文档的架构划分，实际系统可以混合使用。拥有类型化输出，不代表已经验证业务正确性。
""" + "\n\n" + sources("concepts/how-to-build-with-system-one"))
    c.md("""## 2. 配方：把创业路演拆成三个维度

原理：市场、技术和差异化分别判断，代码决定权重。对应简介中的创业路演示例，以下路演正文为中文教学补全。

### 📖 理论根基

“给路演一个总分”隐藏了多个偏好。拆开后，读者可以查看哪个因素拉低分数，也可以在不重新请求模型的情况下调整权重。
本例不构成投资判断；只是展示可组合的有序量表。
""")
    c.step("### 第一步：准备材料\n\n把已有事实写进 state，不把期望答案混进去。",
           '''PITCH = {
    "product": "为小型连锁门店提供库存提醒的软件",
    "market": "访谈了二十家门店，其中十二家报告缺货或积压问题；尚无更大样本",
    "technology": "已有能连接两种收银系统的原型，并在两家门店试用",
    "competition": "市场已有同类软件，目前主要差别是部署较方便",
}''')
    c.step("### 第二步：定义独立量表\n\n每个 Score 只判断一个维度，三个量表都使用 0–2，便于演示归一化。",
           '''PITCH_QUESTIONS = {
    "market_size": Score(instructions="仅据 market 中的证据，评价需求范围。",
        criteria=["需求范围有限", "需求有一定规模", "广泛且明确的需求"]),
    "technical_feasibility": Score(instructions="仅据 technology，评价当前技术可行性。",
        criteria=["关键能力尚不可行", "有部分实现证据", "主要能力已可运行"]),
    "differentiation": Score(instructions="仅据 competition，评价与现有方案的差异。",
        criteria=["与已有方案接近", "局部差异", "有明确且难替代的差异"]),
}''', "把问题写在 instructions 中。用 question ID 取结果，不靠名称暗示评判标准。")
    c.step("### 第三步：一次请求三个判断", '''pitch_response = ts.call(PITCH, PITCH_QUESTIONS, PITCH_OFFLINE, "创业路演三维评分")''')
    c.step("### 第四步：先看分布，再看总分", '''show(pitch_response)''',
           "真实分数可能与人工预览不同。阅读每个分布，检查它是否支持你对该维度的解读。")
    c.step("### 第五步：代码决定权重\n\n同一批模型输出，比较两套教学权重；权重总和为 1，Score 先除以最高档 2。",
           '''WEIGHT_SETS = {
    "偏重需求": {"market_size": 0.5, "technical_feasibility": 0.3, "differentiation": 0.2},
    "偏重技术": {"market_size": 0.2, "technical_feasibility": 0.6, "differentiation": 0.2},
}
combined = {
    name: sum(weights[key] * pitch_response.scores[key].score / 2 for key in weights)
    for name, weights in WEIGHT_SETS.items()
}''')
    c.step("显示组合结果。它是应用自行定义的指标，不是模型返回的成功概率。",
           '''print(json.dumps(combined, ensure_ascii=False, indent=2))''',
           "权重变化不保证排序反转。先记录实际变化，再解释变化来源；不要为得到漂亮结论篡改返回值。")
    c.finish("| 学到的接口 | 使用方式 |\n|---|---|\n| state | 提供事实 |\n| questions | 定义原子判断 |\n| typed answers | 交给代码检查和组合 |",
             "把‘文章质量好不好’拆成三个互不依赖的问题，并注明哪些标准可以由代码直接检查。",
             "可以分别评价是否回应主题、论据是否支持结论、语言是否清楚；字数与链接是否为空可以先由代码检查。",
             "下一章：[快速开始](quickstart_experiments.ipynb)。详细原语与架构模式由对应作者的章节继续展开。")
    return c.save()


if __name__ == "__main__":
    print(build())
