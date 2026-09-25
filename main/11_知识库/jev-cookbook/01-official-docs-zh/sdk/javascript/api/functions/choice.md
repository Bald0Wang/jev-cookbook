# 函数：choice()

```ts theme={null}
function choice<T>(instructions, criteria): ChoiceQuestion<T>;
```

创建一个在命名选项之间进行选择的问题。

## 类型参数

### T

`T` *extends* [`ChoiceCriteria`](/sdk/javascript/api/type-aliases/ChoiceCriteria)

## 参数

### instructions

[`EntryType`](/sdk/javascript/api/type-aliases/EntryType)

以文本、JSON 对象或数组形式给出的问题，或 `null`。

### criteria

`T`

标签到描述的映射，`null` 表示标签没有描述。

## 返回

[`ChoiceQuestion`](/sdk/javascript/api/interfaces/ChoiceQuestion)\<`T`>
