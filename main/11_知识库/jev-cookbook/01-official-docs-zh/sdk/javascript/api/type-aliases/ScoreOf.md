# 类型别名：ScoreOf<T>

```ts theme={null}
type ScoreOf<T> = number extends T["length"] ? number : Extract<keyof T, `${number}`>;
```

从评分标准推断出的分数键；固定长度的元组会得到其索引，否则为 `number`。

## 类型参数

### T

`T` *extends* [`ScoreCriteria`](/sdk/javascript/api/type-aliases/ScoreCriteria)
