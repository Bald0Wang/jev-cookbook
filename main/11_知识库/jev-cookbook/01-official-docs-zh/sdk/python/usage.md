# 用法

> 使用 TypeSafe Python SDK 的指南与模式。

<a id="usage" />

<h2 id="calling-the-system-one-api">
  调用 System One API
</h2>

<Tabs>
  <Tab title="Async">
    ```python theme={null}
    import asyncio

    from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score


    async def main() -> None:
        async with AsyncTypeSafeClient() as client:
            result = await client.system_one(
                "I was charged twice. Please help ASAP.",
                {
                    "billing": Noul(instructions="Is this about billing?"),
                    "tone": Choice(
                        instructions="What is the tone?",
                        criteria={"calm": None, "angry": None},
                    ),
                    "urgency": Score(
                        instructions="How urgent is this?",
                        criteria=["low", "medium", "high"],
                    ),
                },
            )
            print(
                result.nouls["billing"].noul,
                result.choices["tone"].choice,
                result.scores["urgency"].score,
            )


    asyncio.run(main())
    ```
  </Tab>

  <Tab title="Sync">
    ```python theme={null}
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

    client = TypeSafeClient()
    state = "I was charged twice. Please help ASAP."
    questions = {
        "billing": Noul(instructions="Is this about billing?"),
        "tone": Choice(
            instructions="What is the tone?", criteria={"calm": None, "angry": None}
        ),
        "urgency": Score(
            instructions="How urgent is this?", criteria=["low", "medium", "high"]
        ),
    }
    result = client.system_one(state, questions)
    print(
        result.nouls["billing"].noul,
        result.choices["tone"].choice,
        result.scores["urgency"].score,
    )
    ```
  </Tab>
</Tabs>

<h2 id="typed-system_one-responses">
  类型化的 <code>system\_one</code> 响应
</h2>

可以为 `system_one` 提供一个响应模型，使响应的使用更具*类型安全性*：

```python theme={null}
from typesafe_sdk import Noul, NoulAnswer, SystemOneResponse, TypeSafeClient


class BillingResponse(SystemOneResponse):
    billing: NoulAnswer


with TypeSafeClient() as client:
    result = client.system_one(
        "I was charged twice.",
        {"billing": Noul(instructions="Is this about billing?")},
        response_model=BillingResponse,
    )
    assert 0 <= result.billing.noul <= 1
    assert result.billing == result.nouls["billing"]
    print(result.request_id)
```

<h3 id="custom-response-types">
  自定义响应类型
</h3>

也可以定义一个全新的响应模型，而无需继承 `SystemOneResponse`：

```python theme={null}
from pydantic import BaseModel

from typesafe_sdk import Noul, NoulAnswer, TypeSafeClient


class BillingAnswers(BaseModel):
    billing: NoulAnswer


class BillingResponse(BaseModel):
    answers: BillingAnswers


result = TypeSafeClient().system_one(
    "I was charged twice.",
    {"billing": Noul(instructions="Is this about billing?")},
    response_model=BillingResponse,
)
assert 0 <= result.answers.billing.noul <= 1
```

<h2 id="choosing-a-model">
  选择模型
</h2>

查看可用模型：

```python theme={null}
from typesafe_sdk import TypeSafeClient

print(TypeSafeClient().models.list())
```

在构造客户端时选择模型：

```python theme={null}
client = TypeSafeClient(model="jev")
```

