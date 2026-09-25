# Interface: SystemOneRequest<Q>

用于 `systemOne` 的状态与具名问题。

请求变量上的其他属性会被透传，包括值为 `null` 的属性。

## 被以下内容继承

* [`SystemOneRequestPayload`](/sdk/javascript/api/interfaces/SystemOneRequestPayload)

## Type Parameters

### Q

`Q` *extends* [`Questions`](/sdk/javascript/api/interfaces/Questions) = [`Questions`](/sdk/javascript/api/interfaces/Questions)

## Properties

<a id="sdk-model" />

### model?

```ts theme={null}
optional model?: string;
```

模型覆盖项；缺省时继承 `defaultModel`。

***

<a id="sdk-questions" />

### questions

```ts theme={null}
questions: Q;
```

非空的问题集合，以用于标识其答案的名称作为键。

***

<a id="sdk-state" />

### state

```ts theme={null}
state: EntryType;
```

要评估的文本、JSON 对象或数组，或 `null`。
