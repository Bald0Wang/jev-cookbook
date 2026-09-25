# Class: TypeSafeClient

TypeSafe AI API 的客户端。

## 构造函数

<a id="sdk-constructor" />

### Constructor

```ts theme={null}
new TypeSafeClient(config?): TypeSafeClient;
```

创建 TypeSafe AI API 的客户端。

显式选项优先于环境变量，其次才是 SDK 默认值。
为空或仅含空白字符的环境变量值会被忽略。

#### 参数

##### config?

[`TypeSafeClientConfig`](/sdk/javascript/api/interfaces/TypeSafeClientConfig) = `{}`

#### 返回值

`TypeSafeClient`

#### 抛出异常

API 密钥缺失、配置无效，或运行时不受支持时抛出。

## 属性

<a id="sdk-baseurl" />

### baseURL

```ts theme={null}
readonly baseURL: string;
```

移除了尾部斜杠的 API 根地址。

***

<a id="sdk-defaultheaders" />

### defaultHeaders

```ts theme={null}
readonly defaultHeaders: Readonly<Record<string, string>>;
```

随每个请求一起发送的附加请求头。

***

<a id="sdk-defaultmodel" />

### defaultModel

```ts theme={null}
readonly defaultModel: string;
```

当请求省略 `model` 时使用的模型。

***

<a id="sdk-fetch" />

### fetch

```ts theme={null}
readonly fetch: Fetch;
```

HTTP fetch 实现。

***

<a id="sdk-logger" />

### logger

```ts theme={null}
readonly logger: Logger;
```

配置的日志器，按 `logLevel` 过滤。

***

<a id="sdk-loglevel" />

### logLevel

```ts theme={null}
readonly logLevel: LogLevel;
```

配置的日志详细程度。

***

<a id="sdk-models" />

### models

```ts theme={null}
readonly models: Models;
```

该账户可用的模型。

***

<a id="sdk-retry" />

### retry

```ts theme={null}
readonly retry: RetryPolicy;
```

应用了构造函数覆盖项之后的重试设置。

***

<a id="sdk-timeout" />

### timeout

```ts theme={null}
readonly timeout: number;
```

每次尝试的超时时间（毫秒）。

## 方法

<a id="sdk-systemone" />

### systemOne()

```ts theme={null}
systemOne<Q>(request, options?): APIPromise<SystemOneResult<Q>>;
```

针对文本或结构化状态回答具名问题。

#### 类型参数

##### Q

`Q` *extends* [`Questions`](/sdk/javascript/api/interfaces/Questions)

#### 参数

##### request

[`SystemOneRequest`](/sdk/javascript/api/interfaces/SystemOneRequest)\<`Q`>

状态、问题，以及可选的模型覆盖项。

##### options?

[`RequestOptions`](/sdk/javascript/api/interfaces/RequestOptions) = `{}`

每次调用的超时、重试、请求头与取消设置。

#### 返回值

[`APIPromise`](/sdk/javascript/api/classes/APIPromise)\<[`SystemOneResult`](/sdk/javascript/api/interfaces/SystemOneResult)\<`Q`>>

按问题名称与条件给出类型的答案，包含模型与 token 用量。

#### 抛出异常

问题为空，或评分条件不是至少包含两项的列表。

#### 抛出异常

重试后服务器仍返回非 2xx 响应。

#### 抛出异常

重试后请求仍无法连接或超时。

#### 抛出异常

调用方中止了请求。

#### 示例

```ts theme={null}
const { answers } = await client.systemOne({
  state: "I was charged twice. Please help.",
  questions: { billing: noul("Is this about billing?") },
});
console.log(answers.billing.noul);
```
