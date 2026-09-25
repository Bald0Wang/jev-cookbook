# 答案与响应

> 阅读 TypeSafe API 返回的答案、置信度分数、token 用量以及可用模型。

export function SdkSignature({children}) {
  async function copy(event) {
    const button = event.currentTarget;
    const code = button.parentElement.querySelector("pre code");
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.setAttribute("aria-label", "Signature copied");
      button.dataset.copied = "true";
    } catch {
      button.setAttribute("aria-label", "Copy failed; select the signature to copy");
    }
    setTimeout(() => {
      button.setAttribute("aria-label", "Copy signature");
      delete button.dataset.copied;
    }, 2000);
  }
  return <div className="sdk-signature not-prose">
      <button type="button" className="sdk-signature-copy" aria-label="Copy signature" onClick={copy}>
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="8" y="8" width="12" height="12" rx="2" />
          <path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" />
        </svg>
      </button>
      <pre tabIndex={0} aria-label="SDK signature"><code>{children}</code></pre>
    </div>;
}

<a id="answers-and-responses" />

<h2 id="response">
  响应
</h2>

<h2 id="typesafe_sdk.SystemOneResponse">
  typesafe\_sdk.SystemOneResponse
</h2>

`pydantic-model`

基类：`Response`

按问题类型分组的答案，附带模型与用量元数据。

