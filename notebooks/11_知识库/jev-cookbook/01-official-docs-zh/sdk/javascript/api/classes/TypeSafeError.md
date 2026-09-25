# 类：TypeSafeError

SDK 错误的基类。

## 继承自

* `Error`

## 被以下类继承

* [`APIConnectionError`](/sdk/javascript/api/classes/APIConnectionError)
* [`APIError`](/sdk/javascript/api/classes/APIError)
* [`APIUserAbortError`](/sdk/javascript/api/classes/APIUserAbortError)

## 构造函数

<a id="sdk-constructor" />

### 构造函数

```ts theme={null}
new TypeSafeError(message, options?): TypeSafeError;
```

#### 参数

##### message

`string`

##### options?

`ErrorOptions`

#### 返回

`TypeSafeError`

#### 重写

```ts theme={null}
Error.constructor
```
