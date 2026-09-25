# Class: APIPromise<T>

一个携带 HTTP 响应访问能力的解析结果 Promise。

非 2xx 响应会以 `APIError` 拒绝，包括通过 `asResponse()` 的情况。

## 继承

* `Promise`\<`T`>

## 类型参数

### T

`T`

## 构造函数

<a id="sdk-constructor" />

### Constructor

```ts theme={null}
new APIPromise<T>(responsePromise, parseResponse): APIPromise<T>;
```

#### 参数

##### responsePromise

`Promise`\<`Response`>

##### parseResponse

(`response`) => `Promise`\<`T`>

#### 返回值

`APIPromise`\<`T`>

#### 重写

```ts theme={null}
Promise<T>.constructor
```

## 方法

<a id="sdk-asresponse" />

### asResponse()

```ts theme={null}
asResponse(): Promise<Response>;
```

解析为未经处理的原始 `Response`，不解析响应体。SDK 请求会在请求超时之内缓冲完整响应体后再进行交接；之后的读取由调用方负责。响应体归调用方所有；不要在同一个 Promise 上同时 `await` 解析结果。

#### 返回值

`Promise`\<`Response`>

***

<a id="sdk-catch" />

### catch()

```ts theme={null}
catch<TResult>(onrejected?): Promise<T | TResult>;
```

仅为 Promise 被拒绝的情况附加一个回调。

#### 类型参数

##### TResult

`TResult` = `never`

#### 参数

##### onrejected?

((`reason`) => `TResult` | `PromiseLike`\<`TResult`>) | `null`

当 Promise 被拒绝时执行的回调。

#### 返回值

`Promise`\<`T` | `TResult`>

表示回调完成的 Promise。

#### 重写

```ts theme={null}
Promise.catch
```

***

<a id="sdk-finally" />

### finally()

```ts theme={null}
finally(onfinally?): Promise<T>;
```

附加一个在 Promise 落定（fulfilled 或 rejected）时被调用的回调。已解析的值无法在该回调中修改。

#### 参数

##### onfinally?

(() => `void`) | `null`

当 Promise 落定（fulfilled 或 rejected）时执行的回调。

#### 返回值

`Promise`\<`T`>

表示回调完成的 Promise。

#### 重写

```ts theme={null}
Promise.finally
```

***

<a id="sdk-map" />

### map()

```ts theme={null}
map<U>(fn): APIPromise<U>;
```

转换解析后的结果，共享 HTTP 响应和一次性的响应体解析。

#### 类型参数

##### U

`U`

#### 参数

##### fn

(`data`) => `U`

#### 返回值

`APIPromise`\<`U`>

***

<a id="sdk-then" />

### then()

```ts theme={null}
then<TResult1, TResult2>(onfulfilled?, onrejected?): Promise<TResult1 | TResult2>;
```

为 Promise 的完成和/或拒绝附加回调。

#### 类型参数

##### TResult1

`TResult1` = `T`

##### TResult2

`TResult2` = `never`

#### 参数

##### onfulfilled?

((`value`) => `TResult1` | `PromiseLike`\<`TResult1`>) | `null`

当 Promise 完成时执行的回调。

##### onrejected?

((`reason`) => `TResult2` | `PromiseLike`\<`TResult2`>) | `null`

当 Promise 被拒绝时执行的回调。

#### 返回值

`Promise`\<`TResult1` | `TResult2`>

表示所执行的回调（无论哪一个）完成的 Promise。

#### 重写

```ts theme={null}
Promise.then
```

***

<a id="sdk-withresponse" />

### withResponse()

```ts theme={null}
withResponse(): Promise<WithResponse<T>>;
```

返回解析结果、HTTP 响应和请求 ID。

#### 返回值

`Promise`\<[`WithResponse`](/sdk/javascript/api/interfaces/WithResponse)\<`T`>>
