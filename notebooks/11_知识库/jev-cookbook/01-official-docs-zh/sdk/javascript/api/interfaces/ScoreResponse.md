# Interface: ScoreResponse<T>

带评分标准和各档概率的预期分数。

## Type Parameters

### T

`T` *extends* [`ScoreCriteria`](/sdk/javascript/api/type-aliases/ScoreCriteria) = [`ScoreCriteria`](/sdk/javascript/api/type-aliases/ScoreCriteria)

## Properties

<a id="sdk-confidence" />

### confidence

```ts theme={null}
readonly confidence: number;
```

针对该分数报告的置信度。

***

<a id="sdk-legend" />

### legend

```ts theme={null}
readonly legend: ScoreLegend<T>;
```

以分数为键的评分标准说明。

***

<a id="sdk-probabilities" />

### probabilities

```ts theme={null}
readonly probabilities: { readonly [score in number | `${number}`]: number };
```

以分数为键的概率。

***

<a id="sdk-score" />

### score

```ts theme={null}
readonly score: number;
```

预期分数，可能落在整数评分档位之间。

***

<a id="sdk-type" />

### type

```ts theme={null}
readonly type: "score";
```
