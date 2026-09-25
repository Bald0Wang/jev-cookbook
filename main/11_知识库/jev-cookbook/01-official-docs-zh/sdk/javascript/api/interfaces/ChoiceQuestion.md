# Interface: ChoiceQuestion<T>

在具名选项之间进行选择的问题。

## Type Parameters

### T

`T` *extends* [`ChoiceCriteria`](/sdk/javascript/api/type-aliases/ChoiceCriteria) = [`ChoiceCriteria`](/sdk/javascript/api/type-aliases/ChoiceCriteria)

## Properties

<a id="sdk-criteria" />

### criteria

```ts theme={null}
criteria: T;
```

各个可选结果的描述。

***

<a id="sdk-instructions" />

### instructions?

```ts theme={null}
optional instructions?: EntryType;
```

作为问题的文本、JSON 对象或数组；可省略或为 `null`。

***

<a id="sdk-type" />

### type

```ts theme={null}
type: "choice";
```
