# 快速开始

> 想直接上手？这里是立即开始所需的全部内容。

## 试用：Playground

1. **打开 [Playground](https://console.typesafe.ai/playground)** 并登录。
2. **粘贴任意文本**作为状态。

```plaintext title="Sample state" theme={null}
Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP.
```

3. **添加一个问题。**试试 Noul 问题：`"Does this message express urgency?"`

```json theme={null}
{
  "urgency": {
    "type": "noul",
    "instructions": "Does this message express urgency?"
  }
}
```

4. **添加更多问题。**在一次调用中混用 Noul、Choice 和 Score，并一次看到所有结果。

## 调用：API

1. 从[控制台](https://console.typesafe.ai/keys)**获取你的 API 密钥**
2. 向 API 端点**发起 POST 请求**
3. **查看 [API 参考](/api)** 了解所有细节。

```http theme={null}
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

### cURL 命令示例

```bash theme={null}
curl -X POST https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
  {
    "state": "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP.",
    "model": "jev-latest",
    "questions": {
      "urgency": {
        "type": "noul",
        "instructions": "Does this message express urgency?"
      }
    }
  }
EOF
```

### 请求体

```json theme={null}
{
  "state": "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP.",
  "model": "jev-latest",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle this",
      "criteria": {
        "billing": "Payment or subscription issues",
        "technical": "Bugs or integration problems",
        "sales": "Pricing or account questions"
      }
    },
    "frustration": {
      "type": "score",
      "instructions": "How frustrated the customer appears",
      "criteria": [
        "Calm, just stating facts",
        "Frustrated but civil",
        "Very angry, strong language"
      ]
    },
    "is_urgent": {
      "type": "noul",
      "instructions": "The message conveys urgency or time-sensitivity"
    }
  }
}
```

### 响应体

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "department": {
      "type": "choice",
      "choice": "technical",
      "confidence": 0.78,
      "probabilities": {
        "technical": 0.85,
        "sales": 0.0,
        "billing": 0.15
      }
    },
    "frustration": {
      "type": "score",
      "score": 1.0,
      "confidence": 1.0,
      "legend": {
        "0": "Calm, just stating facts",
        "1": "Frustrated but civil",
        "2": "Very angry, strong language"
      },
      "probabilities": {
        "0": 0.0,
        "1": 1.0,
        "2": 0.0
      }
    },
    "is_urgent": {
      "type": "noul",
      "noul": 1.0
    }
  },
  "usage": {
    "input_tokens": 392,
    "output_tokens": 65
  }
}
```

所有细节请参见 [API 参考](/api)。

## 编码：Python SDK

1. **安装 SDK**（需要 Python >= 3.10）。

```bash title="With pip" theme={null}
pip install typesafe-sdk
```

```bash title="With uv" theme={null}
uv add typesafe-sdk
```

2. **使用 SDK。**客户端会从环境变量读取 `TYPESAFE_API_KEY`，并默认调用 `jev-latest`。

```python theme={null}
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

client = TypeSafeClient()

ticket = "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP."

response = client.system_one(
    state=ticket,
    questions={
        "department": Choice(
            instructions="Which team should handle this",
            criteria={
                "billing": "Payment or subscription issues",
                "technical": "Bugs or integration problems",
                "sales": "Pricing or account questions",
            },
        ),
        "frustration": Score(
            instructions="How frustrated the customer appears",
            criteria=[
                "Calm, just stating facts",
                "Frustrated but civil",
                "Very angry, strong language",
            ],
        ),
        "is_urgent": Noul(
            instructions="The message conveys urgency or time-sensitivity",
        ),
    },
)

print(response.answers["department"].choice)  # "technical"
print(response.answers["frustration"].score)  # 1.0
print(response.answers["is_urgent"].noul)     # 1.0
```

安装选项和详细用法参见[客户端 SDK](/sdk)。

## 氛围编程：agent 技能

1. 使用 Claude Code 插件或 `npx skills add typesafe-ai/skills --skill typesafe-ai` 来**[安装 TypeSafe 技能](/agent-skill#installation)**。你也可以[在 GitHub 上阅读 SKILL.md](https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md)。

<Tabs>
  <Tab title="Claude Code">
    在终端中运行以下两条命令：

    ```bash theme={null}
    claude plugin marketplace add typesafe-ai/skills
    claude plugin install typesafe@typesafe-ai
    ```
  </Tab>

  <Tab title="其他 agent">
    ```bash theme={null}
    npx skills add typesafe-ai/skills --skill typesafe-ai
    ```

    出现提示时选择你的 agent。安装默认只作用于当前项目；添加 `-g` 可全局安装。
  </Tab>

  <Tab title="复制到你的 agent">
    把这段提示词粘贴给你的编码 agent：

    ```text wrap theme={null}
    Install the TypeSafe skill. If you're in Claude Code, run `claude plugin marketplace add typesafe-ai/skills`, then `claude plugin install typesafe@typesafe-ai`. If you're in another agent, run `npx skills add typesafe-ai/skills --skill typesafe-ai` and select your agent. Use one installation method. You can read the skill directly at https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md (raw: https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md). Then use the TypeSafe skill when working on this project.
    ```
  </Tab>
</Tabs>

2. **告诉你的编码 agent** 在构建过程中使用 TypeSafe 技能！

```plaintext title="Coding agent prompt" theme={null}
Let's build a simple CLI that uses the TypeSafe API to evaluate a set of supplied documents on multiple dimensions. Use the TypeSafe skill to understand how to use the TypeSafe API and how to structure the system. Ask me questions about what kinds of documents I want to evaluate and on what dimensions.
```

更多细节请参见 [Agent Skill](/agent-skill) 页面。
