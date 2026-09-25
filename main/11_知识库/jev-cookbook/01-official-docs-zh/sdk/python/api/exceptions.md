# 异常

> 处理 TypeSafe API 错误、速率限制、连接失败与超时。

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

<a id="exceptions" />

<h2 id="base-exception">
  基础异常
</h2>

<h2 id="typesafe_sdk.TypeSafeError">
  typesafe\_sdk.TypeSafeError
</h2>

基类：<code><a href="https://docs.python.org/3/builtins/exceptions.html#Exception">Exception</a></code>

SDK 失败时抛出的基础异常。

<h2 id="http-errors">
  HTTP 错误
</h2>

<h2 id="typesafe_sdk.TypeSafeAPIError">
  typesafe\_sdk.TypeSafeAPIError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeError">TypeSafeError</a></code>

带有响应体与请求元数据的未成功 HTTP 响应。

<h3 id="typesafe_sdk.TypeSafeAPIError.status">
  status
</h3>

`instance-attribute`

```python theme={null}
status = status
```

HTTP 响应状态码。

<h3 id="typesafe_sdk.TypeSafeAPIError.body">
  body
</h3>

`instance-attribute`

```python theme={null}
body = body
```

服务器的 JSON 错误体或纯文本响应内容；响应体为空时则为 `None`。

<h3 id="typesafe_sdk.TypeSafeAPIError.headers">
  headers
</h3>

`instance-attribute`

```python theme={null}
headers = headers
```

HTTP 响应头。

<h3 id="typesafe_sdk.TypeSafeAPIError.endpoint">
  endpoint
</h3>

`instance-attribute`

```python theme={null}
endpoint = endpoint
```

可用时为请求的方法与 URL，不包含凭据、查询参数或片段。

<h3 id="typesafe_sdk.TypeSafeAPIError.request_id">
  request\_id
</h3>

`property`

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

  {" "}

  <span className="o">
    {"|"}
  </span>

  {" "}

  <span className="kc">
    {"None"}
  </span>

  {"\n"}
</SdkSignature>

响应头 `x-typesafe-request-id` 的值，缺失时为 `None`。

<h2 id="typesafe_sdk.TypeSafeBadRequestError">
  typesafe\_sdk.TypeSafeBadRequestError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code>

请求无效（400）。

<h2 id="typesafe_sdk.TypeSafeAuthenticationError">
  typesafe\_sdk.TypeSafeAuthenticationError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code>

身份验证失败（401）。

<h2 id="typesafe_sdk.TypeSafePermissionDeniedError">
  typesafe\_sdk.TypeSafePermissionDeniedError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code>

访问被拒绝（403）。

<h2 id="typesafe_sdk.TypeSafeNotFoundError">
  typesafe\_sdk.TypeSafeNotFoundError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code>

未找到资源（404）。

<h2 id="typesafe_sdk.TypeSafeUnprocessableEntityError">
  typesafe\_sdk.TypeSafeUnprocessableEntityError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code>

请求未通过服务器校验（422）。

<h2 id="typesafe_sdk.TypeSafeRateLimitError">
  typesafe\_sdk.TypeSafeRateLimitError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code>

超出速率限制（429）。

<h3 id="typesafe_sdk.TypeSafeRateLimitError.retry_after_ms">
  retry\_after\_ms
</h3>

`instance-attribute`

```python theme={null}
retry_after_ms = parse_retry_after(headers)
```

服务器要求的等待时间（毫秒）；不可用时则为 `None`。

<h2 id="typesafe_sdk.TypeSafeInternalServerError">
  typesafe\_sdk.TypeSafeInternalServerError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code>

服务器处理请求失败（5xx）。

<h2 id="connection-errors">
  连接错误
</h2>

<h2 id="typesafe_sdk.TypeSafeAPIConnectionError">
  typesafe\_sdk.TypeSafeAPIConnectionError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeError">TypeSafeError</a></code>, <code><a href="https://docs.python.org/3/builtins/exceptions.html#ConnectionError">ConnectionError</a></code>

请求失败且未收到 HTTP 响应。

<h2 id="typesafe_sdk.TypeSafeAPITimeoutError">
  typesafe\_sdk.TypeSafeAPITimeoutError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIConnectionError">TypeSafeAPIConnectionError</a></code>, <code><a href="https://docs.python.org/3/builtins/exceptions.html#TimeoutError">TimeoutError</a></code>

请求超出了配置的超时时间。

<h3 id="typesafe_sdk.TypeSafeAPITimeoutError.timeout">
  timeout
</h3>

`instance-attribute`

```python theme={null}
timeout = timeout
```

请求所使用的超时设置，以秒为单位，或为 `httpx2.Timeout`。

<h2 id="response-validation">
  响应校验
</h2>

<h2 id="typesafe_sdk.TypeSafeAPIResponseValidationError">
  typesafe\_sdk.TypeSafeAPIResponseValidationError
</h2>

基类：<code><a href="/sdk/python/api/exceptions#typesafe_sdk.TypeSafeAPIError">TypeSafeAPIError</a></code>

HTTP 响应成功，但其响应体缺失所需数据或所需数据的结构无效。

<h3 id="typesafe_sdk.TypeSafeAPIResponseValidationError.field_path">
  field\_path
</h3>

`instance-attribute`

```python theme={null}
field_path = field_path
```

指向出错字段的点分路径，例如 `answers.tone.confidence`。

<h3 id="typesafe_sdk.TypeSafeAPIResponseValidationError.args">
  args
</h3>

`instance-attribute`

```python theme={null}
args = (
    status,
    body,
    headers,
    field_path,
    endpoint,
)
```
