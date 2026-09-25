# Class: APIUserAbortError

调用方通过 `AbortSignal` 取消了请求。

## 继承自

* [`TypeSafeError`](/sdk/javascript/api/classes/TypeSafeError)

## 构造函数

<a id="sdk-constructor" />

### 构造函数

```ts theme={null}
new APIUserAbortError(message?, options?): APIUserAbortError;
```

#### 参数

##### message?

`string` = `"Request was aborted."`

##### options?

`ErrorOptions`

#### 返回

`APIUserAbortError`

#### 覆盖

[`TypeSafeError`](/sdk/javascript/api/classes/TypeSafeError).[`constructor`](/sdk/javascript/api/classes/TypeSafeError#sdk-constructor)
