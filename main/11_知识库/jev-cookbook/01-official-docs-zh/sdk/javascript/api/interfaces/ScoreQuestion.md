# Interface: ScoreQuestion<T>

使用有序评分标准给出分数的问题。

## Type Parameters

### T

`T` *extends* [`ScoreCriteria`](/sdk/javascript/api/type-aliases/ScoreCriteria) = [`ScoreCriteria`](/sdk/javascript/api/type-aliases/ScoreCriteria)

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
type: "score";
```
