# Interface: NoulQuestion

一个是/否问题，可为两种结果分别提供可选的描述。

## Properties

<a id="sdk-criteria" />

### criteria?

```ts theme={null}
optional criteria?: 
  | {
  false?: EntryType;
  true?: EntryType;
}
  | null;
```

对"是"与"否"两种结果的可选描述。

#### 联合成员

##### Type Literal

```ts theme={null}
{
  false?: EntryType;
  true?: EntryType;
}
```

##### false?

```ts theme={null}
optional false?: EntryType;
```

"否"结果的描述。

##### true?

```ts theme={null}
optional true?: EntryType;
```

"是"结果的描述。

***

`null`

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
type: "noul";
```
