# 原语（问题）

> TypeSafe 的三种问题类型（Choice、Score、Noul）、它们返回的类型化答案、如何在它们之间进行选择，以及如何一次提出多个问题。

export function TypesafeExample({example, display, title}) {
  const keyStrUriSafe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-$";
  function compressToEncodedURIComponent(input) {
    if (input == null) return "";
    return _compress(input, 6, function (a) {
      return keyStrUriSafe.charAt(a);
    });
  }
  function _compress(uncompressed, bitsPerChar, getCharFromInt) {
    if (uncompressed == null) return "";
    var i, value, context_dictionary = {}, context_dictionaryToCreate = {}, context_c = "", context_wc = "", context_w = "", context_enlargeIn = 2, context_dictSize = 3, context_numBits = 2, context_data = [], context_data_val = 0, context_data_position = 0, ii;
    for (ii = 0; ii < uncompressed.length; ii += 1) {
      context_c = uncompressed.charAt(ii);
      if (!Object.prototype.hasOwnProperty.call(context_dictionary, context_c)) {
        context_dictionary[context_c] = context_dictSize++;
        context_dictionaryToCreate[context_c] = true;
      }
      context_wc = context_w + context_c;
      if (Object.prototype.hasOwnProperty.call(context_dictionary, context_wc)) {
        context_w = context_wc;
      } else {
        if (Object.prototype.hasOwnProperty.call(context_dictionaryToCreate, context_w)) {
          if (context_w.charCodeAt(0) < 256) {
            for (i = 0; i < context_numBits; i++) {
              context_data_val = context_data_val << 1;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else {
                context_data_position++;
              }
            }
            value = context_w.charCodeAt(0);
            for (i = 0; i < 8; i++) {
              context_data_val = context_data_val << 1 | value & 1;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else {
                context_data_position++;
              }
              value = value >> 1;
            }
          } else {
            value = 1;
            for (i = 0; i < context_numBits; i++) {
              context_data_val = context_data_val << 1 | value;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else {
                context_data_position++;
              }
              value = 0;
            }
            value = context_w.charCodeAt(0);
            for (i = 0; i < 16; i++) {
              context_data_val = context_data_val << 1 | value & 1;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else {
                context_data_position++;
              }
              value = value >> 1;
            }
          }
          context_enlargeIn--;
          if (context_enlargeIn == 0) {
            context_enlargeIn = Math.pow(2, context_numBits);
            context_numBits++;
          }
          delete context_dictionaryToCreate[context_w];
        } else {
          value = context_dictionary[context_w];
          for (i = 0; i < context_numBits; i++) {
            context_data_val = context_data_val << 1 | value & 1;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
            value = value >> 1;
          }
        }
        context_enlargeIn--;
        if (context_enlargeIn == 0) {
          context_enlargeIn = Math.pow(2, context_numBits);
          context_numBits++;
        }
        context_dictionary[context_wc] = context_dictSize++;
        context_w = String(context_c);
      }
    }
    if (context_w !== "") {
      if (Object.prototype.hasOwnProperty.call(context_dictionaryToCreate, context_w)) {
        if (context_w.charCodeAt(0) < 256) {
          for (i = 0; i < context_numBits; i++) {
            context_data_val = context_data_val << 1;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
          }
          value = context_w.charCodeAt(0);
          for (i = 0; i < 8; i++) {
            context_data_val = context_data_val << 1 | value & 1;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
            value = value >> 1;
          }
        } else {
          value = 1;
          for (i = 0; i < context_numBits; i++) {
            context_data_val = context_data_val << 1 | value;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
            value = 0;
          }
          value = context_w.charCodeAt(0);
          for (i = 0; i < 16; i++) {
            context_data_val = context_data_val << 1 | value & 1;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
            value = value >> 1;
          }
        }
        context_enlargeIn--;
        if (context_enlargeIn == 0) {
          context_enlargeIn = Math.pow(2, context_numBits);
          context_numBits++;
        }
        delete context_dictionaryToCreate[context_w];
      } else {
        value = context_dictionary[context_w];
        for (i = 0; i < context_numBits; i++) {
          context_data_val = context_data_val << 1 | value & 1;
          if (context_data_position == bitsPerChar - 1) {
            context_data_position = 0;
            context_data.push(getCharFromInt(context_data_val));
            context_data_val = 0;
          } else {
            context_data_position++;
          }
          value = value >> 1;
        }
      }
      context_enlargeIn--;
      if (context_enlargeIn == 0) {
        context_enlargeIn = Math.pow(2, context_numBits);
        context_numBits++;
      }
    }
    value = 2;
    for (i = 0; i < context_numBits; i++) {
      context_data_val = context_data_val << 1 | value & 1;
      if (context_data_position == bitsPerChar - 1) {
        context_data_position = 0;
        context_data.push(getCharFromInt(context_data_val));
        context_data_val = 0;
      } else {
        context_data_position++;
      }
      value = value >> 1;
    }
    while (true) {
      context_data_val = context_data_val << 1;
      if (context_data_position == bitsPerChar - 1) {
        context_data.push(getCharFromInt(context_data_val));
        break;
      } else context_data_position++;
    }
    return context_data.join("");
  }
  function buildHref(ex) {
    const documentText = ex.state === undefined ? "" : typeof ex.state === "string" ? ex.state : JSON.stringify(ex.state, null, 2);
    return "https://console.typesafe.ai/decode#share/" + compressToEncodedURIComponent(JSON.stringify({
      apiVersion: "v1",
      documentText,
      promptsText: JSON.stringify(ex.questions, null, 2),
      selectedModels: ex.selectedModels
    }));
  }
  const displayedExample = display === "questions" ? example.questions : example.state === undefined ? {
    questions: example.questions
  } : {
    state: example.state,
    questions: example.questions
  };
  const code = JSON.stringify(displayedExample, null, 2);
  const href = buildHref(example);
  return <div style={{
    margin: "1.25rem 0"
  }}>
      <CodeBlock language="json" filename={title ?? "request"}>
        {code}
      </CodeBlock>
      <div className="pb-8">
        <a href={href} target="_blank" rel="noreferrer" className="text-primary">
          Try it in the Playground →
        </a>
      </div>
    </div>;
}

