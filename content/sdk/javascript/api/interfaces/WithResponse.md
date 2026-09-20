# 接口：WithResponse<T>

解析后的数据及其 HTTP 响应与请求 ID。

## 类型参数

### T

`T`

## 属性

<a id="sdk-data" />

### data

```ts theme={null}
data: T;
```

已解析的响应体。

***

<a id="sdk-requestid" />

### requestId

```ts theme={null}
requestId: string | undefined;
```

来自 `x-typesafe-request-id` 的请求 ID，不存在时为 `undefined`。

***

<a id="sdk-response" />

### response

```ts theme={null}
response: Response;
```

HTTP 响应，其响应体已在解析时被读取。
