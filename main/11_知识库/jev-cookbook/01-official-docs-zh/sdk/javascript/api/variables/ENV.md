# Variable: ENV

```ts theme={null}
const ENV: object;
```

用于客户端配置的环境变量名称。显式选项优先。

## Type Declaration

<a id="sdk-apikey" />

### apiKey

```ts theme={null}
readonly apiKey: "TYPESAFE_API_KEY" = "TYPESAFE_API_KEY";
```

必需的 API key；在省略 `apiKey` 时使用。

<a id="sdk-baseurl" />

### baseURL

```ts theme={null}
readonly baseURL: "TYPESAFE_BASE_URL" = "TYPESAFE_BASE_URL";
```

API 根地址；默认为 `https://api.typesafe.ai`。

<a id="sdk-defaultmodel" />

### defaultModel

```ts theme={null}
readonly defaultModel: "TYPESAFE_DEFAULT_MODEL" = "TYPESAFE_DEFAULT_MODEL";
```

默认模型名称；默认为 `jev-latest`。

<a id="sdk-loglevel" />

### logLevel

```ts theme={null}
readonly logLevel: "TYPESAFE_LOG_LEVEL" = "TYPESAFE_LOG_LEVEL";
```

日志级别；默认为 `warn`。
