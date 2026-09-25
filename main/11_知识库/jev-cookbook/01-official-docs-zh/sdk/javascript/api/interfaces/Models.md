# 接口：Models

访问 Models API 资源。

## 方法

<a id="sdk-list" />

### list()

```ts theme={null}
list(options?): APIPromise<ModelCard[]>;
```

列出该账户可用的模型。

#### 参数

##### options?

[`RequestOptions`](/sdk/javascript/api/interfaces/RequestOptions) = `{}`

#### 返回

[`APIPromise`](/sdk/javascript/api/classes/APIPromise)\<[`ModelCard`](/sdk/javascript/api/interfaces/ModelCard)\[]>
