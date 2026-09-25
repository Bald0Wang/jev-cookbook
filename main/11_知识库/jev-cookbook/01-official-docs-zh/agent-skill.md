# Agent 技能

> 适用于 Claude Code、Codex 及其他智能体环境的即插即用技能。

TypeSafe 智能体技能为你的 AI 编程智能体提供关于 TypeSafe API 的完整上下文：三种问题[类型](/primitives)、架构[模式](/patterns)，以及组织评估的最佳实践。

## 安装

<Tabs>
  <Tab title="Claude Code">
    在终端中运行以下两条命令：

    ```bash theme={null}
    claude plugin marketplace add typesafe-ai/skills
    claude plugin install typesafe@typesafe-ai
    ```
  </Tab>

  <Tab title="其他智能体">
    ```bash theme={null}
    npx skills add typesafe-ai/skills --skill typesafe-ai
    ```

    在提示时选择你的智能体。默认安装到项目本地；添加 `-g` 可全局安装。
  </Tab>

  <Tab title="复制到你的智能体">
    把这段提示粘贴到你的编程智能体中：

    ```text wrap theme={null}
    Install the TypeSafe skill. If you're in Claude Code, run `claude plugin marketplace add typesafe-ai/skills`, then `claude plugin install typesafe@typesafe-ai`. If you're in another agent, run `npx skills add typesafe-ai/skills --skill typesafe-ai` and select your agent. Use one installation method. You can read the skill directly at https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md (raw: https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md). Then use the TypeSafe skill when working on this project.
    ```
  </Tab>
</Tabs>

阅读 [GitHub 上的 SKILL.md](https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md)，或直接获取[原始 Markdown](https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md)。如需手动安装，请把整个 [skills/typesafe-ai 目录](https://github.com/typesafe-ai/skills/tree/main/skills/typesafe-ai)（包括其参考文件）复制到你智能体的技能目录中。

选择一种安装方式即可，避免产生重复副本。

### 更新

对于 Claude Code 插件，运行：

```bash theme={null}
claude plugin marketplace update typesafe-ai
claude plugin update typesafe@typesafe-ai
```

重启 Claude Code 或运行 `/reload-plugins` 以加载更新。要启用自动更新，请打开 `/plugin`，选择 **Marketplaces → typesafe-ai → Enable auto-update**。

对于 skills.sh 安装，运行 `npx skills update`。对于手动复制，用 GitHub 上的最新版本替换整个技能目录。

## 提示示例

在提示中点名该技能——"use the TypeSafe skill"——在任何智能体中都有效，因此下面的每个提示都这样做。使用 Claude Code 插件时，你还可以直接调用 `/typesafe:typesafe-ai`。

* 一个很好的入门提示是头脑风暴类提示，帮助你找出 TypeSafe 在项目中能发挥最大作用的地方。

  ```text theme={null}
  Using the TypeSafe skill, explore the project and find opportunities for using
  intelligent judgement to stand in for complex parsing or other fragile code.
  ```

* 你还可以创建一个 [API key](https://console.typesafe.ai/keys)，并允许你的智能体通过运行廉价的测试查询，自行摸索使用 TypeSafe 的最佳方式。

  ```text theme={null}
  Using the TypeSafe skill, run some experiments using the TypeSafe API key that I've
  exported to `TYPESAFE_API_KEY`. Propose changes based on the most promising results.
  ```

* 让你的智能体参考一个能解决你代码库中实际问题的[具体实战指南](/cookbooks/consistency_noul_cookbook)，或让它查看[实战指南索引](/cookbooks)，问问是否存在与你项目中的模式类似的模式。

  ```text theme={null}
  Using the TypeSafe skill, analyze my code and see if there are any applicable
  cookbooks (https://console.typesafe.ai/docs/cookbooks) that show how I could
  refactor my code to be less fragile or complex.
  ```

## 良好的 vibe coding 原则

1. 与你的智能体把想法聊透，以上面的示例提示作为起点。
2. 在实现之前审阅计划，确保它合理。
3. 把常量（问题和阈值）放在单一位置，便于审阅。智能体并不擅长编写问题，所以要做好与它们协作修改的准备。
4. 不要照单全收智能体的断言；鼓励它验证自己的假设。

## 常见问题

### 智能体没有使用该技能

使用 Claude Code 插件时，调用 `/typesafe:typesafe-ai`。在其他智能体中，要求它"use the TypeSafe skill"。如果技能仍然没有加载，请确认安装时选择的正是你正在使用的智能体，然后重启该智能体。

### 路由行为不符合预期

检查问题和阈值。你的阈值可能设得过高（导致假阴性）或过低（导致假阳性）。你也可能需要调整问题，使其更具体。

### 你到处都在使用置信度阈值

如果你只关心选出最佳选项，只需选择置信度最高的选项即可（而不是设置置信度阈值）。如果你心中已有特定的统计算法，那么或许应该使用概率而不是置信度。

### TypeSafe 代码难以审阅

对人类而言，最需要审阅的是 TypeSafe 代码中使用的问题和任何阈值常量。它们应当定义在单个代码文件中，这样就无需费力翻找也能轻松找到。

### 智能体虚构请求或响应字段

技能版本过旧可能导致此问题。用上面对应的安装方式更新它，然后重试。
