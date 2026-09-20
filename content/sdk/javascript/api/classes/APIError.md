# Class: APIError

API 返回的不成功 HTTP 响应。

## 继承自

* [`TypeSafeError`](/sdk/javascript/api/classes/TypeSafeError)

## 被以下内容继承

* [`AuthenticationError`](/sdk/javascript/api/classes/AuthenticationError)
* [`BadRequestError`](/sdk/javascript/api/classes/BadRequestError)
* [`InternalServerError`](/sdk/javascript/api/classes/InternalServerError)
* [`NotFoundError`](/sdk/javascript/api/classes/NotFoundError)
* [`PermissionDeniedError`](/sdk/javascript/api/classes/PermissionDeniedError)
* [`RateLimitError`](/sdk/javascript/api/classes/RateLimitError)
* [`UnprocessableEntityError`](/sdk/javascript/api/classes/UnprocessableEntityError)

## 构造函数

<a id="sdk-constructor" />

### 构造函数

```ts theme={null}
new APIError(
   status, 
   body, 
   headers, 
   message?
): APIError;
```

#### 参数

##### status

`number`

##### body

`unknown`

##### headers

`Headers`

##### message?

`string`

#### 返回

`APIError`

#### 覆盖

[`TypeSafeError`](/sdk/javascript/api/classes/TypeSafeError).[`constructor`](/sdk/javascript/api/classes/TypeSafeError#sdk-constructor)

## Properties

<a id="sdk-body" />

### body

```ts theme={null}
readonly body: unknown;
```

解析后的 JSON、响应文本，或请求体为空时的 `undefined`。

***

<a id="sdk-headers" />

### headers

```ts theme={null}
readonly headers: Headers;
```

HTTP 响应头。

***

<a id="sdk-requestid" />

### requestId

```ts theme={null}
readonly requestId: string | undefined;
```

来自 `x-typesafe-request-id` 的请求 ID，缺失时为 `undefined`。

***

<a id="sdk-status" />

### status

```ts theme={null}
readonly status: number;
```

HTTP 响应状态码。

## Methods

<a id="sdk-fromresponse" />

### fromResponse()

```ts theme={null}
static fromResponse(
   status, 
   body, 
   headers
): APIError;
```

根据 HTTP 状态码创建对应的错误子类。

#### 参数

##### status

`number`

##### body

`unknown`

##### headers

`Headers`

#### 返回

`APIError`
