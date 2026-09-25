# Werewolf · Jev 狼人杀

第一阶段是 1 名真人 + 5 个 Jev 的离线可运行演示。它使用固定种子、服务器端规则引擎、模板化发言、结构化投票和完整 trace；配置 `TYPESAFE_API_KEY` 后，Jev 请求会从服务器端代理到 `jev-latest`，单次失败自动回退到同一套固定策略。

可选的 `DEEPSEEK_API_KEY` 会启用每个玩家独立的 cognition adapter。白天讨论由 DeepSeek 直接输出经过代码校验的 `speechPlan`；夜间狼人/预言家/女巫技能和白天投票则把 DeepSeek 的摘要、候选嫌疑与记忆交给 Jev 做最终 Choice/Score/Noul 判断，规则引擎负责校验。没有 DeepSeek key 时使用服务器端启发式摘要，不影响游戏运行。默认 `ruleset: "demo"` 在狼人数与好人相等时继续一轮，避免 6 人演示过早结束；需要标准奇偶胜负时传 `ruleset: "standard"`。

## 运行

```powershell
cd D:\AI\jev\games\werewolf
npm start
```

默认打开 <http://localhost:4175>。端口被占用时会自动递增。没有 API key 也能完整进行一局。

服务器从当前目录的 `.env` 或进程环境读取 `TYPESAFE_API_KEY`。浏览器不会接触 API key；普通游戏接口只返回公共状态和真人自己的私有状态。调试面板的“揭示身份”才会返回完整身份、私有 state 和 trace。

## API

- `POST /api/game/new`：创建新局，可传 `seed`、`mode: "offline"`；调试时可传 `debug: true` 和 `fixedRoles`；传 `replay: true, traceId: "sample-game"` 会从服务器 trace 复用已记录动作，完全不请求 Jev。
- `GET /api/game/:id`：返回公共状态与真人私有状态。
- `POST /api/game/:id/advance`：推进到下一个真人操作点或终局。
- `POST /api/game/:id/human-message`：提交真人白天发言。
- `POST /api/game/:id/vote`：提交真人投票。
- `POST /api/game/:id/reveal-debug`：本地调试用的完整快照。
- `POST /api/trace`：传 `{ "gameId": "..." }`，保存到 `trace/<gameId>.json`。

## 验证

白天现在分两步：DeepSeek 先形成玩家私有分析，再生成自然中文公开发言。公开表达请求只接收公共事件、发言计划和经过代码校验的主动查验披露，不接收私有分析或狼人队友名单。发言失败会明确记录 `template_fallback`；自然语言判断不等于规则事实。私有分析按玩家保留，并传给后续投票分析与 Jev。夜间技能和投票仍由 Jev 选择最终目标。

真实发言链路检查（会调用已配置的 DeepSeek/Jev）：`node --env-file=.env verify-live-speech.mjs`。该脚本检查五段实际公开台词、白天不请求 Jev，以及投票读取 DeepSeek 分析。

```powershell
npm test
```
