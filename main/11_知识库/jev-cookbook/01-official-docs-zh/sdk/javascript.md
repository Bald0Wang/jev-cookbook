# JavaScript SDK

用于 [TypeSafe AI](https://typesafe.ai) 的 JavaScript 和 TypeScript SDK。

## 快速开始

安装 SDK（需要 Node.js 20 或更新版本）：

```sh theme={null}
npm install @typesafe-ai/sdk
```

在环境中设置 `TYPESAFE_API_KEY`，然后创建并使用客户端：

```ts theme={null}
import { choice, TypeSafeClient } from "@typesafe-ai/sdk";

const client = new TypeSafeClient();
const response = await client.systemOne({
  state: { document: "I was charged twice. Please fix this ASAP." },
  questions: {
    category: choice("What is this ticket about?", {
      billing: null,
      technical: null,
      other: null,
    }),
  },
});

console.log(response.answers.category.choice);
```

答案类型会根据你定义的问题自动推断。该软件包包含 ESM、CommonJS 和 TypeScript 声明文件。

## 文档

在 [TypeSafe 文档](https://docs.typesafe.ai/)中了解 TypeSafe 能做什么。
查看 SDK 的 [client](https://github.com/typesafe-ai/typesafe-sdk-js/blob/v0.6.0/src/client.ts) 和 [types](https://github.com/typesafe-ai/typesafe-sdk-js/blob/v0.6.0/src/types.ts) 了解 API 选项与默认值。
