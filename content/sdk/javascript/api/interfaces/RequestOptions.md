# Interface: RequestOptions

覆盖客户端设置的单次调用选项。

## Properties

<a id="sdk-headers" />

### headers?

```ts theme={null}
optional headers?: Record<string, string>;
```

附加的请求头，合并到 `defaultHeaders` 之上。

***

<a id="sdk-retry" />

### retry?

```ts theme={null}
optional retry?: Partial<RetryPolicy>;
```

本次调用的重试覆盖项；未指定的字段继承客户端设置。

***

<a id="sdk-signal" />

### signal?

```ts theme={null}
optional signal?: AbortSignal;
```

用于取消请求及待执行重试的取消信号。

***

<a id="sdk-timeout" />

### timeout?

```ts theme={null}
optional timeout?: number;
```

每次尝试的超时时间（毫秒）；不设重试总预算。
