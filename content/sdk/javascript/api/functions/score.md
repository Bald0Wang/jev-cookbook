# 函数：score()

```ts theme={null}
function score<T>(instructions, criteria): ScoreQuestion<T>;
```

使用有序评分标准创建一个评分问题。

## 类型参数

### T

`T` *extends* [`ScoreCriteria`](/sdk/javascript/api/type-aliases/ScoreCriteria)

## 参数

### instructions

[`EntryType`](/sdk/javascript/api/type-aliases/EntryType)

以文本、JSON 对象或数组形式给出的问题，或 `null`。

### criteria

`T`

至少两个描述，按从零开始的分数索引；条目可以为 `null`。

## 返回

[`ScoreQuestion`](/sdk/javascript/api/interfaces/ScoreQuestion)\<`T`>
