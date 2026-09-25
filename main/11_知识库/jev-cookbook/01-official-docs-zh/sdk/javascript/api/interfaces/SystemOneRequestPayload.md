# Interface: SystemOneRequestPayload

`POST /v1/systemone` 的请求体，其中模型已解析确定。

## 继承自

* [`SystemOneRequest`](/sdk/javascript/api/interfaces/SystemOneRequest)

## Properties

<a id="sdk-model" />

### model

```ts theme={null}
model: string;
```

模型覆盖项；缺省时继承 `defaultModel`。

#### 覆盖

[`SystemOneRequest`](/sdk/javascript/api/interfaces/SystemOneRequest).[`model`](/sdk/javascript/api/interfaces/SystemOneRequest#sdk-model)

***

<a id="sdk-questions" />

### questions

```ts theme={null}
questions: Questions;
```

非空的问题集合，以用于标识其答案的名称作为键。

#### 继承自

[`SystemOneRequest`](/sdk/javascript/api/interfaces/SystemOneRequest).[`questions`](/sdk/javascript/api/interfaces/SystemOneRequest#sdk-questions)

***

<a id="sdk-state" />

### state

```ts theme={null}
state: EntryType;
```

要评估的文本、JSON 对象或数组，或 `null`。

#### 继承自

[`SystemOneRequest`](/sdk/javascript/api/interfaces/SystemOneRequest).[`state`](/sdk/javascript/api/interfaces/SystemOneRequest#sdk-state)
