# Interface: ChoiceResponse<T>

所选标签及其各档概率。

## Type Parameters

### T

`T` *extends* [`ChoiceCriteria`](/sdk/javascript/api/type-aliases/ChoiceCriteria) = [`ChoiceCriteria`](/sdk/javascript/api/type-aliases/ChoiceCriteria)

## Properties

<a id="sdk-choice" />

### choice

```ts theme={null}
readonly choice: keyof T & string;
```

所选的标签。

***

<a id="sdk-confidence" />

### confidence

```ts theme={null}
readonly confidence: number;
```

针对所选标签报告的置信度。

***

<a id="sdk-probabilities" />

### probabilities

```ts theme={null}
readonly probabilities: { readonly [label in string | number | symbol]: number };
```

以标签为键的概率。

***

<a id="sdk-type" />

### type

```ts theme={null}
readonly type: "choice";
```
