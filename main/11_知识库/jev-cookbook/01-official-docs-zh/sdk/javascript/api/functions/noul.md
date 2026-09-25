# Function: noul()

```ts theme={null}
function noul(instructions?, criteria?): NoulQuestion;
```

创建一个是/否问题，可为两种结果分别提供可选的描述。

## 参数

### instructions?

[`EntryType`](/sdk/javascript/api/type-aliases/EntryType) = `null`

作为问题的文本、JSON 对象或数组；默认为 `null`。

### criteria?

\| \{
`false?`: [`EntryType`](/sdk/javascript/api/type-aliases/EntryType);
`true?`: [`EntryType`](/sdk/javascript/api/type-aliases/EntryType);
}
\| `null`

对"是"与"否"两种结果的可选描述。

#### Type Literal

\{
`false?`: [`EntryType`](/sdk/javascript/api/type-aliases/EntryType);
`true?`: [`EntryType`](/sdk/javascript/api/type-aliases/EntryType);
}

对"是"与"否"两种结果的可选描述。

##### false?

[`EntryType`](/sdk/javascript/api/type-aliases/EntryType)

"否"结果的描述。

##### true?

[`EntryType`](/sdk/javascript/api/type-aliases/EntryType)

"是"结果的描述。

***

`null`

## 返回

[`NoulQuestion`](/sdk/javascript/api/interfaces/NoulQuestion)