详见 [Models 资源参考](/sdk/python/api/clients/sync#models-resource)。

<h2 id="retries">
  重试
</h2>

在客户端上或按单次调用传入自定义的 [`RetryPolicy`](/sdk/python/api/retries) 作为 `retry`。

<Tabs>
  <Tab title="Client">
    ```python theme={null}
    from typesafe_sdk import RetryPolicy, TypeSafeClient

    client = TypeSafeClient(retry=RetryPolicy(max_retries=3, backoff_max=0.2, timeout=1.0))
    ```
  </Tab>

  <Tab title="Per-call">
    ```python theme={null}
    from typesafe_sdk import RetryPolicy

    client.system_one(
        state, questions, retry=RetryPolicy(max_retries=3, backoff_max=0.2, timeout=1.0)
    )
    ```
  </Tab>
</Tabs>

<h2 id="error-handling">
  错误处理
</h2>

处理 SDK 引发的[异常](/sdk/python/api/exceptions)：

```python theme={null}
from typesafe_sdk import TypeSafeAPIError

try:
    client.system_one(state, questions)
except TypeSafeAPIError as error:
    print(error.status, error.request_id)
```

<h2 id="logging">
  日志
</h2>

SDK 会将日志记录到 `typesafe_sdk` logger。可按照 [标准 logging](https://docs.python.org/3/library/logging.html) 指南进行配置：

```python theme={null}
import logging

logging.getLogger("typesafe_sdk").setLevel(logging.DEBUG)
```

或在导入 SDK 之前，将 `TYPESAFE_LOG_LEVEL` 设置为 `debug`、`info`、`warning`、`error` 或 `off` 之一。

`info` 会为每个请求记录一行摘要；`debug` 还会记录请求与响应的头和体。敏感请求头——authorization、API key、cookie，以及名称中包含 `token` 或 `secret` 的任何请求头——都会从日志输出中脱敏。请求体与响应体**不会**脱敏。

<h2 id="environment-variables">
  环境变量
</h2>

SDK 会读取并使用以下环境变量：

| 变量                 | 配置项                                    | 默认值                    |
| -------------------- | ----------------------------------------- | ------------------------- |
| `TYPESAFE_API_KEY`   | API key（必需）                           | —                         |
| `TYPESAFE_BASE_URL`  | API 根 URL                                | `https://api.typesafe.ai` |
| `TYPESAFE_DEFAULT_MODEL` | 默认模型                              | `jev-latest`              |
| `TYPESAFE_LOG_LEVEL` | `typesafe_sdk` logger 级别，导入时应用一次 | 未设置                    |

SDK 默认值详见[常量参考](/sdk/python/api/constants)。

<h2 id="forward-compatibility">
  向前兼容
</h2>

随着 TypeSafe API 的演进，SDK 仍能持续正常工作，因此你可以在 SDK 版本为其提供一等支持之前，先行采用新的 API 特性。

<h3 id="extra-request-fields">
  额外请求字段
</h3>

通过 [`extra_body`](/sdk/python/api/clients/sync) 发送当前 SDK 版本尚不支持的请求字段：

```python theme={null}
from typesafe_sdk import Noul, TypeSafeClient

with TypeSafeClient() as client:
    client.system_one(
        "I was charged twice.",
        {"billing": Noul(instructions="About billing?")},
        extra_body={"beam_width": 4},
    )
```

<h3 id="raw-question-dictionaries">
  原始问题字典
</h3>

```python theme={null}
from typesafe_sdk import TypeSafeClient

with TypeSafeClient() as client:
    client.system_one(
        "I was charged twice.",
        {"billing": {"type": "noul", "instructions": "About billing?", "weight": 2}},
    )
```

<Tip>
  **提示**

  未知字段是一种向前兼容的应急手段。忽略由此产生的类型检查错误，并优先选择升级 SDK。
</Tip>

<h3 id="unknown-answer-kinds">
  未知的答案类型
</h3>

SDK 会记录一条警告并跳过无法识别的答案类型。可使用 `raw_http_response` 检查完整的 API 响应，包括这些答案：

```python theme={null}
from typesafe_sdk import Noul, TypeSafeClient

result = TypeSafeClient().system_one(
    "I was charged twice.",
    {"billing": Noul(instructions="Is this about billing?")},
)
raw_answers = result.raw_http_response.json()["answers"]
```

<h3 id="unknown-response-fields">
  未知的响应字段
</h3>

已识别响应上的未知额外字段会被忽略。
