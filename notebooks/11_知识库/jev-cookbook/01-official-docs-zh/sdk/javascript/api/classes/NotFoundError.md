# Class: NotFoundError

HTTP 404：未找到资源。

## 继承自

* [`APIError`](/sdk/javascript/api/classes/APIError)

## 构造函数

<a id="sdk-constructor" />

### 构造函数

```ts theme={null}
new NotFoundError(
   status, 
   body, 
   headers, 
   message?
): NotFoundError;
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

`NotFoundError`

#### 继承自

[`APIError`](/sdk/javascript/api/classes/APIError).[`constructor`](/sdk/javascript/api/classes/APIError#sdk-constructor)

## Properties

<a id="sdk-body" />

### body

```ts theme={null}
readonly body: unknown;
```

解析后的 JSON、响应文本，或请求体为空时的 `undefined`。

#### 继承自

[`APIError`](/sdk/javascript/api/classes/APIError).[`body`](/sdk/javascript/api/classes/APIError#sdk-body)

***

<a id="sdk-headers" />

### headers

```ts theme={null}
readonly headers: Headers;
```

HTTP 响应头。

#### 继承自

[`APIError`](/sdk/javascript/api/classes/APIError).[`headers`](/sdk/javascript/api/classes/APIError#sdk-headers)

***

<a id="sdk-requestid" />

### requestId

```ts theme={null}
readonly requestId: string | undefined;
```

来自 `x-typesafe-request-id` 的请求 ID，缺失时为 `undefined`。

#### 继承自

[`APIError`](/sdk/javascript/api/classes/APIError).[`requestId`](/sdk/javascript/api/classes/APIError#sdk-requestid)

***

<a id="sdk-status" />

### status

```ts theme={null}
readonly status: number;
```

HTTP 响应状态码。

#### 继承自

[`APIError`](/sdk/javascript/api/classes/APIError).[`status`](/sdk/javascript/api/classes/APIError#sdk-status)

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

[`APIError`](/sdk/javascript/api/classes/APIError)

#### 继承自

[`APIError`](/sdk/javascript/api/classes/APIError).[`fromResponse`](/sdk/javascript/api/classes/APIError#sdk-fromresponse)
