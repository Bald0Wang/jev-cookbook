# Interface: Logger

接受一条消息和结构化参数的日志方法；与 `console` 兼容。

## Methods

<a id="sdk-debug" />

### debug()

```ts theme={null}
debug(message, ...args): void;
```

#### 参数

##### message

`string`

##### args

...`unknown`\[]

#### 返回

`void`

***

<a id="sdk-error" />

### error()

```ts theme={null}
error(message, ...args): void;
```

#### 参数

##### message

`string`

##### args

...`unknown`\[]

#### 返回

`void`

***

<a id="sdk-info" />

### info()

```ts theme={null}
info(message, ...args): void;
```

#### 参数

##### message

`string`

##### args

...`unknown`\[]

#### 返回

`void`

***

<a id="sdk-warn" />

### warn()

```ts theme={null}
warn(message, ...args): void;
```

#### 参数

##### message

`string`

##### args

...`unknown`\[]

#### 返回

`void`
