# Interface: RetryPolicy

重试配置。部分覆盖项中未设置的字段继承自客户端或 SDK 默认值。

## Properties

<a id="sdk-apiconnectionerror" />

### apiConnectionError

```ts theme={null}
readonly apiConnectionError: boolean;
```

是否重试连接失败，包括响应体中断的情况（`APIConnectionError`）。默认值：true。

***

<a id="sdk-apitimeouterror" />

### apiTimeoutError

```ts theme={null}
readonly apiTimeoutError: boolean;
```

是否重试 `APITimeoutError`。默认值：true。

***

<a id="sdk-backoffinitialms" />

### backoffInitialMs

```ts theme={null}
readonly backoffInitialMs: number;
```

首次退避延迟（毫秒），之后逐次加倍直至 `backoffMaxMs`。默认值：500。

***

<a id="sdk-backoffjitter" />

### backoffJitter

```ts theme={null}
readonly backoffJitter: number;
```

每次退避延迟中随机减去的比例，取值 0 到 1。默认值：0.25。

***

<a id="sdk-backoffmaxms" />

### backoffMaxMs

```ts theme={null}
readonly backoffMaxMs: number;
```

最大退避延迟（毫秒）。默认值：5000。

***

<a id="sdk-httpstatuses" />

### httpStatuses

```ts theme={null}
readonly httpStatuses: ReadonlySet<number>;
```

需要重试的 HTTP 状态码。默认值：408、429 和 500–599。

***

<a id="sdk-maxretries" />

### maxRetries

```ts theme={null}
readonly maxRetries: number;
```

首次尝试之后的最大重试次数；`0` 表示禁用重试。默认值：2。

***

<a id="sdk-maxretryafterms" />

### maxRetryAfterMs

```ts theme={null}
readonly maxRetryAfterMs: number;
```

服务器要求的重试延迟上限（毫秒）；超过此上限时改用退避。默认值：60000。

***

<a id="sdk-respectretryafter" />

### respectRetryAfter

```ts theme={null}
readonly respectRetryAfter: boolean;
```

遵循 `Retry-After` 和 `retry-after-ms`，上限为 `maxRetryAfterMs`。默认值：true。
