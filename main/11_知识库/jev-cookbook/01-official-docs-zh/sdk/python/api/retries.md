# 重试

> 使用 RetryPolicy 配置重试——尝试次数、可重试状态码、退避以及重试相关响应头的处理。

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

<a id="retries" />

<h2 id="typesafe_sdk.RetryPolicy">
  typesafe\_sdk.RetryPolicy
</h2>

`dataclass`

<SdkSignature>
  <span className="nf">{"RetryPolicy"}</span><span className="p">{"("}</span>{"\n"}{"    "}<span className="n">{"max_retries"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#int">{"int"}</a></span>{" "}<span className="o">{"="}</span>{" "}<span className="mi">{"2"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"backoff_initial"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{" "}<span className="o">{"="}</span>{" "}<span className="mf">{"0.5"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"backoff_max"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{" "}<span className="o">{"="}</span>{" "}<span className="mf">{"5.0"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"backoff_jitter"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{" "}<span className="o">{"="}</span>{" "}<span className="mf">{"0.25"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"http_statuses"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#set">{"set"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/functions.html#int">{"int"}</a></span><span className="p">{"]"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="p">{"("}</span>{"\n"}{"        "}<span className="k">{"lambda"}</span><span className="p">{":"}</span>{" "}<span className="p">{"{"}</span><span className="mi">{"408"}</span><span className="p">{","}</span>{" "}<span className="mi">{"429"}</span><span className="p">{","}</span>{" "}<span className="o">{"*"}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#range">{"range"}</a></span><span className="p">{"("}</span><span className="mi">{"500"}</span><span className="p">{","}</span>{" "}<span className="mi">{"600"}</span><span className="p">{")}"}</span>{"\n"}{"    "}<span className="p">{")(),"}</span>{"\n"}{"    "}<span className="n">{"respect_retry_after"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#bool">{"bool"}</a></span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"True"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"api_connection_error"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#bool">{"bool"}</a></span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"True"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"api_timeout_error"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#bool">{"bool"}</a></span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"True"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"exceptions"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#set">{"set"}</a></span><span className="p">{"["}</span>{"\n"}{"        "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#type">{"type"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/exceptions.html#BaseException">{"BaseException"}</a></span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="p">{"]"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#set">{"set"}</a></span><span className="p">{"(),"}</span>{"\n"}{"    "}<span className="n">{"predicate"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable">{"Callable"}</a></span><span className="p">{"[["}</span><span className="n"><a href="https://docs.python.org/3/builtins/exceptions.html#BaseException">{"BaseException"}</a></span><span className="p">{"],"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#bool">{"bool"}</a></span><span className="p">{"]"}</span>{"\n"}{"    "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="n">{"timeout"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#float">{"float"}</a></span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="mf">{"30.0"}</span><span className="p">{","}</span>{"\n"}<span className="p">{")"}</span>{"\n"}
</SdkSignature>

SDK 重试行为的配置。

示例：

```python theme={null}
from typesafe_sdk import RetryPolicy, TypeSafeClient

client = TypeSafeClient(
    retry=RetryPolicy(
        max_retries=3, timeout=10.0, http_statuses={429, 500, 502, 503, 504}
    )
)
```

<h3 id="typesafe_sdk.RetryPolicy.max_retries">
  max\_retries
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">
    {"max_retries"}
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
    {"="}
  </span>

  {" "}

  <span className="mi">
    {"2"}
  </span>

  {"\n"}
</SdkSignature>

首次尝试之后的最大重试次数；`0` 表示禁用重试。

<h3 id="typesafe_sdk.RetryPolicy.backoff_initial">
  backoff\_initial
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">
    {"backoff_initial"}
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

  {" "}

  <span className="o">
    {"="}
  </span>

  {" "}

  <span className="mf">
    {"0.5"}
  </span>

  {"\n"}
</SdkSignature>

首次退避延迟（秒），每次尝试后加倍，直至 `backoff_max`；为零则禁用退避。

<h3 id="typesafe_sdk.RetryPolicy.backoff_max">
  backoff\_max
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">
    {"backoff_max"}
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

  {" "}

  <span className="o">
    {"="}
  </span>

  {" "}

  <span className="mf">
    {"5.0"}
  </span>

  {"\n"}
</SdkSignature>

最大退避延迟（秒）；为零则禁用退避。

<h3 id="typesafe_sdk.RetryPolicy.backoff_jitter">
  backoff\_jitter
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">
    {"backoff_jitter"}
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

  {" "}

  <span className="o">
    {"="}
  </span>

  {" "}

  <span className="mf">
    {"0.25"}
  </span>

  {"\n"}
</SdkSignature>

从每次退避延迟中随机减去的比例，取值介于 0 与 1 之间。

<h3 id="typesafe_sdk.RetryPolicy.http_statuses">
  http\_statuses
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">{"http_statuses"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#set">{"set"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/functions.html#int">{"int"}</a></span><span className="p">{"]"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/dataclasses.html#dataclasses.field">{"field"}</a></span><span className="p">{"("}</span>{"\n"}{"    "}<span className="n">{"default_factory"}</span><span className="o">{"="}</span><span className="k">{"lambda"}</span><span className="p">{":"}</span>{" "}<span className="p">{"{"}</span>{"\n"}{"        "}<span className="mi">{"408"}</span><span className="p">{","}</span>{"\n"}{"        "}<span className="mi">{"429"}</span><span className="p">{","}</span>{"\n"}{"        "}<span className="o">{"*"}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#range">{"range"}</a></span><span className="p">{"("}</span><span className="mi">{"500"}</span><span className="p">{","}</span>{" "}<span className="mi">{"600"}</span><span className="p">{"),"}</span>{"\n"}{"    "}<span className="p">{"}"}</span>{"\n"}<span className="p">{")"}</span>{"\n"}
</SdkSignature>

会被重试的 HTTP 状态码。

<h3 id="typesafe_sdk.RetryPolicy.respect_retry_after">
  respect\_retry\_after
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">
    {"respect_retry_after"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#bool">
      {"bool"}
    </a>
  </span>

  {" "}

  <span className="o">
    {"="}
  </span>

  {" "}

  <span className="kc">
    {"True"}
  </span>

  {"\n"}
</SdkSignature>

是否遵循 `Retry-After` 和 `retry-after-ms` 响应头。

<h3 id="typesafe_sdk.RetryPolicy.api_connection_error">
  api\_connection\_error
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">
    {"api_connection_error"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#bool">
      {"bool"}
    </a>
  </span>

  {" "}

  <span className="o">
    {"="}
  </span>

  {" "}

  <span className="kc">
    {"True"}
  </span>

  {"\n"}
</SdkSignature>

是否重试 `TypeSafeAPIConnectionError`；当请求无法连接服务器或无法从服务器读取时抛出该异常。

<h3 id="typesafe_sdk.RetryPolicy.api_timeout_error">
  api\_timeout\_error
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">
    {"api_timeout_error"}
  </span>

  <span className="p">
    {":"}
  </span>

  {" "}

  <span className="n">
    <a href="https://docs.python.org/3/builtins/functions.html#bool">
      {"bool"}
    </a>
  </span>

  {" "}

  <span className="o">
    {"="}
  </span>

  {" "}

  <span className="kc">
    {"True"}
  </span>

  {"\n"}
</SdkSignature>

是否重试 `TypeSafeAPITimeoutError`；当请求超过其超时时间时抛出该异常。

<h3 id="typesafe_sdk.RetryPolicy.exceptions">
  exceptions
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">{"exceptions"}</span><span className="p">{":"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#set">{"set"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/functions.html#type">{"type"}</a></span><span className="p">{"["}</span><span className="n"><a href="https://docs.python.org/3/builtins/exceptions.html#BaseException">{"BaseException"}</a></span><span className="p">{"]]"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="n"><a href="https://docs.python.org/3/library/dataclasses.html#dataclasses.field">{"field"}</a></span><span className="p">{"("}</span>{"\n"}{"    "}<span className="n">{"default_factory"}</span><span className="o">{"="}</span><span className="n"><a href="https://docs.python.org/3/builtins/stdtypes.html#set">{"set"}</a></span>{"\n"}<span className="p">{")"}</span>{"\n"}
</SdkSignature>

在内置规则之外，额外触发重试的异常类型。

<h3 id="typesafe_sdk.RetryPolicy.predicate">
  predicate
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">{"predicate"}</span><span className="p">{":"}</span>{" "}<span className="p">{"("}</span>{"\n"}{"    "}<span className="n"><a href="https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable">{"Callable"}</a></span><span className="p">{"[["}</span><span className="n"><a href="https://docs.python.org/3/builtins/exceptions.html#BaseException">{"BaseException"}</a></span><span className="p">{"],"}</span>{" "}<span className="n"><a href="https://docs.python.org/3/builtins/functions.html#bool">{"bool"}</a></span><span className="p">{"]"}</span>{" "}<span className="o">{"|"}</span>{" "}<span className="kc">{"None"}</span>{"\n"}<span className="p">{")"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="kc">{"None"}</span>{"\n"}
</SdkSignature>

可选的谓词函数，会以抛出的异常为参数被调用；除其他规则之外，返回 `True` 会触发重试。

<h3 id="typesafe_sdk.RetryPolicy.timeout">
  timeout
</h3>

`class-attribute` `instance-attribute`

<SdkSignature>
  <span className="n">
    {"timeout"}
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

  <span className="mf">
    {"30.0"}
  </span>

  {"\n"}
</SdkSignature>

每次 SDK 调用的总重试预算（秒），包括首次尝试和延迟时间；`None` 表示不设限制。

若某次重试的延迟将达到或超出预算，则在该重试开始前停止，并重新抛出最后一个错误。
