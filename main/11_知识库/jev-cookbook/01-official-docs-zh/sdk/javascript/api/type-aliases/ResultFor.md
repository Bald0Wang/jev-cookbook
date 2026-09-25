# 类型别名：ResultFor<T>

```ts theme={null}
type ResultFor<T> = T extends NoulQuestion ? NoulResponse : T extends ScoreQuestion<infer S> ? ScoreResponse<S> : T extends ChoiceQuestion<infer E> ? ChoiceResponse<E> : never;
```

问题对应的答案类型，保留其评判标准的键。

## 类型参数

### T

`T` *extends* [`Question`](/sdk/javascript/api/type-aliases/Question)