TypeSafe 的原语是你在代码中组合的小型、类型化构建块。它们成对出现：一个问题定义了 [System One 模型](/concepts/system-one)要对某个[状态](/concepts/state)做出的一项判断，而它的答案则是返回的那个类型化值。你在代码中组合这些答案来做出决策。共有三种问题类型，每种返回不同形状的答案。

| 类型                         | 它回答什么              | 返回                                             |
| ---------------------------- | ----------------------- | ------------------------------------------------ |
| [Choice](/primitives/choice) | 这些选项中的哪一个？    | `choice`, `probabilities`, `confidence`          |
| [Score](/primitives/score)   | 哪个级别？              | `score`, `legend`, `probabilities`, `confidence` |
| [Noul](/primitives/noul)     | 这是否为真？            | `noul`（0 到 1）                                 |

你可以只问一个问题，也可以一次发送多个。请求中的每个问题都看到相同的状态，被独立评估，并以你选择的 ID 返回一个类型化答案。

## 每个问题只要求一个快速判断

System One 模型是为快速、聚焦的判断而构建的。请只要求那些懂行的人在拿到正确上下文后一秒钟内就能做出的判断。"这条消息是否传达了紧迫感？"是一个好问题。"分析这条消息并确定最佳行动方案"则不是。后者需要缓慢的推理，而这正是把任务拆分成小问题、再在代码中组合答案的信号。

