# Interface: TypeSafeClientConfig

客户端选项。显式指定的值优先于环境变量，环境变量又优先于 SDK 默认值。

## Properties

<a id="sdk-apikey" />

### apiKey?

```ts theme={null}
optional apiKey?: string;
```

必需的 API key；缺省时回退到 `TYPESAFE_API_KEY`。

***

<a id="sdk-baseurl" />

### baseURL?

```ts theme={null}
optional baseURL?: string;
```

API 根地址；缺省时回退到 `TYPESAFE_BASE_URL`，再回退到 `https://api.typesafe.ai`。

***

<a id="sdk-dangerouslyallowbrowser" />

### dangerouslyAllowBrowser?

```ts theme={null}
optional dangerouslyAllowBrowser?: boolean;
```

允许在浏览器中使用，这会把 API key 暴露给页面用户。默认值：false。

***

<a id="sdk-defaultheaders" />

### defaultHeaders?

```ts theme={null}
optional defaultHeaders?: Record<string, string>;
```

附加的请求头；单次调用的请求头优先。

***

<a id="sdk-defaultmodel" />

### defaultModel?

```ts theme={null}
optional defaultModel?: string;
```

默认模型；缺省时回退到 `TYPESAFE_DEFAULT_MODEL`，再回退到 `jev-latest`。

***

<a id="sdk-fetch" />

### fetch?

```ts theme={null}
optional fetch?: Fetch;
```

自定义 HTTP fetch 实现，用于配置传输层或测试。默认值：全局 `fetch`。

***

<a id="sdk-logger" />

### logger?

```ts theme={null}
optional logger?: Logger;
```

日志器，仅输出 `logLevel` 及以上级别的日志。默认值：带前缀的 `console`。

***

<a id="sdk-loglevel" />

### logLevel?

```ts theme={null}
optional logLevel?: LogLevel;
```

日志级别；缺省时回退到 `TYPESAFE_LOG_LEVEL`，再回退到 `warn`。
`info` 会记录请求摘要；`debug` 额外记录请求头和请求体。
已知的凭证类请求头会被脱敏，请求体不会。

***

<a id="sdk-retry" />

### retry?

```ts theme={null}
optional retry?: Partial<RetryPolicy>;
```

重试配置的覆盖项；未指定的字段使用 `RetryPolicy` 中的默认值。

***

<a id="sdk-timeout" />

### timeout?

```ts theme={null}
optional timeout?: number;
```

每次尝试的超时时间（毫秒），不设重试总预算。默认值：10000。
