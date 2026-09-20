# API 参考手册

> TypeSafe 评估端点的完整 HTTP API 参考。

对照一组类型化的 `questions` 评估 `state`，并返回结构化的 `answers`，每个问题对应一个答案。如需引导式入门，请从[原语](/primitives)开始。

## 评估端点

```http theme={null}
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

## 请求体

每个请求的顶层结构。`questions` 映射中的每一项都是一个由你命名的类型化问题。

<ParamField body="state" type="string | object | array" required>
  要评估的内容。纯文本使用字符串；聊天记录、数据条目或应用当前状态等内容使用结构化数据（对象/数组）。格式与最佳实践参见 [State](/concepts/state)。
</ParamField>

<ParamField body="model" type="string" required>
  处理该请求的模型。请使用 `"jev-latest"`，即 TypeSafe 的旗舰模型。可用模型与别名参见 [Models](/models)。
</ParamField>

<ParamField body="questions" type="map<string, Question>" required>
  类型化 [Question](#question-types) 对象的映射。每个键由你选择；答案会以相同的键返回。

  <Expandable title="映射条目">
    <ParamField body="‹question id›" type="Question">
      由你选择的键。对应的 [Answer](#answer-types) 会以相同的 id 返回。该键不会发送给底层模型，也不参与推理。
    </ParamField>
  </Expandable>
</ParamField>

```json Example request theme={null}
{
  "state": "Help! My payouts have been failing for 3 days.",
  "model": "jev-latest",
  "questions": {
    "is_urgent": {
      "type": "noul",
      "instructions": "Does this convey urgency?"
    }
  }
}
```

## 问题类型

`Question` 共有三种类型，由其 `type` 字段设定。三者在 `type` 和 `instructions` 上相同；每种类型各自增加自己的 `criteria`。

`instructions` 属性可以是字符串、对象或数组。对于包含额外上下文或需要引用数据的长问题，你可以把它拆成结构化对象：把问题放在一个字段中，数据放在其他字段中，并像把问题指向嵌套 `state` 值那样，用反引号按名称引用数据字段：

```json theme={null}
"instructions": {
  "potential_duplicate": {
    "name": "John Smith",
    "location": "Oakland, California",
    "last_employer": "Google"
  },
  "question": "Is the resume for the same person as `potential_duplicate`?"
}
```

详情参见[在问题中使用结构](/concepts/how-to-build-with-system-one#use-structure-in-the-questions)。

### Noul

一个是/否问题。返回答案为"是"的概率。

<ParamField body="type" type="&#x22;noul&#x22;" required />

<ParamField body="instructions" type="string | object | array" required>
  要评估的是/否问题。对象可以把问题放在一个字段，把它引用的数据放在其他字段；参见[在问题中使用结构](/concepts/how-to-build-with-system-one#use-structure-in-the-questions)。
</ParamField>

<ParamField body="criteria" type="object">
  可选：描述"是"与"否"各自的含义。

  <Expandable title="属性">
    <ParamField body="true" type="string | object | array">
      "是"（数值接近 1）的含义。
    </ParamField>

    <ParamField body="false" type="string | object | array">
      "否"（数值接近 0）的含义。
    </ParamField>
  </Expandable>
</ParamField>

```json Example request focus={5-12} theme={null}
{
  "state": "Help! My payouts have been failing for 3 days.",
  "model": "jev-latest",
  "questions": {
    "is_urgent": {
      "type": "noul",
      "instructions": "Does this convey urgency?",
      "criteria": {
        "true": "Explicitly time-sensitive",
        "false": "No urgency expressed"
      }
    }
  }
}
```

### Choice

从你定义的选项集合中挑选一个选项。返回被选中的选项以及完整的概率分布。

<ParamField body="type" type="&#x22;choice&#x22;" required />

<ParamField body="instructions" type="string | object | array" required>
  模型需要决定的内容。对象可以把问题放在一个字段，把它引用的数据放在其他字段；参见[结构化的 instructions 与 criteria](/primitives/choice#structured-instructions-and-criteria)。
</ParamField>

<ParamField body="criteria" type="map<string, string | object | array | null>" required>
  选项到评分标准描述的映射；当某个选项无需额外细节时使用 null。每个 Choice 最多可包含 255 个选项。

  <Expandable title="映射条目">
    <ParamField body="‹option›" type="string | object | array | null">
      由你选择的键。对该选项的描述。
    </ParamField>
  </Expandable>
</ParamField>

```json Example request focus={5-13} theme={null}
{
  "state": "Help! My payouts have been failing for 3 days.",
  "model": "jev-latest",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle this?",
      "criteria": {
        "billing": "Payments, invoicing, refunds",
        "technical": "Bugs, outages, integrations",
        "sales": "Pricing, upgrades, new accounts"
      }
    }
  }
}
```

### Score

按照你定义的评分标准为状态打分。返回跨各级别的概率加权值。

<ParamField body="type" type="&#x22;score&#x22;" required />

<ParamField body="instructions" type="string | object | array" required>
  模型需要评分的内容。对象可以把问题放在一个字段，把它引用的数据放在其他字段；参见[在问题中使用结构](/concepts/how-to-build-with-system-one#use-structure-in-the-questions)。
</ParamField>

<ParamField body="criteria" type="array<string | object | array>" required>
  按顺序排列的级别描述数组。一个 Score 应至少包含两个级别；API 最多接受 10 个。
</ParamField>

```json Example request focus={5-9} theme={null}
{
  "state": "Help! My payouts have been failing for 3 days.",
  "model": "jev-latest",
  "questions": {
    "frustration": {
      "type": "score",
      "instructions": "How frustrated is the customer?",
      "criteria": ["Calm", "Frustrated", "Very angry"]
    }
  }
}
```

## 响应体

每个问题对应一个答案，以你提供的相同 id 返回。

<ResponseField name="model" type="string" required>
  执行评估的模型。
</ResponseField>

<ResponseField name="answers" type="map<string, Answer>" required>
  每个问题对应一个 [Answer](#answer-types)，以你在 questions 中使用的相同 id 作为键。

  <Expandable title="映射条目">
    <ResponseField name="‹question id›" type="Answer">
      与你在 questions 中选择的相同 id。
    </ResponseField>
  </Expandable>
</ResponseField>

<ResponseField name="usage" type="object" required>
  该请求的 token 用量。

  <Expandable title="属性">
    <ResponseField name="input_tokens" type="integer" />

    <ResponseField name="output_tokens" type="integer" />
  </Expandable>
</ResponseField>

```json Example response theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "is_urgent": {
      "type": "noul",
      "noul": 0.95
    }
  },
  "usage": { "input_tokens": 296, "output_tokens": 20 }
}
```

## 答案类型

每个答案都带有与其问题匹配的 `type`。Choice 与 Score 答案还带有 0 到 1 之间的 `confidence`，由答案的概率分布推导得出。参见 [Confidence](/confidence)。

### Noul 答案

<ResponseField name="type" type="&#x22;noul&#x22;" required />

<ResponseField name="noul" type="number" required>
  以 0（否）到 1（是）为刻度的是/否答案。
</ResponseField>

```json Example response focus={4-7} theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "is_urgent": {
      "type": "noul",
      "noul": 0.95
    }
  },
  "usage": { "input_tokens": 307, "output_tokens": 20 }
}
```

### Choice 答案

<ResponseField name="type" type="&#x22;choice&#x22;" required />

<ResponseField name="choice" type="string" required>
  概率最高的选项。
</ResponseField>

<ResponseField name="probabilities" type="map<string, number>" required>
  每个选项映射到其概率（总和为 1 的浮点数）。

  <Expandable title="映射条目">
    <ResponseField name="‹option›" type="number">
      你在 criteria 中定义的一个选项。
    </ResponseField>
  </Expandable>
</ResponseField>

<ResponseField name="confidence" type="number" required>
  模型的确信程度，由概率推导得出。
</ResponseField>

```json Example response focus={4-9} theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "department": {
      "type": "choice",
      "choice": "billing",
      "probabilities": { "billing": 0.88, "technical": 0.12, "sales": 0.0 },
      "confidence": 0.81
    }
  },
  "usage": { "input_tokens": 318, "output_tokens": 34 }
}
```

### Score 答案

<ResponseField name="type" type="&#x22;score&#x22;" required />

<ResponseField name="score" type="number" required>
  跨各级别的概率加权答案；可能落在两个级别之间。
</ResponseField>

<ResponseField name="legend" type="map<string, string>" required>
  每个级别编号映射回其描述。
</ResponseField>

<ResponseField name="probabilities" type="map<string, number>" required>
  每个级别（字符串键）映射到其概率（总和为 1 的浮点数）。

  <Expandable title="映射条目">
    <ResponseField name="‹level›" type="number">
      级别索引，以与 legend 一致的字符串键表示。
    </ResponseField>
  </Expandable>
</ResponseField>

<ResponseField name="confidence" type="number" required>
  模型的确信程度，由概率推导得出。
</ResponseField>

```json Example response focus={4-10} theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "frustration": {
      "type": "score",
      "score": 1.05,
      "legend": { "0": "Calm", "1": "Frustrated", "2": "Very angry" },
      "probabilities": { "0": 0.0, "1": 0.95, "2": 0.05 },
      "confidence": 0.92
    }
  },
  "usage": { "input_tokens": 304, "output_tokens": 18 }
}
```

## 错误

错误使用标准 HTTP 状态码，并附带描述问题所在的 JSON 响应体。

| Status                     | 含义                                                                     |
| -------------------------- | ------------------------------------------------------------------------ |
| `401 Unauthorized`         | 缺少或无效的 API key。请检查 `Authorization` 请求头。                     |
| `422 Unprocessable Entity` | 请求体未通过校验——例如缺少必填字段或问题格式不正确。响应体会详细说明出错的字段。 |
| `429 Too Many Requests`    | 你已超出速率限制。请稍作退避后再重试。                                   |
| `529 Overloaded`           | TypeSafe 暂时过载。请稍作延迟后重试。                                    |

### 处理速率限制

当收到 `429 Too Many Requests` 或 `529 Overloaded` 响应时，请使用指数退避方式重试请求，而不是立即重试。我们的客户端 SDK 会自动处理这种情况，因此如果你使用我们的任一 SDK 及其默认重试策略，就无需额外处理。