如果你想要的判断取决于多个独立因素，就分别就每个因素提问，并用你自己的逻辑组合答案。与其问"给这个创业路演打分"，不如分别询问市场规模、技术可行性和差异化程度，然后在代码中按其相对重要性加权。当优先级变化时，改变权重的数值，而不是重写提示词。[一次提出多个问题](#ask-multiple-questions-together)展示了具体做法。

## 定义一个问题

每个问题都有一个 ID、一个 `type` 和 `instructions`。Choice 和 Score 问题还接受 `criteria`，它为 Choice 问题定义选项，或为 Score 定义级别。Noul 问题接受 `criteria` 作为对"是"与"否"含义的可选澄清。

* ID。你自己选定的键，例如 `refund_requested`。它在响应中标识该答案。
* `type`。`choice`、`score` 或 `noul` 之一。
* `instructions`。你要就状态提出的问题。这是放置你的评估逻辑的地方。把它写成清晰、具体的问题，或写成供模型判断的陈述。对大多数问题来说，一个字符串就足够了。它也可以是对象或数组，这样可以把问题放在一个字段里、把它引用的数据放在其他字段里；参见[在问题中使用结构](/concepts/how-to-build-with-system-one#use-structure-in-the-questions)。
* `criteria`。可能的答案：Choice 问题是一个选项映射，Score 是一个有序的级别列表，Noul 是对"是"与"否"的可选描述。每种问题类型的页面会介绍其结构。

下面这个问题询问客户是否请求了退款：

```python theme={null}
from typesafe_sdk import Noul

questions = {
    "refund_requested": Noul(
        instructions="Does the customer request a refund?",
    ),
}
```

<Tip>
  问题 ID 是给你代码用的。它们不会被发送给模型。即使 ID 看起来不言自明，也要在 `instructions` 中写出完整的问题。
</Tip>

## 选择问题类型

选择与所需答案形状匹配的类型。

* **Choice** 适用于答案是已知选项集合之一、且选项之间没有顺序的情况：把工单路由到某个部门、分类文档类型、检测编程语言。给出完整的选项列表，当列表可能无法覆盖所有输入时，添加一个 `other` 或 `none of the above` 选项。

* **Score** 适用于答案落在一个连续谱上、且你能描述该谱上每个点含义的情况：bug 严重程度、客户沮丧程度、技能水平。级别由你定义，模型返回沿这些级别的位置。

* **Noul** 适用于干净的"是/否"问题，且概率本身就是有用的信号：这条消息是否包含个人身份信息、客户是否在请求退款、简历是否提到了分布式系统。

<Note>
  用 Noul 做"是/否"判断，用 Score 衡量连续谱上的位置。"这位候选人的 Python 是否很强？"需要对"强"有清晰的定义。Noul 值为 0.5 意味着模型给"是"和"否"赋予相等的概率。它并不意味着候选人具有中等技能水平。定义不清晰会使这个概率难以解读。

  如果你想衡量技能水平，请使用带有明确定义级别的 Score，例如无经验、有一定了解、日常使用、深厚专长。如果你需要"是/否"决策，请清晰地定义条件，例如"简历中是否写明候选人在工作中使用过 Python？"
</Note>

如果两种类型看起来都合适，优先选择其答案能被你的代码直接使用的那一种。在 `refund`、`rebook` 和 `information` 之间的 Choice 直接映射到三条代码路径。客户沮丧程度的 Score 映射到一个阈值。Noul 映射到一个 `if`。

## 返回什么

答案本身也是原语。每种问题类型返回一个类型化值，你的代码可以对它进行比较、设置阈值、排序、传入后续逻辑，或放入后续请求的状态中（参见[当一个问题依赖另一个问题时](#when-one-question-depends-on-another)）。

| 类型   | 答案字段                                         | 如何解读                                                                                                                                                             |
| ------ | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Choice | `choice`, `probabilities`, `confidence`          | `choice` 是被选中的选项。`probabilities` 是所有选项上的分布。`confidence` 概括了该分布的尖锐程度。                                                                   |
| Score  | `score`, `legend`, `probabilities`, `confidence` | `score` 是沿你定义的级别的位置，可能落在其中两级之间。`legend` 按编号重复列出级别。`probabilities` 是各级别上的分布。                                                |
| Noul   | `noul`                                           | 答案为"是"的概率。接近 1 表示强烈的"是"，接近 0 表示强烈的"否"，接近 0.5 表示不确定。Noul 没有单独的 `confidence`。                                                 |

这些答案的两个特性使它们可以组合：

* **每个答案都被约束在你提供的选项之内。**模型返回的是你的选项或级别上的概率分布，绝不会超出它们。你的代码永远不必从生成的散文中恢复出一个值。
* **每个答案都是独立的。**一个问题的答案不会成为另一个问题的隐藏上下文。你可以增加或删除问题，而不改变其他问题的结果。

[置信度](/confidence)解释了 `confidence` 如何由 `probabilities` 推导而来，以及如何用它来决定何时自动执行、何时升级给人工。

## 引用具体字段

被评估的内容，即[状态](/concepts/state)，通常是一个包含多个部分的 JSON 对象：一段对话、一条记录、一份政策。当问题只关乎其中某个部分时，在 `instructions` 中用点号加索引的路径（包括反引号）指明它的键。这样模型就知道该判断状态的哪个部分。

以 State 页面中的支持对话为例：

```json theme={null}
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

下面两个问题通过路径指向客户的消息、政策和扣款记录：

```python theme={null}
questions = {
    "refund_requested": {
        "type": "noul",
        "instructions": "Does `ticket.messages[0].text` request a refund?",
    },
    "policy_supports_refund": {
        "type": "noul",
        "instructions": (
            "Does `refund_policy` support the refund requested "
            "in `ticket.messages[0].text`, given `order.charges`?"
        ),
    },
}
```

显式路径明确了结构化状态的哪些部分应为每个判断提供依据。关于如何构造输入，参见[状态](/concepts/state)。

## 一次提出多个问题

把使用相同状态的所有问题放在一个请求中发送。你可以自由混合问题类型。System One 模型并行评估请求中的每个问题。增加问题几乎不会改变响应时间，且只消耗额外问题的 token，而这些非常便宜。问一个你可能不需要的问题几乎是无成本的。

这个请求同时分类一条客户消息、检查紧迫性并对沮丧程度打分：

<TypesafeExample
  example={{
state:
  "Our API integration started returning 500 errors on every request about 20 minutes ago, and we can't process any customer orders until this is fixed.",
questions: {
  department: {
    type: 'choice',
    instructions: 'Which team should handle this',
    criteria: {
      billing: 'Payment or subscription issues',
      technical: 'Bugs or integration problems',
      sales: 'Pricing or account questions',
    },
  },
  is_urgent: {
    type: 'noul',
    instructions: 'The message conveys urgency or time-sensitivity',
  },
  frustration: {
    type: 'score',
    instructions: 'How frustrated the customer appears',
    criteria: [
      'Calm, just stating facts',
      'Frustrated but civil',
      'Very angry, strong language',
    ],
  },
},
}}
/>

我们的[客户端 SDK](/sdk) 提供类型化的问题与答案。在 Python 中，把由 `Choice`、`Noul` 和 `Score` 对象组成的 `questions` 字典传给 `client.system_one(...)`。这个请求只发送一次工单和退款政策，却为每个问题得到一个类型化答案：

```python theme={null}
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

state = {
    "ticket_message": "My flight was cancelled. Can I get a refund?",
    "refund_policy": "Cancelled flights are eligible for a full refund.",
}

with TypeSafeClient() as client:
    response = client.system_one(
        state=state,
        questions={
            "refund_requested": Noul(
                instructions="Does `ticket_message` request a refund?",
            ),
            "request_type": Choice(
                instructions="What is the main request in `ticket_message`?",
                criteria={
                    "refund": "The customer wants money returned.",
                    "rebooking": "The customer wants a replacement flight.",
                    "information": "The customer is asking for information only.",
                },
            ),
            "frustration": Score(
                instructions="How frustrated does the customer appear in `ticket_message`?",
                criteria=[
                    "Calm and neutral.",
                    "Concerned but civil.",
                    "Very angry or using strong language.",
                ],
            ),
        },
    )

print(response.answers["refund_requested"].noul)
print(response.answers["request_type"].choice)
print(response.answers["frustration"].score)
```

关于在你所用语言中的安装与使用，参见[客户端 SDK](/sdk)。

### 提出推测性问题

把你代码可能需要的每个问题都提出来，包括那些答案只对部分输入才有意义的问题，让代码决定使用哪些答案。如果一张工单最终不是缺陷报告，就忽略严重程度答案。我们称之为[推测性扇出](/patterns/fan-out)模式。[并行问题实战指南](/cookbooks/parallel_questions)展示了把 13 个问题合并到一次调用中比 13 次单独调用便宜 11.5 倍、快 9.6 倍，而答案没有任何变化。

<Tip>
  编码智能体比人更容易陷入一次调用只问一个问题的习惯。[TypeSafe 智能体技能](/agent-skill#installation)会指示你的智能体在每次调用中放入多个问题，包括那些只对部分输入才有意义的问题。
</Tip>

### 把复杂判断拆分成多个问题

依赖于多个方面的判断，最好按每个方面拆成一个问题。在你的代码中组合答案，并按相对重要性为每个答案赋予一个权重。权重由你决定。当组合结果与团队会做出的决定不符时，在代码中修改权重并重新运行。增加问题几乎不会改变响应时间，因为它们在同一个请求内并行运行。拆分的代价只是少量额外的问题 token。

例如，工单优先级可以由三个 Score 问题构成：bug 有多严重、客户有多沮丧、报告给工程师提供了多少可用信息。Score 页面在[把复杂判断拆分为多个 Score](/primitives/score#splitting-a-complex-judgment-into-several-scores) 中完整讲解了这一请求以及归一化并加权答案的代码。这种技术称为[复合评分](/patterns/composite-scoring)模式。

### 当一个问题依赖另一个问题时

同一请求中的问题是相互独立的：一个答案不会成为另一个问题的上下文。如果后面的判断依赖前面的答案，就在代码中发起第二个请求。只有当你的代码在拿到第一个答案之前无法构建第二个请求时，这种依赖才是真实的：它需要用该答案来为状态获取更多数据、决定状态的构成，或选择下一个问题的选项。否则，就把问题放在一起问，并在代码中组合它们的答案。

两个请求是例外，而非常规。如果第二个请求的问题本可以针对原始状态提出，就把它们放进第一个请求，让代码忽略不需要的那些。有三个实战指南出于真实原因发起了第二次请求。[技能推荐](/cookbooks/skill_suggestion)在一次请求中对 182 个技能排序，然后获取前三名的全文，并基于更好的证据再次判断。[结构恢复](/cookbooks/autoformat)先询问每个换行是否拆散了一个句子，根据这些答案把行合并成块，再对块进行分类——而这些块在第一个请求得到回答之前并不存在。[层级分类](/cookbooks/hierarchical_classification)用每个 Choice 答案来决定下一个请求提供哪些选项。

关于如何把工作流拆解成聚焦的判断，参见[如何用 TypeSafe 构建](/concepts/how-to-build-with-system-one)。

## 下一步

<Columns cols={3}>
  <Card title="Choice" href="/primitives/choice" icon="list">
    从固定列表中选择一个选项。
  </Card>

  <Card title="Score" href="/primitives/score" icon="gauge">
    沿有序级别对状态评分。
  </Card>

  <Card title="Noul" href="/primitives/noul" icon="circle-check">
    获取一个陈述为真的概率。
  </Card>
</Columns>

要了解这些原语如何组合成系统架构，请前往[模式](/patterns)。
