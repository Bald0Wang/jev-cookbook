# Models

Jev 是 TypeSafe 的旗舰模型，也是首个 [System One 模型](/concepts/system-one)。本页上的每个模型都由同一个端点 `POST /v1/systemone` 提供服务。请求的 `model` 字段选择由哪个模型处理调用；完整的请求结构参见 [API 参考](/api)。

## 当前模型

| Jev 1.13                    | `jev-1.13.0`                                                                              |
| :-------------------------- | :---------------------------------------------------------------------------------------- |
| 价格（每 Btok / 每 Mtok）   | \$42 / \$0.042                                                                            |
| 速率限制                    | 每秒 250,000 token / 每分钟 1,200 个请求                                                  |
| 上下文长度                  | 每个请求 64k token；`state` 加上单个最长的问题为 32k token                                |
| 输入                        | 仅文本。字符串、JSON 对象或文本值数组。不支持图像、音频或视频输入。                       |

* **价格：**按输入 token 计费。输出 token 免费。1 Btok 为十亿 token，1 Mtok 为一百万 token。
* **速率限制：**按每秒 token 数和每分钟请求数计量。超过任一限制的请求会返回 `429 Too Many Requests`。我们的[客户端 SDK](/sdk) 默认以退避方式重试，并在响应携带 `retry-after` 头时遵循它。如果你直接调用 HTTP API，参见[处理速率限制](/api#handling-rate-limits)。
* **上下文长度：**Jev 只读取一次 `state`，并针对它并行评估每个问题。64k 预算涵盖 `state` 加上所有问题的总和；32k 预算适用于 `state` 加上单个最长的问题。把多个问题打包进一个请求参见[推测式扇出](/patterns/fan-out)；随着 state 增大准确率如何变化参见 [Jev 1.13 的参差之处](/model-jaggedness/jev-1.13)。
* **输入：**Jev 评估自然语言文本。在把非文本输入（图像、音频、视频、二进制）作为 `state` 发送之前，先将其预处理为文本或结构化字段。支持的形态参见 [State](/concepts/state)。

<Warning>
  **速率限制正在动态调整。**我们正在服务非常大量的需求，在即将落地的大型 GPU 采购到位、更多用户加入的过程中，上述限制可能随时更改而不另行通知。等局面更加稳定后，我们将能提供更稳定的限制。自定义版和企业版可提供更高的限制。联系 [sales@typesafe.ai](mailto:sales@typesafe.ai)。
</Warning>

## 别名

别名是解析为带版本号模型 ID 的模型名称。像其他名称一样把它填入 `model` 字段即可。

| 别名          | 指向         | 含义                                                                                                                          |
| :------------ | :----------- | :---------------------------------------------------------------------------------------------------------------------------- |
| `jev-latest`  | `jev-1.13.0` | 最近的稳定官方版本。是我们客户端 SDK 中的默认值，也是这些文档示例中使用的名称。                                               |
| `jev-preview` | `jev-1.13.0` | 最近的版本，无论它是否为官方版本。当有预览构建可用时，它会先于 `jev-latest` 前移。                                            |

<Warning>
  `jev-preview` 目前指向与 `jev-latest` 相同的模型。当前没有可用的预览构建。
</Warning>

新版本发布时别名会随之前移，因此即使你这边没有任何改动，它背后的答案也可能变化。响应的 `model` 字段会报告实际作答的带版本 ID，方便你记录每个结果由哪个模型产生。如果你已针对特定版本调好了置信度阈值，请固定使用该版本的 ID 而不是别名，并按你自己的节奏迁移到新版本。

## 定制 Jev

Jev 不会用客户数据做微调或 LoRA 适配。它通过 [RLCD](/introduction/machine-learning-primer) 训练以返回经过校准的判断，所有账户共用同一套权重。你通过请求来塑造它针对你的领域的答案，而不是通过每个账户独立的权重：

* 把你的专有内容、数据记录和参考资料放进 `state` 字段。参见 [State](/concepts/state)。
* 在每个问题的 `instructions` 和 `criteria` 中编码你的领域规则和边界情况。参见[如何使用 TypeSafe 构建](/concepts/how-to-build-with-system-one)和[进阶：结构](/primitives/advanced)。
* 把宽泛的判断拆解为原子问题，并在代码中组合输出。参见[组合评分](/patterns/composite-scoring)，以及[AutoResearch 实战指南](/cookbooks/autoresearch_feature_discovery)——其中介绍了如何基于 Jev 的概率训练下游经典模型。

## 语言支持

Jev 接受自然语言文本。英语是主要训练语言，也是目前准确率最高的语言。其他语言（包括中日韩文字）可以处理但效果不一；在把 Jev 用于非英语工作负载之前，请先在自己的内容上测试，并在路由时密切关注 [Confidence](/confidence)。

## 数据处理

Jev 不会在客户请求或响应上训练。数据处理协议、隐私政策以及面向企业客户的零数据留存（ZDR）详情参见 [Legal](/legal)。

## 列出模型

`GET /v1/models` 返回你的账户可以在 `model` 字段中填写的名称，并附带各自的描述和发布日期。它目前列出的是别名。像 `jev-1.13.0` 这样的带版本 ID 无论是否出现在列表中，`model` 字段都接受。

<CodeGroup>
  ```bash cURL theme={null}
  curl https://api.typesafe.ai/v1/models \
    -H "Authorization: Bearer $TYPESAFE_API_KEY"
  ```

  ```python Python theme={null}
  from typesafe_sdk import TypeSafeClient

  with TypeSafeClient() as client:
      for model in client.models.list().models:
          print(model.name, model.release_date, model.description)
  ```

  ```typescript JavaScript theme={null}
  import { TypeSafeClient } from "@typesafe-ai/sdk";

  const client = new TypeSafeClient();
  const models = await client.models.list();
  for (const model of models) {
    console.log(model.name, model.release_date, model.description);
  }
  ```
</CodeGroup>

<ResponseField name="models" type="array" required>
  每个模型或别名对应一个条目。

  <Expandable title="属性">
    <ResponseField name="name" type="string" required>
      模型 ID 或别名，即 `model` 字段接受的值。
    </ResponseField>

    <ResponseField name="description" type="string" required>
      该模型的用途。
    </ResponseField>

    <ResponseField name="release_date" type="string" required>
      模型或别名的发布时间。
    </ResponseField>
  </Expandable>
</ResponseField>

完整的方法签名参见 [Python](/sdk/python/api/clients/sync#typesafe_sdk.Models.list) 和 [JavaScript](/sdk/javascript/api/interfaces/Models) SDK 参考。
