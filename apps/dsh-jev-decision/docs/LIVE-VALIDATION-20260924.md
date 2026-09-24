# 2026-09-24 真实联调记录

两套凭据均真实使用成功。Jev 三种原语和三条固定分流案例成功；DSH 主模型能够主动调用插件、按 review 阅读材料后完成修复，以及在 clarify 提问并取得回答后继续修复。0.1.2 修正了实测中发现的澄清跳过和分流顺序问题。

环境：Node 24.19.0、DSH 0.1.5-rc.2、DeepSeek `deepseek-flash`（thinking disabled）、Jev `jev-1.13.0`。完整任务使用 DSH 正式核心运行时显式挂载 `jev-decision` 预设，没有模拟模型或工具响应。澄清回答由测试脚本按预先写好的答案提供，不是现场用户操作。

公开版报告见 [validation](../validation/README.md)，保留关键事件并去除个人路径；本地新增报告仍写入 `reports/`。后续重新安装与 Notebook 验证见 [仓库集成记录](../validation/INTEGRATION.md)。

## 实际结果

| 检查 | 结果 | reports 中的原始记录 |
| --- | --- | --- |
| Choice / Noul / Score | 一次真实请求成功，1329 ms；输入 532、输出 73 tokens | `live-primitives-20260924-02.json` |
| 三条任务分流 | proceed / clarify / review，与固定案例预期相符；676 / 549 / 259 ms | `live-routes-20260924-01.json` |
| 0.1.2 明确任务 | 首个工具为 Jev；返回 review，读资料后修改函数、测试和说明；独立复跑 4 项测试通过 | `chat-clear-20260924-02.json` |
| 0.1.2 必要澄清 | clarify → ask_user_question → 脚本回答 → proceed → 修改并测试；回答前源码未改变；独立复跑 2 项测试通过 | `chat-clarify-20260924-03.json` |
| 0.1.2 材料任务 | TypeSafe network_error；没有有效 action；未修改文件、未自动重试；文字询问材料和目标 | `chat-review-20260924-02.json` |
| 新环境组装 | setup-chat-check 创建独立 profile，inspect 核对模式提示及 10 个工具，不调用模型 | `chat-repro-inspect-20260924.json` |
| 自动化测试 | 最终提示规则编译后 26 项通过，0 失败 | 本轮 npm test 输出 |

三个固定分流样本只证明接口和示例路径，不证明业务准确率。完整明确任务的背景与固定分流样本不同，真实返回 review 属于实际观察，不能改写为 proceed。

## 问题与修正

1. **默认 headless 不自动挂载预设。** 首次尝试只有模型文字输出，工具未执行。新增 `check-chat-live.mjs`，使用与 DSH 会话控制器一致的显式 `agentPresets.mount`，请求前断言模式提示及工具存在。首次 headless 记录不算验收通过。
2. **0.1.1 的 clarify 被主模型跳过。** 模型读示例 README 后猜目标并直接改文件。0.1.2 明确要求先提问等待回答，并规定首个工具调用独立进行分流。失败记录 `chat-clarify-20260924-01.json` 保留；新版成功记录为 `...-03.json`。规则仍依赖主模型遵循，不是强制权限网关。
3. **偶发 TypeSafe 网络失败。** 初次受限网络请求失败，解除网络限制后成功；后续聊天另有两次 network_error，均保留，模型没有据此修改文件或自动重复请求。尚未确认瞬时连接错误的底层原因，不宣称网络稳定性通过。
4. **行为扩展需人工审阅。** 明确任务样本把纯空白字符串也视作空字符串；澄清后的样本只处理严格空字符串。两者满足本例空字符串及正常 ISO 日期要求，但不证明所有业务输入都正确。

## 复现核心会话

先按 README 安装 Node 24 和依赖，在本地 `.env` 配置两套 Key。使用新的 DSH_HOME、示例目录和报告名，避免覆盖记录：

```bash
npm run build
export DSH_HOME="$PWD/.dsh-local/chat-check-01"
node scripts/setup-chat-check.mjs
node --input-type=module -e 'import {cp} from "node:fs/promises"; await cp("examples/chat-workspace", ".demo-workspace-chat-01", {recursive:true, force:false, errorOnExist:true});'

# 检查组装，不调用模型。
node scripts/check-chat-live.mjs --inspect --workspace .demo-workspace-chat-01 --output reports/chat-inspect-new.json

# 真实调用，会消耗两套 API 额度；180 秒超时，无自动模型重试。
node --env-file=.env scripts/check-chat-live.mjs --case clear --workspace .demo-workspace-chat-01 --output reports/chat-clear-new.json
```

`--case` 可为 clear、clarify、review，每次使用新的示例副本。`status: captured` 仅表示证据已保存，**不代表任务成功**。检查 tool/call、tool/result、turn/end、实际文件与测试；网络错误或没有实际修改不能记为修复成功。

clarify 的预设回答是“当前目录 parseDate 对空字符串返回 null，正常 ISO 日期行为保持不变，并补测试”。脚本仅在实际出现提问后提供答案，不提前把答案塞进初始任务。

## 尚未覆盖

- 网页模式选择器中的完整人工交互、截图或录像。
- 同伴在另一台机器从零安装并完成任务。
- 网络稳定性、业务准确率及阈值校准。

本机 `.env` 权限为 0600。凭据不进入安装包、源码包或验收报告。
