# 类型别名：ScoreLegend<T>

```ts theme={null}
type ScoreLegend<T> = { readonly [score in ScoreOf<T>]: T[score] };
```

以分数为键的评分标准描述。

## 类型参数

### T

`T` *extends* [`ScoreCriteria`](/sdk/javascript/api/type-aliases/ScoreCriteria)
