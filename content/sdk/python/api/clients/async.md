# 异步客户端

> 使用 AsyncTypeSafeClient 提问、列出模型，并配置异步的 TypeSafe API 请求。

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

<a id="asynchronous-client" />

<h2 id="typesafe_sdk.AsyncTypeSafeClient">
  typesafe\_sdk.AsyncTypeSafeClient
</h2>

<SdkSignature>
  <span className="nf">{"AsyncTypeSafeClient"}</span><span className="p">{"("}</span>{"\n"}{"    "}<span className="o">{"*"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"api_key"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"model"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"retry"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="/sdk/python/api/retries#typesafe_sdk.RetryPolicy">{"RetryPolicy"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"timeout"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="n">{"httpx2"}</span><span className="o">{"."}</span><span className="n">{"Timeout"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"headers"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{"]"}</span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"transport"}</span><span className="p">{":"}</span>{" "}<span className="n">{"httpx2"}</span><span className="o">{"."}</span><span className="n">{"AsyncBaseTransport"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"http_client"}</span><span className="p">{":"}</span>{" "}<span className="n">{"httpx2"}</span><span className="o">{"."}</span><span className="n"><a href="https://pydantic.dev/docs/httpx2/api/api/#httpx2.AsyncClient">{"AsyncClient"}</a></span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"base_url"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}<span className="p">{")"}</span>{"\n"}
</SdkSignature>

为 [TypeSafe AI API](https://typesafe.ai) 创建一个异步 HTTP 客户端。

显式选项优先于环境变量；为空或仅含空白字符的环境变量值将被忽略。

<Tip>
  **日志设置**

  SDK 会将日志记录到 `typesafe_sdk` logger；可通过标准 logging 进行配置，或设置 `TYPESAFE_LOG_LEVEL`（`debug`、`info` 等）以快速使用默认配置。敏感请求头会从日志输出中脱敏；请求体与响应体则不会。
</Tip>

参数：

* **`api_key`** (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a> | None</code>, default: `None` ) –

  必需的 API key；可通过 `TYPESAFE_API_KEY` 环境变量设置。会去除首尾空白字符。空 key、中间含空白、控制字符与非 ASCII 字符会被拒绝。
* **`model`** (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a> | None</code>, default: `None` ) –

  模型名称；可通过 `TYPESAFE_DEFAULT_MODEL` 环境变量设置。
* **`retry`** (<code><a href="/sdk/python/api/retries#typesafe_sdk.RetryPolicy">RetryPolicy</a> | None</code>, default: `None` ) –

  控制重试行为的 `RetryPolicy`；可用选项及其默认值见 `RetryPolicy`。传入 `RetryPolicy(max_retries=0)` 可禁用重试。
* **`timeout`** (<code><a href="https://docs.python.org/3/builtins/functions.html#float">float</a> | httpx2.Timeout | None</code>, default: `None` ) –

  HTTP 操作的超时时间。若提供了 `http_client` 则继承其 `http_client.timeout`，否则使用 SDK 默认值。
* **`headers`** (<code><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">Mapping</a>\[<a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>, <a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>] | None</code>, default: `None` ) –

  要设置的额外请求头。
* **`transport`** (`httpx2.AsyncBaseTransport | None`, default: `None` ) –

  可选的自定义 HTTP transport，会在该 SDK 客户端关闭时一并关闭。
* **`http_client`** (<code>httpx2.<a href="https://pydantic.dev/docs/httpx2/api/api/#httpx2.AsyncClient">AsyncClient</a> | None</code>, default: `None` ) –

  可选的 `httpx2.AsyncClient`；与 `transport` 互斥。会在该 SDK 客户端关闭时一并关闭。
* **`base_url`** (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a> | None</code>, default: `None` ) –

  API 根地址；可通过 `TYPESAFE_BASE_URL` 环境变量设置。

引发：

* <code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeError">TypeSafeError</a></code> –

  API key 缺失或无效，或超时设置无效。
* <code><a href="https://docs.python.org/3/builtins/exceptions.html#ValueError">ValueError</a></code> –

  同时提供了 `transport` 和 `http_client`。

示例：

```python theme={null}
import asyncio

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul


async def main() -> None:
    async with AsyncTypeSafeClient() as client:
        result = await client.system_one(
            state="I was charged twice. Please help.",
            questions={
                "billing": Noul(instructions="Is this about billing?"),
                "tone": Choice(
                    instructions="What is the tone?",
                    criteria={"calm": None, "angry": None},
                ),
            },
        )
        assert 0 <= result.nouls["billing"].noul <= 1
        assert result.choices["tone"].choice in {"calm", "angry"}


asyncio.run(main())
```

<h3 id="typesafe_sdk.AsyncTypeSafeClient.models">
  models
</h3>

`cached` `property`

<SdkSignature>
  <span className="n">
    {"models"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="/sdk/python/api/clients/async#typesafe_sdk.AsyncModels">
      {"AsyncModels"}
    </a>
  </span>

  {"\n"}
</SdkSignature>

Models API 资源的访问器。

示例：

```python theme={null}
async def main() -> None:
    async with AsyncTypeSafeClient() as client:
        models = await client.models.list()
```

<h3 id="typesafe_sdk.AsyncTypeSafeClient.system_one">
  system\_one
</h3>

`async`

<Tabs>
  <Tab title="Implementation">
    <SdkSignature>
      <span className="nf">{"system_one"}</span><span className="p">{"("}</span>{"\n"}{"    "}<span className="n">{"state"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="/sdk/python/api/types/common#typesafe_sdk.JSONContent">{"JSONContent"}</a></span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"questions"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="/sdk/python/api/types/questions#typesafe_sdk.Question">{"Question"}</a></span><span className="p">{"],"}</span>{"\n"}{"    "}<span className="o">{"*"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"model"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"retry"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="/sdk/python/api/retries#typesafe_sdk.RetryPolicy">{"RetryPolicy"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"timeout"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="n">{"httpx2"}</span><span className="o">{"."}</span><span className="n">{"Timeout"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"extra_headers"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"extra_body"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="/sdk/python/api/types/common#typesafe_sdk.JSONValue">{"JSONValue"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"response_model"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#type">{"type"}</a></span><span className="p">{"["}</span><span className="n">{"ResponseT"}</span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}<span className="p">{")"}</span>{" "}<span className="o">{"->"}</span>{" "}<span className="n"><a href="/sdk/python/api/types/responses#typesafe_sdk.SystemOneResponse">{"SystemOneResponse"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="n">{"ResponseT"}</span>{"\n"}
    </SdkSignature>
  </Tab>

  <Tab title="Overload 1">
    <SdkSignature>
      <span className="nf">{"system_one"}</span><span className="p">{"("}</span>{"\n"}{"    "}<span className="n">{"state"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="/sdk/python/api/types/common#typesafe_sdk.JSONContent">{"JSONContent"}</a></span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"questions"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="/sdk/python/api/types/questions#typesafe_sdk.Question">{"Question"}</a></span><span className="p">{"],"}</span>{"\n"}{"    "}<span className="o">{"*"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"model"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"retry"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="/sdk/python/api/retries#typesafe_sdk.RetryPolicy">{"RetryPolicy"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"timeout"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="n">{"httpx2"}</span><span className="o">{"."}</span><span className="n">{"Timeout"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"extra_headers"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"extra_body"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="/sdk/python/api/types/common#typesafe_sdk.JSONValue">{"JSONValue"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"response_model"}</span><span className="p">{":"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}<span className="p">{")"}</span>{" "}<span className="o">{"->"}</span>{" "}<span className="n"><a href="/sdk/python/api/types/responses#typesafe_sdk.SystemOneResponse">{"SystemOneResponse"}</a></span>{"\n"}
    </SdkSignature>
  </Tab>

  <Tab title="Overload 2">
    <SdkSignature>
      <span className="nf">{"system_one"}</span><span className="p">{"("}</span>{"\n"}{"    "}<span className="n">{"state"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="/sdk/python/api/types/common#typesafe_sdk.JSONContent">{"JSONContent"}</a></span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"questions"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="/sdk/python/api/types/questions#typesafe_sdk.Question">{"Question"}</a></span><span className="p">{"],"}</span>{"\n"}{"    "}<span className="o">{"*"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"model"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"retry"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="/sdk/python/api/retries#typesafe_sdk.RetryPolicy">{"RetryPolicy"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"timeout"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="n">{"httpx2"}</span><span className="o">{"."}</span><span className="n">{"Timeout"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"extra_headers"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"extra_body"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="/sdk/python/api/types/common#typesafe_sdk.JSONValue">{"JSONValue"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"response_model"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#type">{"type"}</a></span><span className="p">{"["}</span><span className="n">{"ResponseT"}</span><span className="p">{"],"}</span>{"\n"}<span className="p">{")"}</span>{" "}<span className="o">{"->"}</span>{" "}<span className="n">{"ResponseT"}</span>{"\n"}
    </SdkSignature>
  </Tab>
</Tabs>

针对文本或结构化状态回答命名的问题。

详见 [System One](https://docs.typesafe.ai/concepts/system-one)。

参数：

* **`state`** (<code><a href="/sdk/python/api/types/common#typesafe_sdk.JSONContent">JSONContent</a></code>) –

  要评估的文本、JSON 对象或数组。详见[状态](https://docs.typesafe.ai/concepts/state)。
* **`questions`** (<code><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">Mapping</a>\[<a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>, <a href="/sdk/python/api/types/questions#typesafe_sdk.Question">Question</a>]</code>) –

  名称到问题对象或原始字典的非空映射。
* **`model`** (<code><a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a> | None</code>, default: `None` ) –

  覆盖模型；`None` 表示继承客户端默认值。
* **`retry`** (<code><a href="/sdk/python/api/retries#typesafe_sdk.RetryPolicy">RetryPolicy</a> | None</code>, default: `None` ) –

  可选的重试策略，仅在本次调用中覆盖客户端级别的值。
* **`timeout`** (<code><a href="https://docs.python.org/3/builtins/functions.html#float">float</a> | httpx2.Timeout | None</code>, default: `None` ) –

  可选的 HTTP 操作超时时间（秒），仅在本次调用中覆盖客户端级别的值。
* **`extra_headers`** (<code><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">Mapping</a>\[<a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>, <a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>] | None</code>, default: `None` ) –

  要设置的额外请求头。
* **`extra_body`** (<code><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">Mapping</a>\[<a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>, <a href="/sdk/python/api/types/common#typesafe_sdk.JSONValue">JSONValue</a> | None] | None</code>, default: `None` ) –

  额外的顶层请求体字段，会在设置 `state`、`model` 和 `questions` 之后浅合并到请求体上。合并采用后写优先：与 `state`、`model` 或 `questions` 冲突的键会将其覆盖，对象值会被替换而非深度合并。
* **`response_model`** (<code><a href="https://docs.python.org/3/builtins/functions.html#type">type</a>\[ResponseT] | None</code>, default: `None` ) –

  可选的 Pydantic `BaseModel` 类型，用于描述 JSON 响应体，包括所有嵌套的答案模型。

返回：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.SystemOneResponse">SystemOneResponse</a> | ResponseT</code> –

  `response_model` 的实例；或在未提供自定义模型时，返回以问题
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.SystemOneResponse">SystemOneResponse</a> | ResponseT</code> –

  名称为键的答案以及模型与 token 用量信息的 `SystemOneResponse`。

引发：

* <code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeError">TypeSafeError</a></code> –

  问题为空，或 Score 类型问题的标准列表为空。
* <code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code> –

  在所有重试之后，服务器仍返回不成功的 HTTP 响应。
* <code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIConnectionError">TypeSafeAPIConnectionError</a></code> –

  在所有重试之后，请求仍无法连接或超时。
* <code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIResponseValidationError">TypeSafeAPIResponseValidationError</a></code> –

  响应体与响应模型不匹配。

示例：

使用命名参数创建问题：

```python theme={null}
async def main() -> None:
    async with AsyncTypeSafeClient() as client:
        result = await client.system_one(
            state="I was charged twice. Please help.",
            questions={
                "billing": Noul(instructions="Is this about billing?"),
                "tone": Choice(
                    instructions="What is the tone?",
                    criteria={"calm": None, "angry": None},
                ),
            },
        )
        assert 0 <= result.nouls["billing"].noul <= 1
        assert result.choices["tone"].choice in {"calm", "angry"}
```

以字典形式传入问题：

```python theme={null}
async def main() -> None:
    async with AsyncTypeSafeClient() as client:
        result = await client.system_one(
            state={"message": "I was charged twice. Please help."},
            questions={
                "billing": {"type": "noul", "instructions": "Is this about billing?"},
                "tone": {
                    "type": "choice",
                    "instructions": "What is the tone?",
                    "criteria": {"calm": None, "angry": None},
                },
            },
        )
        assert 0 <= result.nouls["billing"].noul <= 1
        assert result.choices["tone"].choice in {"calm", "angry"}
```

<h3 id="typesafe_sdk.AsyncTypeSafeClient.aclose">
  aclose
</h3>

`async`

```python theme={null}
aclose() -> None
```

释放网络资源并关闭底层 HTTP 客户端，包括外部传入的客户端。

<h2 id="models-resource">
  Models 资源
</h2>

通过 [`AsyncTypeSafeClient.models`](/sdk/python/api/clients/async#typesafe_sdk.AsyncTypeSafeClient.models) 访问。

<h3 id="typesafe_sdk.AsyncModels">
  typesafe\_sdk.AsyncModels
</h3>

访问该账户可用的模型，通过 `AsyncTypeSafeClient.models` 进入。

<h4 id="typesafe_sdk.AsyncModels.list">
  list
</h4>

`async`

<SdkSignature>
  <span className="nf">{"list"}</span><span className="p">{"("}</span>{"\n"}{"    "}<span className="o">{"*"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"retry"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="/sdk/python/api/retries#typesafe_sdk.RetryPolicy">{"RetryPolicy"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"timeout"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="n">{"httpx2"}</span><span className="o">{"."}</span><span className="n">{"Timeout"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"extra_headers"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">{"Mapping"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{","}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#str">{"str"}</a></span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}<span className="p">{")"}</span>{" "}<span className="o">{"->"}</span>{" "}<span className="n"><a href="/sdk/python/api/types/responses#typesafe_sdk.ListModelsResponse">{"ListModelsResponse"}</a></span>{"\n"}
</SdkSignature>

列出该账户可用的模型。

参数：

* **`retry`** (<code><a href="/sdk/python/api/retries#typesafe_sdk.RetryPolicy">RetryPolicy</a> | None</code>, default: `None` ) –

  可选的重试策略，仅在本次调用中覆盖客户端级别的值。
* **`timeout`** (<code><a href="https://docs.python.org/3/builtins/functions.html#float">float</a> | httpx2.Timeout | None</code>, default: `None` ) –

  针对单次操作的超时覆盖值；`None` 表示继承客户端设置。
* **`extra_headers`** (<code><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping">Mapping</a>\[<a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>, <a href="https://docs.python.org/3/builtins/stdtypes.html#str">str</a>] | None</code>, default: `None` ) –

  对额外请求头的覆盖；身份认证、SDK 标识与 `Accept` 仍受保护，不可覆盖。

返回：

* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ListModelsResponse">ListModelsResponse</a></code> –

  一个 `ListModelsResponse`，其 `models` 包含每个模型的名称、描述
* <code><a href="/sdk/python/api/types/responses#typesafe_sdk.ListModelsResponse">ListModelsResponse</a></code> –

  以及发布日期。

引发：

* <code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code> –

  在所有重试之后，服务器仍返回不成功的 HTTP 响应。
* <code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIConnectionError">TypeSafeAPIConnectionError</a></code> –

  在所有重试之后，请求仍无法连接或超时。

示例：

```python theme={null}
from typesafe_sdk import AsyncTypeSafeClient


async def main() -> None:
    async with AsyncTypeSafeClient() as client:
        models = await client.models.list()
```
