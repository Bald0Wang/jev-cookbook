# Interface: SystemOneResult<Q>

以问题名称为键的答案，附带模型与用量元数据。

## Type Parameters

### Q

`Q` *extends* [`Questions`](/sdk/javascript/api/interfaces/Questions)

## Properties

<a id="sdk-answers" />

### answers

```ts theme={null}
readonly answers: { readonly [K in string | number | symbol]: ResultFor<Q[K]> };
```

答案，其类型根据所提供的问题推断。

***

<a id="sdk-model" />

### model

```ts theme={null}
readonly model: string;
```

用于回答该请求的模型。

***

<a id="sdk-usage" />

### usage

```ts theme={null}
readonly usage: Usage;
```

该请求的 token 用量。
