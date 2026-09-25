# Choice

> Choice 是一种 System One 问题类型，用于从一组已定义的选项中选择一个。答案包括所选选项、每个选项的概率以及置信度。

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

当答案是固定选项集合之一时，使用 Choice。例如：由哪个团队处理工单、产品属于哪个类别、一段代码是用哪种语言写的。如果答案是某个光谱上的位置，使用 [Score](/primitives/score)。如果是肯定或否定，使用 [Noul](/primitives/noul)。[选择问题类型](/primitives#choose-a-question-type) 对三者进行了比较。

Choice 的答案是通过 `choice` 返回的所选选项。模型还会在 `probabilities` 中为每个选项返回一个概率，并为所选选项返回一个 `confidence` 值。

示例问题：

```
"What programming language is this code written in"
  → options: python, javascript, typescript, go, rust, other

"What type of meeting is this based on the title and description"
  → options: standup, planning, retrospective, one on one, brainstorm, none of the above

"Which product category does this item belong to"
  → options: electronics, clothing, home garden, food and beverage
```

## 请求结构

发送到 [TypeSafe API](/api) 的 POST 请求体具有特定的结构。顶层有三个字段：`state`，即要评估的内容；`model`；以及 `questions`，一个从你自选的问题 id 到问题对象的映射。每个 Choice 问题包含以下字段：

* `type`：始终为 `"choice"`。
* `instructions`：模型要回答的问题。
* `criteria`：答案选项，以映射的形式给出。每个键是一个选项名称，每个值是对该选项的描述。

下面这个请求中，状态是来自一家在线鞋店的客服工单，问题是由哪个团队来处理它：

<TypesafeExample
  display="request"
  example={{
state: 'My running shoes arrived in the wrong size. Can I swap them for a size 10?',
selectedModels: ['jev-latest'],
questions: {
  department: {
    type: 'choice',
    instructions: 'Which team should handle this?',
    criteria: {
      returns: 'Exchanges, wrong or damaged items',
      shipping: 'Delivery status, delays, lost packages',
      billing: 'Charges, invoices, payment problems',
    },
  },
},
}}
/>

问题 id 由你来定，此处为 `department`。答案以相同的 id 返回。模型永远看不到问题 id。选项名称及其描述都会发送给模型，因此描述要能把各选项彼此区分开。

我们的[客户端 SDK](/sdk) 提供类型化的问题。在 Python 中，同一个问题就是一个 `Choice`：

```python theme={null}
from typesafe_sdk import Choice, TypeSafeClient

with TypeSafeClient() as client:
    response = client.system_one(
        state="My running shoes arrived in the wrong size. Can I swap them for a size 10?",
        questions={
            "department": Choice(
                instructions="Which team should handle this?",
                criteria={
                    "returns": "Exchanges, wrong or damaged items",
                    "shipping": "Delivery status, delays, lost packages",
                    "billing": "Charges, invoices, payment problems",
                },
            ),
        },
    )

    print(response.answers["department"].choice)
```

使用 `system_one` 方法或 `https://api.typesafe.ai/v1/systemone` 端点来调用 System One 模型。`model` 字段选择由哪个模型处理该请求。[如何使用 TypeSafe 进行构建](/concepts/how-to-build-with-system-one) 介绍了在你的代码中应在何处调用它。

使用我们的某个[客户端 SDK](/sdk)，或直接调用 [HTTP API](/api)。如果有编码智能体在为你编写集成代码，请先安装 [TypeSafe agent skill](/agent-skill#installation)，让它了解请求和响应的结构。

<Note>
  `instructions` 和 `criteria` 中的每个条目可以是字符串、对象或数组。先用字符串。当一条描述需要多种指引时使用对象，例如选项涵盖什么、不涵盖什么，以及一些示例。参见下文的[结构化 instructions 与 criteria](#structured-instructions-and-criteria)和 [API 参考](/api#param-instructions-1)。
</Note>

## 响应结构

响应在 `answers` 中为每个问题包含一个条目，使用请求中的 id。以下是对上面示例请求的响应：

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "department": {
      "type": "choice",
      "choice": "returns",
      "confidence": 1.0,
      "probabilities": {
        "shipping": 0.0,
        "returns": 1.0,
        "billing": 0.0
      }
    }
  },
  "usage": {
    "input_tokens": 328,
    "output_tokens": 34
  }
}
```

除 `type` 之外，每个 Choice 答案有三个值：

* `choice`：概率最高的选项。
* `probabilities`：覆盖每个选项的完整概率分布。所有值之和为 1。
* [`confidence`](/confidence)：一个 0 到 1 之间的数值，由 `probabilities` 的分布形态计算得出。平坦的形态——概率分散在多个选项上——意味着低置信度；单个选项上的一个尖峰意味着高置信度。

这张工单很简单，因此全部概率都落在 `returns` 上，置信度为 1.0。一张同时提到尺码不对和退款缺失的工单，会把概率分摊到 `returns` 和 `billing` 之间，置信度也会随之下降。

## 良好实践：每次调用提出多个问题

在单个请求中提出代码可能需要的所有 Choice 问题，而不是每个问题发一个请求。问题会并行评估。增加问题几乎不会改变响应时间，代码也可以忽略不需要的答案。额外的问题仍然消耗 token。[同时提出多个问题](/primitives#ask-multiple-questions-together) 对此有完整说明；下一节将展示在单次调用中提出五个 Choice 问题。

同样的逻辑也适用于单个 Choice 问题内部的选项。一个 Choice 问题最多接受 255 个选项，每增加一个选项会消耗少量 token，因此应把团队、类别或产品的完整列表交给模型，而不是一份入围名单。当列表可能无法覆盖所有输入时，添加一个 `other` 或 `none of the above` 选项，让模型可以表示其他选项都不合适。

要通过深层层级或大型分类体系对文档分类，可以逐级串联 Choice 问题。[层级分类实战指南](/cookbooks/hierarchical_classification) 展示了如何在 Choice 概率上运行束搜索，在每一层保留最优的 `K` 条候选路径，而不是只走一条贪婪路径。

## 一个更复杂的示例

上面的基础示例把工单路由给一个团队。更大的客服系统可能还需要退货原因、配送问题、客户想要什么，以及客户的语气。

下面的请求针对一张比第一张更模糊的工单提出五个 Choice 问题：它涉及三个团队，而且没有说明客户想要什么。

<TypesafeExample
  display="request"
  example={{
state: 'Shoes arrived two weeks late and in the wrong size. Also I see two charges of $120 on my card. What are you going to do about this?',
selectedModels: ['jev-latest'],
questions: {
  department: {
    type: 'choice',
    instructions: 'Which team should handle this?',
    criteria: {
      returns: 'Exchanges, wrong or damaged items',
      shipping: 'Delivery status, delays, lost packages',
      billing: 'Charges, invoices, payment problems',
    },
  },
  return_reason: {
    type: 'choice',
    instructions: 'If the customer wants to return something, why?',
    criteria: {
      wrong_size: "The item doesn't fit",
      wrong_item: 'A different product was delivered',
      damaged: 'The item arrived broken or faulty',
      changed_mind: 'The item is fine, the customer no longer wants it',
      other: 'A return reason that fits none of the above',
    },
  },
  shipping_issue: {
    type: 'choice',
    instructions: 'If this is a shipping problem, which kind is it?',
    criteria: {
      not_delivered: 'The package never arrived',
      delayed: 'The package is late but still on its way',
      wrong_address: 'The package went to the wrong place',
      damaged_in_transit: 'The package arrived damaged',
      other: 'A shipping problem that fits none of the above',
    },
  },
  requested_resolution: {
    type: 'choice',
    instructions: 'What does the customer want to happen?',
    criteria: {
      exchange: 'Swap the item for a different one',
      refund: 'Money back',
      replacement: 'The same item sent again',
      information: 'Just an answer, no action needed',
    },
  },
  tone: {
    type: 'choice',
    instructions: "What is the customer's tone?",
    criteria: {
      calm: null,
      frustrated: null,
      angry: null,
    },
  },
},
}}
/>

这些问题中有两个 Choice 是推测性的：`return_reason` 只有在 `department` 为 `returns` 时才有意义，而 `shipping_issue` 只有在为 `shipping` 时才有意义。`tone` 问题使用 `null` 描述，因为选项名称本身已经足够清晰。

TypeSafe 的响应：

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "department": {
      "type": "choice",
      "choice": "returns",
      "confidence": 0.42,
      "probabilities": {
        "shipping": 0.04,
        "billing": 0.35,
        "returns": 0.61
      }
    },
    "return_reason": {
      "type": "choice",
      "choice": "wrong_size",
      "confidence": 1.0,
      "probabilities": {
        "other": 0.0,
        "wrong_size": 1.0,
        "changed_mind": 0.0,
        "damaged": 0.0,
        "wrong_item": 0.0
      }
    },
    "shipping_issue": {
      "type": "choice",
      "choice": "delayed",
      "confidence": 0.67,
      "probabilities": {
        "wrong_address": 0.0,
        "other": 0.26,
        "not_delivered": 0.0,
        "damaged_in_transit": 0.0,
        "delayed": 0.74
      }
    },
    "requested_resolution": {
      "type": "choice",
      "choice": "refund",
      "confidence": 0.2,
      "probabilities": {
        "replacement": 0.34,
        "refund": 0.4,
        "information": 0.02,
        "exchange": 0.24
      }
    },
    "tone": {
      "type": "choice",
      "choice": "frustrated",
      "confidence": 0.76,
      "probabilities": {
        "frustrated": 0.84,
        "angry": 0.16,
        "calm": 0.0
      }
    }
  },
  "usage": {
    "input_tokens": 589,
    "output_tokens": 212
  }
}
```

每个问题都独立地针对这张工单作答：

* `department` 的答案是 `returns`，概率 0.61，但由于重复扣款，`billing` 也有 0.35。这张工单属于两个团队，0.42 的分散置信度正反映了这一点。
* `return_reason` 是 `wrong_size`，置信度 1.0，这是意料之中，因为工单里明确写了这一点。
* `shipping_issue` 的答案分散在 `delayed` 和 `other` 之间。这是一个推测性问题，而且 `department` 的结果不是 shipping，所以代码可以忽略它，如下面的示例代码片段所示。
* `requested_resolution` 的答案倾向于 `refund`，为 0.40，`replacement` 和 `exchange` 分享了其余大部分概率，置信度为 0.20。重复扣款暗示退钱，尺码不对暗示换货，而客户从未说明自己想要哪一种。
* `tone` 的答案是 `frustrated`，概率 0.84，置信度 0.76。

下面的示例代码读取它需要的答案，忽略其余的，并把低置信度的答案当作“先询问而非行动”的理由：

```python theme={null}
from typesafe_sdk import Choice, TypeSafeClient

TRIAGE_QUESTIONS = {
    "department": Choice(
        instructions="Which team should handle this?",
        criteria={
            "returns": "Exchanges, wrong or damaged items",
            "shipping": "Delivery status, delays, lost packages",
            "billing": "Charges, invoices, payment problems",
        },
    ),
    "return_reason": Choice(
        instructions="If the customer wants to return something, why?",
        criteria={
            "wrong_size": "The item doesn't fit",
            "wrong_item": "A different product was delivered",
            "damaged": "The item arrived broken or faulty",
            "changed_mind": "The item is fine, the customer no longer wants it",
            "other": "A return reason that fits none of the above",
        },
    ),
    "shipping_issue": Choice(
        instructions="If this is a shipping problem, which kind is it?",
        criteria={
            "not_delivered": "The package never arrived",
            "delayed": "The package is late but still on its way",
            "wrong_address": "The package went to the wrong place",
            "damaged_in_transit": "The package arrived damaged",
            "other": "A shipping problem that fits none of the above",
        },
    ),
    "requested_resolution": Choice(
        instructions="What does the customer want to happen?",
        criteria={
            "exchange": "Swap the item for a different one",
            "refund": "Money back",
            "replacement": "The same item sent again",
            "information": "Just an answer, no action needed",
        },
    ),
    "tone": Choice(
        instructions="What is the customer's tone?",
        criteria={"calm": None, "frustrated": None, "angry": None},
    ),
}


def triage(ticket: str) -> None:
    with TypeSafeClient() as client:
        response = client.system_one(
            state=ticket,
            questions=TRIAGE_QUESTIONS,
        )
    answers = response.answers

    department = answers["department"]
    if department.confidence < 0.3:
        # Not clear which team to send to. Let a person decide.
        send_to_manual_triage(ticket)
        return

    if department.choice == "returns":
        # return_reason answer is only used here
        assign(ticket, team="returns", issue=answers["return_reason"].choice)
    elif department.choice == "shipping":
        # shipping_issue answer is only used here
        assign(ticket, team="shipping", issue=answers["shipping_issue"].choice)
    else:
        assign(ticket, team="billing")

    # A second team with a real share of the probability gets a copy
    for team, probability in department.probabilities.items():
        if team != department.choice and probability > 0.25:
            notify(ticket, team=team)

    resolution = answers["requested_resolution"]
    if resolution.confidence < 0.5:
        # The customer hasn't said what they want. Ask, don't guess.
        ask_customer_what_they_want(ticket)
    elif resolution.choice == "refund":
        flag_for_refund_approval(ticket)

    if answers["tone"].choice == "angry":
        flag_for_senior_agent(ticket)
```

对于上面这张工单，这段代码会把工单分派给退货团队，问题为 `wrong_size`；因为 billing 团队 0.35 的份额超过了 0.25 的阈值，会给它发送一份副本；又因为处理方式的置信度 0.20 低于 0.5，会询问客户想要什么。代码没有使用 `shipping_issue` 的答案。

一个请求，五个答案，而路由逻辑只是普通的 `if` 语句。如果以后需要知道客户使用的语言，或工单涉及哪个产品，只需向 `TRIAGE_QUESTIONS` 再添加一个 Choice 问题；请求数量仍然是一个。

[智能家居助手演示](/demos/smart-home) 在单次调用中，针对一长串 Choice 问题评估每个用户请求：请求类别、房间、设备和操作。这些问题中的大多数对任何一个请求都无关紧要，代码会忽略它们。

## 结构化 instructions 与 criteria

每个选项先用一行描述。当两个选项相似、模型总是混淆它们时，改用对象来描述每个选项。为其提供字段，说明该选项涵盖什么、什么其实属于相邻的选项，以及几个示例输入。

下面两个答案选项 return\_policy 和 return\_status 很容易混淆。涉及其中任何一个的工单都可能提到退货和退款，因此每个选项都说明了它不适用于什么。

<TypesafeExample
  display="request"
  example={{
state: 'I sent the shoes back a week ago. When do I get my money?',
selectedModels: ['jev-latest'],
questions: {
  return_topic: {
    type: 'choice',
    instructions: {
      question: 'Which returns topic is the customer asking about?',
      focus: 'Classify the information the customer wants.',
    },
    criteria: {
      return_policy: {
        what: 'Whether and how an item can be returned',
        not_for: 'Progress of a return already sent',
        examples: [
          "Can I return shoes I've worn once?",
          'How long do I have to return an order?',
        ],
      },
      return_status: {
        what: 'Progress of a return already sent',
        not_for: 'Whether and how an item can be returned',
        examples: [
          'Has my return arrived yet?',
          'When will my refund be paid?',
        ],
      },
    },
  },
},
}}
/>

响应是 `return_status`，置信度 1.0：

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "return_topic": {
      "type": "choice",
      "choice": "return_status",
      "confidence": 1.0,
      "probabilities": {
        "return_policy": 0.0,
        "return_status": 1.0
      }
    }
  },
  "usage": {
    "input_tokens": 407,
    "output_tokens": 32
  }
}
```

字段名 `question`、`focus`、`what`、`not_for` 和 `examples` 并不是 API 的一部分，也没有任何一个是保留字。由你来选择它们，就像选择选项名称一样。模型会连同值一起看到这些名称，因此请使用能标示其后内容的简短名称。