详见 [System One](https://docs.typesafe.ai/concepts/system-one)。

<Note>
  **显示 JSON schema：**

  <Accordion title="Details" id="sdk-disclosure-1">
    ```json theme={null}
    {
      "$defs": {
        "ChoiceAnswer": {
          "description": "A selected label and its probabilities.\n\nSee the [choice primitive](https://docs.typesafe.ai/primitives/choice) for details.",
          "properties": {
            "type": {
              "const": "choice",
              "default": "choice",
              "title": "Type",
              "type": "string"
            },
            "choice": {
              "description": "The name of the choice with the highest probability among the question's criteria.",
              "examples": [
                "angry"
              ],
              "title": "Choice",
              "type": "string"
            },
            "confidence": {
              "description": "Confidence in the selected choice, from 0 to 1. Higher values indicate greater certainty; use lower values to flag uncertain selections for review.",
              "examples": [
                0.9
              ],
              "title": "Confidence",
              "type": "number"
            },
            "probabilities": {
              "additionalProperties": {
                "type": "number"
              },
              "description": "Probability of each choice in criteria, keyed by choice name, from 0 to 1. Shows how likely the alternatives are; values sum to approximately 1.",
              "examples": [
                {
                  "angry": 0.8,
                  "calm": 0.1,
                  "excited": 0.1
                }
              ],
              "title": "Probabilities",
              "type": "object"
            }
          },
          "required": [
            "choice",
            "confidence",
            "probabilities"
          ],
          "title": "ChoiceAnswer",
          "type": "object"
        },
        "NoulAnswer": {
          "description": "A yes/no answer.\n\nSee the [noul primitive](https://docs.typesafe.ai/primitives/noul) for details.",
          "properties": {
            "type": {
              "const": "noul",
              "default": "noul",
              "title": "Type",
              "type": "string"
            },
            "noul": {
              "description": "Probability of a yes answer or a true statement, from 0 to 1. Values near 1 favor yes or true, values near 0 favor no or false, and values near 0.5 indicate uncertainty.",
              "examples": [
                0.98
              ],
              "title": "Noul",
              "type": "number"
            }
          },
          "required": [
            "noul"
          ],
          "title": "NoulAnswer",
          "type": "object"
        },
        "ScoreAnswer": {
          "description": "An expected score with its rubric and probabilities.\n\nSee the [score primitive](https://docs.typesafe.ai/primitives/score) for details.",
          "properties": {
            "type": {
              "const": "score",
              "default": "score",
              "title": "Type",
              "type": "string"
            },
            "score": {
              "description": "Expected score: the probability-weighted average of the rubric levels. May fall between integer levels.",
              "examples": [
                1.7
              ],
              "title": "Score",
              "type": "number"
            },
            "confidence": {
              "description": "Confidence in the score, from 0 to 1. Higher values indicate greater certainty; use lower values to flag uncertain ratings for review.",
              "examples": [
                0.9
              ],
              "title": "Confidence",
              "type": "number"
            },
            "legend": {
              "additionalProperties": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "additionalProperties": true,
                    "type": "object"
                  },
                  {
                    "items": {},
                    "type": "array"
                  }
                ]
              },
              "title": "Legend",
              "type": "object"
            },
            "probabilities": {
              "additionalProperties": {
                "type": "number"
              },
              "title": "Probabilities",
              "type": "object"
            }
          },
          "required": [
            "score",
            "confidence",
            "legend",
            "probabilities"
          ],
          "title": "ScoreAnswer",
          "type": "object"
        },
        "Usage": {
          "description": "Token counts for a request, when reported by the API.",
          "properties": {
            "input_tokens": {
              "anyOf": [
                {
                  "type": "integer"
                },
                {
                  "type": "null"
                }
              ],
              "default": null,
              "title": "Input Tokens"
            },
            "output_tokens": {
              "anyOf": [
                {
                  "type": "integer"
                },
                {
                  "type": "null"
                }
              ],
              "default": null,
              "title": "Output Tokens"
            }
          },
          "title": "Usage",
          "type": "object"
        }
      },
      "description": "Answers grouped by question type with model and usage metadata.\n\nSee [System One](https://docs.typesafe.ai/concepts/system-one) for details.",
      "properties": {
        "model": {
          "title": "Model",
          "type": "string"
        },
        "usage": {
          "$ref": "#/$defs/Usage"
        },
        "answers": {
          "additionalProperties": {
            "discriminator": {
              "mapping": {
                "choice": "#/$defs/ChoiceAnswer",
                "noul": "#/$defs/NoulAnswer",
                "score": "#/$defs/ScoreAnswer"
              },
              "propertyName": "type"
            },
            "oneOf": [
              {
                "$ref": "#/$defs/NoulAnswer"
              },
              {
                "$ref": "#/$defs/ChoiceAnswer"
              },
              {
                "$ref": "#/$defs/ScoreAnswer"
              }
            ]
          },
          "title": "Answers",
          "type": "object"
        }
      },
      "required": [
        "model",
        "usage"
      ],
      "title": "SystemOneResponse",
      "type": "object"
    }
    ```
  </Accordion>
</Note>

配置：

* `extra`: `ignore`
* `frozen`: `True`
* `strict`: `True`

字段：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.SystemOneResponse.model">model</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a></code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.SystemOneResponse.usage">usage</a></code> (<code><a href="/sdk/python/api/types/responses#typesafe_sdk.Usage">Usage</a></code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.SystemOneResponse.answers">answers</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#dict">dict</a>\[<a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>, <a href="/sdk/python/api/types/responses#typesafe_sdk.Answer">Answer</a>]</code>)

<h3 id="typesafe_sdk.SystemOneResponse.request_id">
  request\_id
</h3>

`cached` `property`

<SdkSignature>
  <span className="n">
    {"request_id"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

`x-typesafe-request-id` 响应头。

<h3 id="typesafe_sdk.SystemOneResponse.raw_http_response">
  raw\_http\_response
</h3>

`property`

```python theme={null}
raw_http_response: httpx2.Response
```

底层的 `httpx2.Response`，暴露状态码、请求头与响应体。

<h3 id="typesafe_sdk.SystemOneResponse.model_config">
  model\_config
</h3>

`class-attribute` `instance-attribute`

```python theme={null}
model_config = ConfigDict(
    extra="ignore", frozen=True, strict=True
)
```

<h3 id="typesafe_sdk.SystemOneResponse.model">
  model
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"model"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

用于回答该请求的模型。

<h3 id="typesafe_sdk.SystemOneResponse.usage">
  usage
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"usage"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="/sdk/python/api/types/responses#typesafe_sdk.Usage">
      {"Usage"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

该请求的 token 用量。

<h3 id="typesafe_sdk.SystemOneResponse.answers">
  answers
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"answers"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#dict">
      {"dict"}
    </a>
  </span>

  <span className="p">
    {"["}
  </span>

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  <span className="p">
    {","}
  </span>

  {" "}

  <span className="n">
    <a href="/sdk/python/api/types/responses#typesafe_sdk.Answer">
      {"Answer"}
    </a>
  </span>

  <span className="p">
    {"]"}
  </span>

  {"\n"}
</SdkSignature>

以问题名称为键的所有答案对象。

<h3 id="typesafe_sdk.SystemOneResponse.nouls">
  nouls
</h3>

`cached` `property`

<SdkSignature>
  <span className="n">
    {"nouls"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#dict">
      {"dict"}
    </a>
  </span>

  <span className="p">
    {"["}
  </span>

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  <span className="p">
    {","}
  </span>

  {" "}

  <span className="n">
    <a href="/sdk/python/api/types/responses#typesafe_sdk.NoulAnswer">
      {"NoulAnswer"}
    </a>
  </span>

  <span className="p">
    {"]"}
  </span>

  {"\n"}
</SdkSignature>

以问题名称为键的是/否答案。

<h3 id="typesafe_sdk.SystemOneResponse.choices">
  choices
</h3>

`cached` `property`

<SdkSignature>
  <span className="n">
    {"choices"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#dict">
      {"dict"}
    </a>
  </span>

  <span className="p">
    {"["}
  </span>

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  <span className="p">
    {","}
  </span>

  {" "}

  <span className="n">
    <a href="/sdk/python/api/types/responses#typesafe_sdk.ChoiceAnswer">
      {"ChoiceAnswer"}
    </a>
  </span>

  <span className="p">
    {"]"}
  </span>

  {"\n"}
</SdkSignature>

以问题名称为键的 Choice 答案。

<h3 id="typesafe_sdk.SystemOneResponse.scores">
  scores
</h3>

`cached` `property`

<SdkSignature>
  <span className="n">
    {"scores"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#dict">
      {"dict"}
    </a>
  </span>

  <span className="p">
    {"["}
  </span>

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  <span className="p">
    {","}
  </span>

  {" "}

  <span className="n">
    <a href="/sdk/python/api/types/responses#typesafe_sdk.ScoreAnswer">
      {"ScoreAnswer"}
    </a>
  </span>

  <span className="p">
    {"]"}
  </span>

  {"\n"}
</SdkSignature>

以问题名称为键的 Score 答案。

<h2 id="typesafe_sdk.Usage">
  typesafe\_sdk.Usage
</h2>

`pydantic-model`

基类：`wire.Usage`

请求的 token 计数（当 API 有报告时）。

<Note>
  **显示 JSON schema：**

  <Accordion title="Details" id="sdk-disclosure-2">
    ```json theme={null}
    {
      "description": "Token counts for a request, when reported by the API.",
      "properties": {
        "input_tokens": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Input Tokens"
        },
        "output_tokens": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Output Tokens"
        }
      },
      "title": "Usage",
      "type": "object"
    }
    ```
  </Accordion>
</Note>

配置：

* `extra`: `ignore`
* `frozen`: `True`
* `strict`: `True`

字段：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.Usage.input_tokens">input\_tokens</a></code> (<code><a href="https://docs.python.org/3/builtins/functions.html#int">int</a> | None</code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.Usage.output_tokens">output\_tokens</a></code> (<code><a href="https://docs.python.org/3/builtins/functions.html#int">int</a> | None</code>)

<h3 id="typesafe_sdk.Usage.model_config">
  model\_config
</h3>

`class-attribute` `instance-attribute`

```python theme={null}
model_config = ConfigDict(
    extra="ignore", frozen=True, strict=True
)
```

<h3 id="typesafe_sdk.Usage.input_tokens">
  input\_tokens
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"input_tokens"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#int">
      {"int"}
    </a>
  </span>

  {" "}

  <span className="o">
    {"|"}
  </span>

  {" "}

  <span className="kc">
    {"None"}
  </span>

  {" "}

  <span className="o">
    {"="}
  </span>

  {" "}

  <span className="kc">
    {"None"}
  </span>

  {"\n"}
</SdkSignature>

使用的输入 token 数量；若 API 未报告则为 `None`。

<h3 id="typesafe_sdk.Usage.output_tokens">
  output\_tokens
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"output_tokens"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#int">
      {"int"}
    </a>
  </span>

  {" "}

  <span className="o">
    {"|"}
  </span>

  {" "}

  <span className="kc">
    {"None"}
  </span>

  {" "}

  <span className="o">
    {"="}
  </span>

  {" "}

  <span className="kc">
    {"None"}
  </span>

  {"\n"}
</SdkSignature>

使用的输出 token 数量；若 API 未报告则为 `None`。

<h2 id="answers">
  答案
</h2>

<h2 id="typesafe_sdk.NoulAnswer">
  typesafe\_sdk.NoulAnswer
</h2>

`pydantic-model`

基类：`wire.NoulAnswer`

一个是/否答案。

详见 [noul 原语](https://docs.typesafe.ai/primitives/noul)。

<Note>
  **显示 JSON schema：**

  <Accordion title="Details" id="sdk-disclosure-3">
    ```json theme={null}
    {
      "description": "A yes/no answer.\n\nSee the [noul primitive](https://docs.typesafe.ai/primitives/noul) for details.",
      "properties": {
        "type": {
          "const": "noul",
          "default": "noul",
          "title": "Type",
          "type": "string"
        },
        "noul": {
          "description": "Probability of a yes answer or a true statement, from 0 to 1. Values near 1 favor yes or true, values near 0 favor no or false, and values near 0.5 indicate uncertainty.",
          "examples": [
            0.98
          ],
          "title": "Noul",
          "type": "number"
        }
      },
      "required": [
        "noul"
      ],
      "title": "NoulAnswer",
      "type": "object"
    }
    ```
  </Accordion>
</Note>

配置：

* `extra`: `ignore`
* `frozen`: `True`
* `strict`: `True`

字段：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.NoulAnswer.noul">noul</a></code> (<code><a href="https://docs.python.org/3/builtins/functions.html#float">float</a></code>)
* `type` (<code><a href="https://docs.python.org/3/library/typing.html#typing.Literal">Literal</a>\['noul']</code>)

<h3 id="typesafe_sdk.NoulAnswer.noul">
  noul
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"noul"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#float">
      {"float"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

是/否答案或真值陈述的概率，取值范围 0 到 1。接近 1 表示倾向于"是"或"真"，接近 0 表示倾向于"否"或"假"，接近 0.5 表示不确定。

<h3 id="typesafe_sdk.NoulAnswer.model_config">
  model\_config
</h3>

`class-attribute` `instance-attribute`

```python theme={null}
model_config = ConfigDict(
    extra="ignore", frozen=True, strict=True
)
```

<h2 id="typesafe_sdk.ChoiceAnswer">
  typesafe\_sdk.ChoiceAnswer
</h2>

`pydantic-model`

基类：`wire.ChoiceAnswer`

所选标签及其概率。

详见 [choice 原语](https://docs.typesafe.ai/primitives/choice)。

<Note>
  **显示 JSON schema：**

  <Accordion title="Details" id="sdk-disclosure-4">
    ```json theme={null}
    {
      "description": "A selected label and its probabilities.\n\nSee the [choice primitive](https://docs.typesafe.ai/primitives/choice) for details.",
      "properties": {
        "type": {
          "const": "choice",
          "default": "choice",
          "title": "Type",
          "type": "string"
        },
        "choice": {
          "description": "The name of the choice with the highest probability among the question's criteria.",
          "examples": [
            "angry"
          ],
          "title": "Choice",
          "type": "string"
        },
        "confidence": {
          "description": "Confidence in the selected choice, from 0 to 1. Higher values indicate greater certainty; use lower values to flag uncertain selections for review.",
          "examples": [
            0.9
          ],
          "title": "Confidence",
          "type": "number"
        },
        "probabilities": {
          "additionalProperties": {
            "type": "number"
          },
          "description": "Probability of each choice in criteria, keyed by choice name, from 0 to 1. Shows how likely the alternatives are; values sum to approximately 1.",
          "examples": [
            {
              "angry": 0.8,
              "calm": 0.1,
              "excited": 0.1
            }
          ],
          "title": "Probabilities",
          "type": "object"
        }
      },
      "required": [
        "choice",
        "confidence",
        "probabilities"
      ],
      "title": "ChoiceAnswer",
      "type": "object"
    }
    ```
  </Accordion>
</Note>

配置：

* `extra`: `ignore`
* `frozen`: `True`
* `strict`: `True`

字段：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ChoiceAnswer.choice">choice</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a></code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ChoiceAnswer.confidence">confidence</a></code> (<code><a href="https://docs.python.org/3/builtins/functions.html#float">float</a></code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ChoiceAnswer.probabilities">probabilities</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#dict">dict</a>\[<a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>, <a href="https://docs.python.org/3/builtins/functions.html#float">float</a>]</code>)
* `type` (<code><a href="https://docs.python.org/3/library/typing.html#typing.Literal">Literal</a>\['choice']</code>)

<h3 id="typesafe_sdk.ChoiceAnswer.choice">
  choice
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"choice"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

在问题的评判标准中概率最高的选项名称。

<h3 id="typesafe_sdk.ChoiceAnswer.confidence">
  confidence
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"confidence"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#float">
      {"float"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

所选选项的置信度，取值范围 0 到 1。值越高表示确定性越大；可用较低的值标记不确定的选择以便复核。

<h3 id="typesafe_sdk.ChoiceAnswer.probabilities">
  probabilities
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"probabilities"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#dict">
      {"dict"}
    </a>
  </span>

  <span className="p">
    {"["}
  </span>

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  <span className="p">
    {","}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#float">
      {"float"}
    </a>
  </span>

  <span className="p">
    {"]"}
  </span>

  {"\n"}
</SdkSignature>

标准中每个选项的概率，以选项名称为键，取值范围 0 到 1。表示各备选项的可能性；各值之和约为 1。

<h3 id="typesafe_sdk.ChoiceAnswer.model_config">
  model\_config
</h3>

`class-attribute` `instance-attribute`

```python theme={null}
model_config = ConfigDict(
    extra="ignore", frozen=True, strict=True
)
```

<h2 id="typesafe_sdk.ScoreAnswer">
  typesafe\_sdk.ScoreAnswer
</h2>

`pydantic-model`

基类：`wire.ScoreAnswer`

预期分数及其评分标准与概率。

详见 [score 原语](https://docs.typesafe.ai/primitives/score)。

<Note>
  **显示 JSON schema：**

  <Accordion title="Details" id="sdk-disclosure-5">
    ```json theme={null}
    {
      "description": "An expected score with its rubric and probabilities.\n\nSee the [score primitive](https://docs.typesafe.ai/primitives/score) for details.",
      "properties": {
        "type": {
          "const": "score",
          "default": "score",
          "title": "Type",
          "type": "string"
        },
        "score": {
          "description": "Expected score: the probability-weighted average of the rubric levels. May fall between integer levels.",
          "examples": [
            1.7
          ],
          "title": "Score",
          "type": "number"
        },
        "confidence": {
          "description": "Confidence in the score, from 0 to 1. Higher values indicate greater certainty; use lower values to flag uncertain ratings for review.",
          "examples": [
            0.9
          ],
          "title": "Confidence",
          "type": "number"
        },
        "legend": {
          "additionalProperties": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "items": {},
                "type": "array"
              }
            ]
          },
          "title": "Legend",
          "type": "object"
        },
        "probabilities": {
          "additionalProperties": {
            "type": "number"
          },
          "title": "Probabilities",
          "type": "object"
        }
      },
      "required": [
        "score",
        "confidence",
        "legend",
        "probabilities"
      ],
      "title": "ScoreAnswer",
      "type": "object"
    }
    ```
  </Accordion>
</Note>

配置：

* `extra`: `ignore`
* `frozen`: `True`
* `strict`: `True`

字段：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ScoreAnswer.score">score</a></code> (<code><a href="https://docs.python.org/3/builtins/functions.html#float">float</a></code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ScoreAnswer.confidence">confidence</a></code> (<code><a href="https://docs.python.org/3/builtins/functions.html#float">float</a></code>)
* `type` (<code><a href="https://docs.python.org/3/library/typing.html#typing.Literal">Literal</a>\['score']</code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ScoreAnswer.legend">legend</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#dict">dict</a>\[<a href="https://docs.python.org/3/builtins/functions.html#int">int</a>, <a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a> | <a href="https://docs.python.org/3/builtins/stdtypes.html#dict">dict</a>\[<a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>, <a href="https://docs.python.org/3/library/typing.html#typing.Any">Any</a>] | <a href="https://docs.python.org/3/builtins/stdtypes.html#list">list</a>\[<a href="https://docs.python.org/3/library/typing.html#typing.Any">Any</a>]]</code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ScoreAnswer.probabilities">probabilities</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#dict">dict</a>\[<a href="https://docs.python.org/3/builtins/functions.html#int">int</a>, <a href="https://docs.python.org/3/builtins/functions.html#float">float</a>]</code>)

<h3 id="typesafe_sdk.ScoreAnswer.score">
  score
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"score"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#float">
      {"float"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

预期分数：各评分档位的概率加权平均值。可能落在整数档位之间。

<h3 id="typesafe_sdk.ScoreAnswer.confidence">
  confidence
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"confidence"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#float">
      {"float"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

分数的置信度，取值范围 0 到 1。值越高表示确定性越大；可用较低的值标记不确定的评分以便复核。

<h3 id="typesafe_sdk.ScoreAnswer.model_config">
  model\_config
</h3>

`class-attribute` `instance-attribute`

```python theme={null}
model_config = ConfigDict(
    extra="ignore", frozen=True, strict=True
)
```

<h3 id="typesafe_sdk.ScoreAnswer.legend">
  legend
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">{"legend"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#dict">{"dict"}</a></span><span className="p">{"["}</span>{"\n"}{"    "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#int">{"int"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#dict">{"dict"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/typing.html#typing.Any">{"Any"}</a></span><span className="p">{"]"}</span>{" "}<span className="o">{"|"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#list">{"list"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/library/typing.html#typing.Any">{"Any"}</a></span><span className="p">{"]"}</span>{"\n"}<span className="p">{"]"}</span>{"\n"}
</SdkSignature>

以整数分数为键的评分标准描述。

<h3 id="typesafe_sdk.ScoreAnswer.probabilities">
  probabilities
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"probabilities"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#dict">
      {"dict"}
    </a>
  </span>

  <span className="p">
    {"["}
  </span>

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#int">
      {"int"}
    </a>
  </span>

  <span className="p">
    {","}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#float">
      {"float"}
    </a>
  </span>

  <span className="p">
    {"]"}
  </span>

  {"\n"}
</SdkSignature>

以整数分数为键的概率。

<h2 id="typesafe_sdk.Answer">
  typesafe\_sdk.Answer
</h2>

`module-attribute`

<SdkSignature>
  <span className="n">{"Answer"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/typing.html#typing.TypeAlias">{"TypeAlias"}</a></span>{" "}<span className="o">{"="}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/typing.html#typing.Annotated">{"Annotated"}</a></span><span className="p">{"["}</span>{"\n"}{"    "}<span className="n"><a href="/sdk/python/api/types/responses#typesafe_sdk.NoulAnswer">{"NoulAnswer"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="n"><a href="/sdk/python/api/types/responses#typesafe_sdk.ChoiceAnswer">{"ChoiceAnswer"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="n"><a href="/sdk/python/api/types/responses#typesafe_sdk.ScoreAnswer">{"ScoreAnswer"}</a></span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"Field"}</span><span className="p">{"("}</span><span className="n">{"discriminator"}</span><span className="o">{"="}</span><span className="s2">{"\"type\""}</span><span className="p">{"),"}</span>{"\n"}<span className="p">{"]"}</span>{"\n"}
</SdkSignature>

对单个问题的答案，由其 `type` 标识。

<h2 id="available-models">
  可用模型
</h2>

<h2 id="typesafe_sdk.ListModelsResponse">
  typesafe\_sdk.ListModelsResponse
</h2>

`pydantic-model`

基类：`Response`

该账户可用的模型。

<Note>
  **显示 JSON schema：**

  <Accordion title="Details" id="sdk-disclosure-6">
    ```json theme={null}
    {
      "$defs": {
        "ModelMetadata": {
          "description": "Metadata describing a single available model.",
          "properties": {
            "name": {
              "title": "Name",
              "type": "string"
            },
            "description": {
              "title": "Description",
              "type": "string"
            },
            "release_date": {
              "title": "Release Date",
              "type": "string"
            }
          },
          "required": [
            "name",
            "description",
            "release_date"
          ],
          "title": "ModelMetadata",
          "type": "object"
        }
      },
      "description": "The models available to the account.",
      "properties": {
        "models": {
          "items": {
            "$ref": "#/$defs/ModelMetadata"
          },
          "title": "Models",
          "type": "array"
        }
      },
      "required": [
        "models"
      ],
      "title": "ListModelsResponse",
      "type": "object"
    }
    ```
  </Accordion>
</Note>

字段：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ListModelsResponse.models">models</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#tuple">tuple</a>\[<a href="/sdk/python/api/types/responses#typesafe_sdk.ModelMetadata">ModelMetadata</a>, ...]</code>)

<h3 id="typesafe_sdk.ListModelsResponse.request_id">
  request\_id
</h3>

`cached` `property`

<SdkSignature>
  <span className="n">
    {"request_id"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

`x-typesafe-request-id` 响应头。

<h3 id="typesafe_sdk.ListModelsResponse.raw_http_response">
  raw\_http\_response
</h3>

`property`

```python theme={null}
raw_http_response: httpx2.Response
```

底层的 `httpx2.Response`，暴露状态码、请求头与响应体。

<h3 id="typesafe_sdk.ListModelsResponse.model_config">
  model\_config
</h3>

`class-attribute` `instance-attribute`

```python theme={null}
model_config = ConfigDict(
    extra="ignore", frozen=True, strict=True
)
```

<h3 id="typesafe_sdk.ListModelsResponse.models">
  models
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"models"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#tuple">
      {"tuple"}
    </a>
  </span>

  <span className="p">
    {"["}
  </span>

  <span className="n">
    <a href="/sdk/python/api/types/responses#typesafe_sdk.ModelMetadata">
      {"ModelMetadata"}
    </a>
  </span>

  <span className="p">
    {","}
  </span>

  {" "}

  <span className="o">
    {"..."}
  </span>

  <span className="p">
    {"]"}
  </span>

  {"\n"}
</SdkSignature>

可用模型。

<h2 id="typesafe_sdk.ModelMetadata">
  typesafe\_sdk.ModelMetadata
</h2>

`pydantic-model`

基类：`Schema`

描述单个可用模型的元数据。

<Note>
  **显示 JSON schema：**

  <Accordion title="Details" id="sdk-disclosure-7">
    ```json theme={null}
    {
      "description": "Metadata describing a single available model.",
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "description": {
          "title": "Description",
          "type": "string"
        },
        "release_date": {
          "title": "Release Date",
          "type": "string"
        }
      },
      "required": [
        "name",
        "description",
        "release_date"
      ],
      "title": "ModelMetadata",
      "type": "object"
    }
    ```
  </Accordion>
</Note>

字段：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ModelMetadata.name">name</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a></code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ModelMetadata.description">description</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a></code>)
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ModelMetadata.release_date">release\_date</a></code> (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a></code>)

<h3 id="typesafe_sdk.ModelMetadata.name">
  name
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"name"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

请求的 model 字段所接受的模型名称或别名。

<h3 id="typesafe_sdk.ModelMetadata.description">
  description
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"description"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

关于该模型及其能力的人类可读描述。

<h3 id="typesafe_sdk.ModelMetadata.release_date">
  release\_date
</h3>

`pydantic-field`

<SdkSignature>
  <span className="n">
    {"release_date"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/stdtypes.html#str">
      {"str"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

模型发布日期，格式为 YYYY-MM-DD。
