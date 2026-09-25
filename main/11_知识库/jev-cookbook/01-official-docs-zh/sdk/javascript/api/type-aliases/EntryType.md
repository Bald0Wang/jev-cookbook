# 类型别名：EntryType

```ts theme={null}
type EntryType = 
  | string
  | {
[key: string]: JsonValue;
}
  | JsonValue[]
  | null;
```

文本、JSON 对象或数组，或 `null`；用于状态、指令和评判标准。
