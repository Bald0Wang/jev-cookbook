# Class: APITimeoutError

在超时时间内未收到完整响应。是 `APIConnectionError` 的一种。

## 继承自

* [`APIConnectionError`](/sdk/javascript/api/classes/APIConnectionError)

## 构造函数

<a id="sdk-constructor" />

### 构造函数

```ts theme={null}
new APITimeoutError(timeoutMs, options?): APITimeoutError;
```

#### 参数

##### timeoutMs

`number`

##### options?

`ErrorOptions`

#### 返回

`APITimeoutError`

#### 覆盖

[`APIConnectionError`](/sdk/javascript/api/classes/APIConnectionError).[`constructor`](/sdk/javascript/api/classes/APIConnectionError#sdk-constructor)

## Properties

<a id="sdk-timeoutms" />

### timeoutMs

```ts theme={null}
readonly timeoutMs: number;
```

配置的超时时间（毫秒）。
