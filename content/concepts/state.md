# 状态

> 什么是状态、如何构造它，以及如何为 System One 模型提供所需的上下文。

**状态**是你要求 System One 模型评估的内容。它可以是一条客服消息、一段文字，或你的应用当前的状况。你通过 API 请求的 `state` 字段传入它，同时附上你想要得到答案的问题。

每个请求针对一个或多个问题评估一个状态。所有问题看到的都是同一个状态，并且各自独立评估。你可以在一个请求中混用 [Choice](/primitives/choice)、[Score](/primitives/score) 和 [Noul](/primitives/noul) 问题。

## 状态可以是简单字符串，也可以是结构化 JSON 值

最简单的状态是纯字符串：

```python theme={null}
state = "My card was charged twice."
```

状态也可以是一个 JSON 对象或数组，包含相关上下文、示例以及其他有助于模型回答相关问题的信息。把状态想象成你在请专家小组做判断之前呈给他们的材料。在 Python 中，将相应的字符串、字典或列表直接传给 `client.system_one(state=...)`。

| 格式   | 适用情形                                             | 示例                                                                    |
| ------ | --------------------------------------------------- | ----------------------------------------------------------------------- |
| 字符串 | 一条消息、一篇文章或一个段落                        | `"My card was charged twice."`                                          |
| 对象   | 具名字段、相关记录或应用状态                        | `{"message": "My card was charged twice.", "order_id": "A-104"}`        |
| 数组   | 一系列消息或记录                                    | `["Hi", "My customer number is TS1337.", "My card was charged twice."]` |

大多数请求应使用对象，这样状态的每个部分都有一个描述性名称，各部分之间的关系也保持清晰。当用例简单、只需要一段文字时，使用字符串即可。

<Note>
  Jev 只接受文本。状态必须是字符串、JSON 对象或文本值数组。图像、音频和视频尚不受支持（暂时）。Jev 的主要训练语言是英语；其他语言（包括中日韩文字）也可以接受，但目前准确率较低——参见[模型](/models#language-support)。
</Note>

```json title="A support conversation as state" theme={null}
{
  "ticket": {
    "subject": "Duplicate charge",
    "messages": [
      {"from": "customer", "text": "I was charged twice for order A-104. Please refund the duplicate."},
      {"from": "support", "text": "We are checking the charges."}
    ]
  },
  "order": {
    "id": "A-104",
    "charges": [
      {"amount_usd": 49, "status": "captured"},
      {"amount_usd": 49, "status": "captured"}
    ]
  },
  "refund_policy": "Duplicate charges are eligible for a refund."
}
```

这个对象是一个状态，尽管它包含一段对话、一个订单和一项政策。当决策需要比较这些部分时，就把相关信息放在一起。

## 将内容与问题分开

状态包含内容和支撑性事实。[问题](/primitives)定义模型应当就这些材料做出哪些判断。例如，把退款请求和政策放在状态中，然后询问客户是否请求了退款，以及政策是否支持退款。

有关 instructions、criteria、问题类型以及针对一个状态提出多个问题的指引，参见[原语（问题）](/primitives)。

请求模式参见 [API 参考](/api)；安装、类型化输入和响应处理参见[客户端 SDK](/sdk)。
