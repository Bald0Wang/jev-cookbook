# 公开实验记录

这些 JSON 来自 2026-09-24 的真实 API 与 DSH 核心会话，不是人工 mock；它们也不是读者本次新运行的结果。

| 文件 | 内容 |
|---|---|
| `live-primitives-20260924-02.json` | 三种原语，一次真实请求 |
| `live-routes-20260924-01.json` | 三条固定分流输入与真实响应 |
| `chat-clear-20260924-02.json` | 0.1.2 明确任务，首步 review 后完成修复 |
| `chat-clarify-20260924-03.json` | 0.1.2 模糊任务，提问后脚本回答并修复 |
| `chat-clarify-20260924-01.json` | 0.1.1 未遵守 clarify 的失败案例 |
| `chat-review-20260924-02.json` | 0.1.2 network_error，未修改源码 |
| `chat-repro-inspect-20260924.json` | 独立 profile 的挂载检查，不调用模型 |
| `workspaces/clear/`、`workspaces/clarify/` | 两次成功会话结束后的实际练习文件 |
| [INTEGRATION.md](INTEGRATION.md) | 纳入学习仓库后的重新安装与执行验证 |

公开导出保留原语请求与响应；聊天只保留 `tool/call`、`tool/result`、助手正文与 `turn/end`，放在 `trace` 数组中。工具调用与结果以 `call_id` 对应。省略流式片段和会话标识，个人路径替换为 `$PLUGIN_ROOT` / `$HOME`。因此它是可读的证据摘录，不是原始流的完整替代品。`provenance.source_sha256` 是本机原始报告的摘要，用于记录来源，不是对模型正确性的证明。

明确任务的 `changed_before_scripted_followup=true` 不表示违反澄清：该任务没有脚本澄清环节。澄清案例应检查 `scripted_answers[].source_changed_before_answer`，它只观测 `date.mjs`。`status: captured` 不等于通过。

在工程根目录可以独立复跑归档产物的测试：

```bash
node --test validation/workspaces/clear/date.test.mjs
node --test validation/workspaces/clarify/date.test.mjs
```

4 项与 2 项测试通过，只证明这两份保存的产物符合各自测试，不代表重新执行过模型。新增原始报告保存到被忽略的 `reports/`；公开前检查密钥、个人路径、访问令牌及输入材料。
