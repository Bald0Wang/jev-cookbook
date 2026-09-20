# TypeSafe Python SDK

> 安装 TypeSafe Python SDK，开始进行异步或同步 API 调用。

<a id="typesafe-python-sdk" />

浏览 [GitHub 上的 Python SDK 源代码](https://github.com/typesafe-ai/typesafe-sdk-python)。

面向 [TypeSafe](https://typesafe.ai) API 的异步与同步 Python 客户端。了解如何使用 TypeSafe，请参见[此处](https://docs.typesafe.ai/)。

<h2 id="quickstart">
  快速开始
</h2>

1. 安装 SDK：

   <Tabs>
     <Tab title="uv">
       ```sh theme={null}
       uv add typesafe-sdk
       ```
     </Tab>

     <Tab title="pip">
       ```sh theme={null}
       pip install typesafe-sdk
       ```
     </Tab>
   </Tabs>
2. 在你的环境中设置 `TYPESAFE_API_KEY`（在[此处](https://console.typesafe.ai/)创建）
3. 调用 System One API：

   <Tabs>
     <Tab title="Async">
       使用 [AsyncTypeSafeClient](/sdk/python/api/clients/async)：

       ```python theme={null}
       from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score


       async def main() -> None:
           async with AsyncTypeSafeClient() as client:
               response = await client.system_one(
                   state={"document": "I was charged twice. Please fix this ASAP."},
                   questions={
                       "billing": Noul(instructions="Is this ticket about billing?"),
                       "tone": Choice(
                           instructions="What is the customer's tone?",
                           criteria={"calm": None, "frustrated": None, "angry": None},
                       ),
                       "urgency": Score(
                           instructions="How urgent is this ticket?",
                           criteria=["can wait", "this week", "today"],
                       ),
                   },
               )

           print(response.nouls["billing"].noul)
           print(response.choices["tone"].choice)
           print(response.scores["urgency"].score)
       ```
     </Tab>

     <Tab title="Sync">
       使用 [TypeSafeClient](/sdk/python/api/clients/sync)：

       ```python theme={null}
       from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

       with TypeSafeClient() as client:
           response = client.system_one(
               state={"document": "I was charged twice. Please fix this ASAP."},
               questions={
                   "billing": Noul(instructions="Is this ticket about billing?"),
                   "tone": Choice(
                       instructions="What is the customer's tone?",
                       criteria={"calm": None, "frustrated": None, "angry": None},
                   ),
                   "urgency": Score(
                       instructions="How urgent is this ticket?",
                       criteria=["can wait", "this week", "today"],
                   ),
               },
           )

       print(response.nouls["billing"].noul)
       print(response.choices["tone"].choice)
       print(response.scores["urgency"].score)
       ```
     </Tab>
   </Tabs>

<h2 id="usage">
  用法
</h2>

更多信息请参阅[使用指南](/sdk/python/usage)。
