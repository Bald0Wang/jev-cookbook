# Noul

> Noul 问题要求 TypeSafe 模型评估一个是/否问题，并返回答案为“是”的概率。

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

当答案是“是”或“否”时，使用 Noul。例如：这条消息是否要求退款、这份简历是否提到分布式系统、这条评论是否包含个人数据。如果答案是几个选项之一，请使用 [Choice](/primitives/choice)。如果是光谱上的一个位置，请使用 [Score](/primitives/score)。[选择问题类型](/primitives#choose-a-question-type)对这三种类型进行了比较。

Noul 的答案是一个数字，表示答案为“是”的概率，其中 0 表示否，1 表示是。

## 请求结构

发送到 [TypeSafe API](/api) 的 POST 请求体与任何其他问题类型一样具有相同的三个顶层字段：`state`（要评估的内容）、`model` 和 `questions`。每个 Noul 问题包含以下字段：

* `type`：始终为 `"noul"`。
* `instructions`：模型要回答的是/否问题，或供它判断的陈述。
* `criteria`：可选。一个对象，通过对“是”和“否”含义的 `true` 和 `false` 描述来说明。

下面是一个请求示例，其中状态是一条支持消息，两个问题分别是客户是否想找人和之前是否联系过支持团队：

<TypesafeExample
  display="request"
  example={{
state: 'I have asked three times now. Can I please just talk to a real person?',
selectedModels: ['jev-latest'],
questions: {
  is_human_escalation: {
    type: 'noul',
    instructions: 'Is the customer asking for a human agent?',
  },
  is_repeat_contact: {
    type: 'noul',
    instructions: 'Has the customer contacted support about this before?',
    criteria: {
      true: 'Mentions a prior attempt, ticket, or that they have asked before',
      false: 'No sign of any previous contact',
    },
  },
},
}}
/>

问题 id 由你选择，此处为 `is_human_escalation` 和 `is_repeat_contact`。这些 id 不会发送给模型。每个答案都以相同的 id 返回。第一个问题仅依靠 `instructions`。第二个问题添加了 `criteria` 来说明什么算“是”、什么算“否”。

使用 [Python SDK](/sdk/python) 时，同样的问题是 `Noul` 对象：

```python theme={null}
from typesafe_sdk import Noul, NoulCriteria, TypeSafeClient

with TypeSafeClient() as client:
    response = client.system_one(
        model="jev-latest",
        state="I have asked three times now. Can I please just talk to a real person?",
        questions={
            "is_human_escalation": Noul(
                instructions="Is the customer asking for a human agent?",
            ),
            "is_repeat_contact": Noul(
                instructions="Has the customer contacted support about this before?",
                criteria=NoulCriteria(
                    true="Mentions a prior attempt, ticket, or that they have asked before",
                    false="No sign of any previous contact",
                ),
            ),
        },
    )

    print(response.answers["is_human_escalation"].noul)
    print(response.answers["is_repeat_contact"].noul)
```

`system_one` 方法和 `https://api.typesafe.ai/v1/systemone` 端点都以 TypeSafe 的 AI 模型 [System One](/concepts/system-one) 命名。[如何使用 TypeSafe 构建](/concepts/how-to-build-with-system-one)介绍了在代码中的什么位置使用它。

如果你正在使用编码 agent，请先安装 [TypeSafe agent 技能](/agent-skill#installation)，这样它就了解请求和响应的结构。

<Note>
  `instructions` 可以是字符串、对象或数组。先从字符串开始。当问题需要附带数据时（例如需要与状态进行比较的记录），或者当问题的一部分由你的代码构建时，使用对象。[在问题中使用结构](/concepts/how-to-build-with-system-one#use-structure-in-the-questions)解释了结构何时有帮助，[下面的示例](#structured-instructions)展示了用代码构建的问题。
</Note>

## 响应结构

响应中的 `answers` 为每个问题包含一个条目，以请求中的 id 为键：

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "is_human_escalation": {
      "type": "noul",
      "noul": 0.99
    },
    "is_repeat_contact": {
      "type": "noul",
      "noul": 0.93
    }
  },
  "usage": {
    "input_tokens": 360,
    "output_tokens": 39
  }
}
```

这里的两个答案都接近 1。客户说“能不能让我跟真人谈谈”，所以 `is_human_escalation` 为 0.99。“我已经问了三次了”符合 `is_repeat_contact` 的 `true` 描述，所以它为 0.93。

## 解读 Noul

这个数字同时是答案和确定性。接近 1 的值表示强烈的“是”。接近 0 的值表示强烈的“否”。接近 0.5 的值表示模型认为“是”和“否”的概率相近。

下表展示了 `jev-1.13.0` 对不同客户消息在 `is_human_escalation` 问题上的记录答案：

| 状态 | `noul` |
| --- | --- |
| 谢谢，问题解决了！ | 0.02 |
| 怎么重置密码？ | 0.07 |
| 我今天就需要解决这个问题，不惜一切代价。 | 0.26 |
| 你是机器人吗？ | 0.40 |
| 有没有办法找人谈谈我的发票？ | 0.84 |
| 我已经问了三次了。能不能让我跟真人谈谈？ | 0.99 |

前两条和最后两条都很明确。“我今天就需要解决”很紧急，但从未要求找人，得到 0.26。“你是机器人吗？”暗示了想找真人却没有直接开口要，模型以 0.40 几乎五五开。这两条都是需要根据代码中的阈值来做决策的那类消息。

与 [Choice](/primitives/choice) 或 [Score](/primitives/score) 不同，Noul 没有单独的 `confidence` 值。Noul 的概率分布只有“是”和“否”两种结果，所以单个 `noul` 值就能完整描述它。Choice 或 Score 会把概率分布在多个选项或级别上，`confidence` 概括了这种分散程度。

最常见的做法是让代码把 `noul` 按阈值转成布尔值：

```python theme={null}
wants_human = response.answers["is_human_escalation"].noul > 0.9

if wants_human:
    route_to_agent(ticket)
else:
    route_to_bot(ticket)
```

阈值设在哪里取决于出错的代价。当“是”和“否”都同样容易处理时，使用 0.5。当根据错误的“是”行动代价很高时（例如呼叫某人或发放退款），调高它。当漏掉一个真正的“是”代价很高时（例如未能标记安全问题），调低它。处于中间的值可以交给人工，而不是走任何一条代码路径。这与 [Confidence](/confidence#three-paths-for-using-confidence-in-your-code) 页面为 Choice 和 Score 答案描述的三路分流相同。

Noul 的值从 0 到 1，但它并不是你所问事物本身程度的量表。它是答案为“是”的概率。如果问题实际上是关于程度的，这个值并不衡量程度。下面针对四位候选人提出“该候选人 Python 强吗？”，旁边是具有四个级别（无经验、略有了解、工作中经常使用、深厚专业能力）的 [Score](/primitives/score)：

| 候选人 | Noul：“该候选人 Python 强吗？” | Score：“该候选人有多少 Python 经验？” |
| --- | --- | --- |
| 我的经验在 Java 和 Go。我没有用过 Python。 | 0.03 | 0.0（无经验） |
| 在主要的 Java 工作之外，我偶尔用 Python 写些小脚本。 | 0.14 | 1.0（略有了解） |
| 在上一份工作中，我连续两年每天使用 Python，主要是数据流水线。 | 0.81 | 2.05（工作中经常使用） |
| 我八年来每天编写 Python，包括维护一个大型 Django 代码库。 | 0.92 | 2.89（深厚专业能力） |

Noul 判断的是一个命题——“强”，值表示它成立的可能性。你可以在代码中创建 0 到 1 范围内的级别，比如用 0.3 到 0.7 表示“有一定经验”，但模型看不到它们，因此答案中没有任何内容是针对这些级别判断的。一个中间值可能意味着经验中等，也可能意味着情况不明，候选人之间的间距也不是你选定的。Score 则是独立判断每个级别描述，所以每位候选人都落在你写的某个级别上或其附近，返回的概率显示了模型如何在级别之间分配它的判断。如果你不认同，可以改写某个级别并重新运行。[选择问题类型](/primitives#choose-a-question-type)解释了这一区别。

## 编写 Noul 问题

每个 Noul 只问一个是/否问题。如果一个问题包含两个条件，例如“客户是否既生气又在要求退款？”，模型就必须同时判断两者，值的意义也会减弱。请提出两个 Noul 问题，然后在代码中组合。

措辞上要让高值表示“是”。“这条消息是否包含个人数据？”很清晰。“这条消息是否不含个人数据？”把含义反转了，日后阅读这段代码的人会理解反。

陈述句和疑问句同样有效。对于“客户正在要求退款”，接近 1 的值表示该陈述为真。用你自己的数据尝试两种措辞，看看哪种效果更好。

让“是”与“否”之间的边界毫无歧义。“这位候选人是否有任何 Python 经验？”效果很好，因为“任何”没有留下中间地带。当边界比较微妙时，添加带有 `true` 和 `false` 描述的 `criteria`，就像上面的 `is_repeat_contact` 问题那样。对大多数 Noul 来说，instructions 就足够了，所以请尝试带和不带 `criteria` 的版本，保留在你的文档上给出更好答案的那个。

## 最佳实践：一次调用提出多个问题

对于一组条件清单，在一个请求中提出多个 Noul 问题：每个条件一个问题，由代码决定组合的含义。问题会被并行评估，所以增加 Noul 几乎不会改变响应时间。[一次提出多个问题](/primitives#ask-multiple-questions-together)对此有更详细的说明。

## 在代码中处理多个 Noul 答案

上面包含两个问题的请求已经足以为消息做路由。下面的示例在客户要求找真人时升级给人工，并在客户之前联系过时提高优先级。任一问题出现中间值时，都会交给审核人员而不是走代码路径：

```python theme={null}
from typesafe_sdk import Noul, NoulCriteria, TypeSafeClient

SUPPORT_QUESTIONS = {
    "is_human_escalation": Noul(
        instructions="Is the customer asking for a human agent?",
    ),
    "is_repeat_contact": Noul(
        instructions="Has the customer contacted support about this before?",
        criteria=NoulCriteria(
            true="Mentions a prior attempt, ticket, or that they have asked before",
            false="No sign of any previous contact",
        ),
    ),
}

YES = 0.8
NO = 0.2


def route(message: str) -> None:
    with TypeSafeClient() as client:
        response = client.system_one(
            model="jev-latest",
            state=message,
            questions=SUPPORT_QUESTIONS,
        )
    answers = response.answers

    wants_human = answers["is_human_escalation"].noul
    repeat = answers["is_repeat_contact"].noul

    if NO < wants_human < YES or NO < repeat < YES:
        # The model isn't sure either way. Let a person decide.
        send_to_review(message)
        return

    priority = "high" if repeat > YES else "normal"
    if wants_human > YES:
        route_to_agent(message, priority=priority)
    else:
        route_to_bot(message, priority=priority)
```

对于上面的消息，`is_human_escalation` 的 noul 答案值为 0.99，`is_repeat_contact` 为 0.93，因此代码以高优先级把它路由给人工坐席。消息“怎么重置密码？”在两个问题上都是 0.07，被路由给机器人。

阈值存在于你的代码中。如果审核人员看到的消息太多，就缩小 `NO` 与 `YES` 之间的差距。如果太多错误路由漏了过去，就扩大它。如果以后需要知道消息是否提到付款，或者是否包含个人数据，在 `SUPPORT_QUESTIONS` 中再加一个 Noul 即可。请求数量保持为一个。

## 结构化 instructions

Instructions 可以是对象而不是字符串，问题放在其中一个字段，其余字段放补充数据。[在问题中使用结构](/concepts/how-to-build-with-system-one#use-structure-in-the-questions)介绍了何时这样做有帮助。这里用它来构建由代码生成的问题：把刚收到的一份简历与候选人数据库中可能是同一个人的记录进行比较。每条记录原样放入 `potential_duplicate` 字段，`question` 对每条记录都相同，所有记录都在一个请求中检查。代码生成的问题键包含每条记录的数据库 ID：

<TypesafeExample
  display="request"
  example={{
state: {
  resume: {
    name: 'John Smith',
    location: 'Oakland, CA',
    summary: 'Backend engineer with eight years of Python and Go experience.',
    experience: [
      { employer: 'Google', title: 'Senior Backend Engineer', years: '2021-2025' },
      { employer: 'Microsoft', title: 'Software Engineer', years: '2017-2021' },
    ],
  },
},
selectedModels: ['jev-latest'],
questions: {
  same_as_record_18: {
    type: 'noul',
    instructions: {
      potential_duplicate: { name: 'Jon Smith', location: 'Oakland, CA', last_employer: 'Google' },
      question: 'Is the resume for the same person as `potential_duplicate`?',
    },
  },
  same_as_record_42: {
    type: 'noul',
    instructions: {
      potential_duplicate: { name: 'John Smith', location: 'Austin, TX', last_employer: 'Lone Star Freight' },
      question: 'Is the resume for the same person as `potential_duplicate`?',
    },
  },
  same_as_record_77: {
    type: 'noul',
    instructions: {
      potential_duplicate: { name: 'John Smithers', location: 'Oakland, CA', last_employer: 'Bay Health Clinic' },
      question: 'Is the resume for the same person as `potential_duplicate`?',
    },
  },
},
}}
/>

响应：

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "same_as_record_18": {
      "type": "noul",
      "noul": 0.74
    },
    "same_as_record_42": {
      "type": "noul",
      "noul": 0.09
    },
    "same_as_record_77": {
      "type": "noul",
      "noul": 0.08
    }
  },
  "usage": {
    "input_tokens": 535,
    "output_tokens": 58
  }
}
```

每个答案都是这份简历属于该记录中那个人的概率。记录 18 的名字拼写不同，但地点和雇主匹配，得到 0.74。记录 42 名字相同，但城市和雇主不同，得到 0.09。记录 77 名字相近、地点相同，但雇主不同，得到 0.08。在代码中像[在代码中处理多个 Noul 答案](#handling-multiple-noul-answers-in-code)那样为每个值设置阈值，并把中间值交给人工。

使用 Python SDK 时，问题由候选人记录构建。问题文本固定，变化的是记录：

```python theme={null}
from typesafe_sdk import Noul, TypeSafeClient

SAME_PERSON = "Is the resume for the same person as `potential_duplicate`?"


def duplicate_questions(candidates: list[dict]) -> dict[str, Noul]:
    """One Noul per candidate record, all asking the same question."""
    return {
        f"same_as_record_{candidate['id']}": Noul(
            instructions={
                "potential_duplicate": {
                    "name": candidate["name"],
                    "location": candidate["location"],
                    "last_employer": candidate["last_employer"],
                },
                "question": SAME_PERSON,
            },
        )
        for candidate in candidates
    }


def find_duplicates(resume: dict, candidates: list[dict]) -> list[str]:
    with TypeSafeClient() as client:
        response = client.system_one(
            model="jev-latest",
            state={"resume": resume},
            questions=duplicate_questions(candidates),
        )
    return [
        question_id
        for question_id, answer in response.answers.items()
        if answer.noul > 0.7
    ]
```

[结构化数据提取级联实战指南](/cookbooks/sde_cascade)使用结构化 instructions 来验证提取出的记录。每个字段都会得到同一组问题。每个问题的 `instructions` 对象在 `main_question` 属性中存放问题文本。还有 `field_spec` 和 `extracted_field` 属性随每个字段变化。

## 实战指南中的 Noul

看看我们的实战指南，了解使用 Noul 问题的应用：

* [并行问题](/cookbooks/parallel_questions)在单个请求中对一篇文章运行包含 13 个问题的合规检查清单。
* [自洽性：noul](/cookbooks/consistency_noul_cookbook)用一个包含 15 个问题的评分细则为保险理赔打分，并衡量各次运行之间数值的稳定性。
* [重排序](/cookbooks/rerank_typesafe)直接使用概率本身而非阈值：每个查询-候选对一个 Noul，然后按值对候选排序。
* [逐行搜索](/cookbooks/semantic_find)把找到匹配行的 Choice 与检查文档中是否根本存在答案的 Noul 配对使用。
* [结构恢复](/cookbooks/autoformat)对每对相邻行提出一个 Noul 问题（换行是否把一句话切开了），以从纯文本重建段落。
