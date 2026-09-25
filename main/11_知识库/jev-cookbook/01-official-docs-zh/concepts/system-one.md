# System One

> System One 模型为软件做出快速、结构化的决策。Jev 是 TypeSafe 的旗舰模型，也是首个 System One 模型。

System One 模型是一类 AI 模型，专为做出软件可直接使用的快速结构化决策而构建。System One 模型评估一个[状态](/concepts/state)，并返回类型化的答案和概率。

Jev 是 TypeSafe 的旗舰模型，也是首个 System One 模型。

与 LLM 一样，System One 模型能理解自然语言输入。它返回的是类型化的决策和概率，而非生成的文本。

<Note>
  Jev 目前只接受文本输入。它可以评估字符串、JSON 对象和文本数组。图像、音频和视频尚不受支持（暂时）。
</Note>

## 与 LLM 的区别

System One 模型为校准决策而训练：其概率针对实际结果进行优化，以反映不确定性。校准是在成组的预测上度量的；它并不保证单个答案一定正确。

System One 模型不撰写回复、不产出代码，也不生成对其推理过程的解释。你通过[原语](/primitives)定义可能的答案：

| 原语                         | 问题                                  | 示例答案空间                                  | 示例输出            |
| ---------------------------- | ------------------------------------- | --------------------------------------------- | ------------------- |
| [Choice](/primitives/choice) | 哪个团队应当处理这张工单？            | `billing`, `technical`, 或 `account`          | `choice: "billing"` |
| [Score](/primitives/score)   | 这位客户有多不满？                    | 0 = 平静, 1 = 不满, 2 = 非常不满              | `score: 1.4`        |
| [Noul](/primitives/noul)     | 这条消息是否要求退款？                | 真或假                                        | `noul: 0.95`        |

这些只是示例性的配置和数值。各原语页面描述了可用的配置选项和完整的响应字段。

阅读 [AI 入门](/introduction/machine-learning-primer)，了解 System One 模型的工作原理和训练方式。

<Note>
  System One 这个名称源自丹尼尔·卡尼曼（Daniel Kahneman）在其著作《思考，快与慢》中推广的概念。系统 1 思维快速而直观，系统 2 则更慢、更审慎。在这里，强调的是快速、聚焦的判断。
</Note>

## 更大工作流中的快速判断

对于一笔退款请求，你的应用可以：

1. 构建一个包含客户消息、相关交易和退款政策的状态。
2. 一起提出相互独立的问题：是否请求了退款、证据是否表明存在重复扣款，以及政策是否支持退款。
3. 在代码中将答案与确定性检查相结合，然后将案例路由至执行或审核。

看过原语的实际运作之后，你就可以将它们组合成更大的系统。由于 System One 模型返回的是类型化、受约束的输出而非自由格式的文本，你的代码可以检查并组合这些答案，构建可预测的工作流。完整工作流参见[如何使用 TypeSafe 构建](/concepts/how-to-build-with-system-one)。

System One 模型的答案还包含[置信度](/confidence)，你可以据此决定何时行动、何时升级给人工或推理模型。

## 调用 System One 模型

通过我们的某个[客户端 SDK](/sdk)或 [HTTP API](/api) 中的 `POST /v1/systemone` 调用 System One 模型。`model` 字段选择由哪个模型处理请求。这些文档中的示例使用 `jev-latest`，它也是 SDK 的默认值。可用模型、价格及别名请参见[模型](/models)。

从[状态](/concepts/state)开始准备输入，并通过[原语（问题）](/primitives)探索你可以提出的问题类型。
