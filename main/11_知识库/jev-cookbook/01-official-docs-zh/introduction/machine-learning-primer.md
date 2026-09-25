# AI 入门

> 为什么 TypeSafe 训练具有校准概率的决策模型，而不是为生成文本进行优化。

大多数 AI 产品都围绕模型与人之间的对话构建。TypeSafe 从一个不同的押注出发：大规模自动化将由 AI 对 AI 和 AI 对软件的交互主导，因此机器接口比聊天接口更重要。

> **我们称之为机器原生智能（Machine Native Intelligence）：**
>
> 具有软件般特性的 AI，例如结构化、可靠性、可观测性、可测试性、速度、一致性和低成本。

## 构建生产系统，而非造神

TypeSafe 并不试图构建一个无所不能的模型。它是为生产系统设计的——在这些系统中，代码需要一个狭窄的、可以审查并据此行动的决策。

我们的预期是，大规模 AI 自动化将更接近 99% 的机器对机器交互和 1% 的人类交互。这把设计目标从读起来令人愉悦的响应，转向在软件中表现可预测的输出。

阅读 [TypeSafe 宣言](https://typesafe.ai/manifesto)。

## 三种训练后方法

预训练语言模型已经以两种主要方式被改造。TypeSafe 增加了第三种。这里展示 RLHF 和 RLVR 作为背景；TypeSafe 的训练路径是 RLCD。

<Columns cols={3}>
  <Card title="RLHF" icon="messages-square" type="note">
    **基于人类反馈的强化学习**把预训练模型变成了聊天机器人。它训练模型生成人们更偏好的响应。
  </Card>

  <Card title="RLVR" icon="brain-circuit" type="note">
    **可验证奖励的强化学习**创造了推理模型，它们擅长数学等任务，但更慢、更昂贵。
  </Card>

  <Card title="RLCD" icon="binary" type="tip">
    **面向校准决策的强化学习**训练 TypeSafe 返回决策和校准概率，而不是生成的文本。
  </Card>
</Columns>

RLHF 曾被用于训练 InstructGPT 和 ChatGPT，并由 TypeSafe 联合创始人 Diogo Almeida [共同发明](https://scholar.google.com/citations?user=0T4y07QAAAAJ\&hl=en)。

<Frame>
  <img className="block dark:hidden" src="https://mintcdn.com/ts-docs/aFVnpmCIX68NpsV1/images/ai-primer/training-paths-light.webp?fit=max&auto=format&n=aFVnpmCIX68NpsV1&q=85&s=61898215ac31388d3be15bf583b743ee" alt="Pretrained language models branch into muted RLHF and RLVR paths and an emphasized RLCD decision-model path." width="2048" height="810" data-path="images/ai-primer/training-paths-light.webp" />

  <img className="hidden dark:block" src="https://mintcdn.com/ts-docs/aFVnpmCIX68NpsV1/images/ai-primer/training-paths-dark.webp?fit=max&auto=format&n=aFVnpmCIX68NpsV1&q=85&s=2747633edb0e54fa3f14a8aba830f4fd" alt="Pretrained language models branch into muted RLHF and RLVR paths and an emphasized RLCD decision-model path." width="2048" height="810" data-path="images/ai-primer/training-paths-dark.webp" />
</Frame>

## RLCD 与校准决策

RLCD 优化的是另一种不同的输出契约：

* 模型不生成文本。
* 它返回决策和概率。
* 更高的概率应当对应答案正确的更大可能性。

校准让不确定性变得可以被软件使用。对于一个校准良好的模型的多次预测：

* 被赋予 `0.2` 概率的结果应当大约在 20% 的情况下发生。
* 被赋予 `0.8` 概率的结果应当大约在 80% 的情况下发生。
* 被赋予 `1.0` 概率的结果应当在 100% 的情况下发生。

这些比率描述的是一组预测，而不是对任何单个答案的保证。关于如何决定软件何时应当执行、何时应当升级，参见[置信度](/confidence)。

## RLHF 的问题

RLHF 教模型说人们偏好的话。这个目标对聊天机器人很有效，但它也可能奖励谄媚行为和听起来自信的幻觉。

偏好优化还会导致**模式丢弃（mode dropping）**：模型学会偏好某种特定风格，例如遵循指令，同时降低其他可能输出的概率。

<Frame>
  <img className="block dark:hidden" src="https://mintcdn.com/ts-docs/aFVnpmCIX68NpsV1/images/ai-primer/mode-dropping-light.webp?fit=max&auto=format&n=aFVnpmCIX68NpsV1&q=85&s=d51758a6212b526fc243cc9a81572cc7" alt="The probability distribution of a base model compared with a narrowed, mode-dropped distribution after RLHF." width="2048" height="1117" data-path="images/ai-primer/mode-dropping-light.webp" />

  <img className="hidden dark:block" src="https://mintcdn.com/ts-docs/aFVnpmCIX68NpsV1/images/ai-primer/mode-dropping-dark.webp?fit=max&auto=format&n=aFVnpmCIX68NpsV1&q=85&s=4330e6251ca335515a61f61794f21389" alt="The probability distribution of a base model compared with a narrowed, mode-dropped distribution after RLHF." width="2048" height="1117" data-path="images/ai-primer/mode-dropping-dark.webp" />
</Frame>

<Warning>
  一个输出可以对人很有说服力，却不足以可靠地支撑无人值守的自动化。人类偏好和机器可信度是不同的优化目标。
</Warning>

模式丢弃是**模式坍缩（mode collapse）**的较温和版本。在经典的生成对抗网络失败模式中，生成器学会反复生成同一种输出，因为那种输出能持续骗过判别器。

<Accordion title="模式坍缩类比">
  <Frame>
    <img className="block dark:hidden" src="https://mintcdn.com/ts-docs/aFVnpmCIX68NpsV1/images/ai-primer/mode-collapse-light.webp?fit=max&auto=format&n=aFVnpmCIX68NpsV1&q=85&s=2896f125ad1a5835b31b088fbc64eff1" alt="Repeated characters illustrate a GAN suffering from mode collapse." width="1084" height="759" data-path="images/ai-primer/mode-collapse-light.webp" />

    <img className="hidden dark:block" src="https://mintcdn.com/ts-docs/aFVnpmCIX68NpsV1/images/ai-primer/mode-collapse-dark.webp?fit=max&auto=format&n=aFVnpmCIX68NpsV1&q=85&s=95645bdefd0bb3fa093edc3dd9308337" alt="Repeated characters illustrate a GAN suffering from mode collapse." width="1084" height="759" data-path="images/ai-primer/mode-collapse-dark.webp" />
  </Frame>
</Accordion>

RLHF 仍然是会话模型的良好选择。TypeSafe 的立场是：生产自动化需要一种不同的训练目标——一种以受约束的决策和校准的不确定性为中心的目标。
