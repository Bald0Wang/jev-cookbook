# 一天任务的最小验收

原任务：**1 人 1 天，DSH 决策插件开发，或者对 DSH 新增模式。** 经确认采用“DSH × Jev 决策工具，附带可演示模式配置”。

本次补齐只服务于：可安装、能调用 Jev、能在 DSH 里演示、别人能复现。业务评测集、阈值校准、普通 DSH 对照实验、跨平台适配和生产部署都不作为这次交付的前置条件。

0.1.2 的实际结果及无需浏览器的核心会话复现入口见[真实联调记录](LIVE-VALIDATION-20260924.md)。

## 1. 准备环境

在项目根目录使用 Node 24、pnpm 和锁定的 DSH `0.1.5-rc.2`。先运行 `node --version`，不要因默认终端是其他 Node 版本而误判插件故障。

按 README 的安装步骤建立独立 `.dsh-local` 和 `jev-demo` profile。在本机新建 `.env`，字段参照 `.env.example`：

- `TYPESAFE_API_KEY`：TypeSafe 凭据，用于 Jev。
- `DEEPSEEK_API_KEY`：DeepSeek 凭据，用于聊天主模型。
- `TYPESAFE_DEFAULT_MODEL=jev-1.13.0`。
- `JEV_DECISION_MODE=live`。

密钥不用贴到聊天、截图或交付包。`.env` 已被忽略；已有进程环境变量优先于 Node 的 `--env-file`，修改配置后须启动新进程。

## 2. Jev 真实接口检查

```bash
npm run build
node --env-file=.env scripts/check-live.mjs --output reports/live-primitives-01.json
node --env-file=.env scripts/check-live.mjs --routes --output reports/live-routes-01.json
```

第一条检查最多 1 次请求，覆盖 Choice / Noul / Score；第二条最多 3 次请求，覆盖任务分流工具。每个命令遇到第一个错误就停止，不自动重试。报告路径已存在时拒绝覆盖，换一个文件名再运行。

检查 `status`、各项 `result.source=typesafe_api`、实际模型、答案、请求 ID、耗时和用量。缺少 Key 时记录 `request_attempts=0` 并返回非零退出码，不会伪造成功。

`intended_action` 是教学预期，只用于对照，不发送给 Jev；`matches_intended_action=false` 应保留并解释。`status=ok` 只说明本组工具请求成功，不代表预期分支全部吻合。不要为得到想要的分支反复调用或改写记录。三个案例不用于计算业务准确率。

## 3. DSH 中完成真实任务

先复制练习材料。目录已存在时使用新名字，不覆盖以前的演示结果：

```bash
node --input-type=module -e 'import {cp} from "node:fs/promises"; await cp("examples/chat-workspace", ".demo-workspace-01", {recursive:true, force:false, errorOnExist:true});'
```

然后在同一终端、项目根目录启动已安装的 profile：

```bash
export DSH_HOME="$PWD/.dsh-local"
node --env-file=.env node_modules/@deepseek-ai/dsh/lib/bin.js --profile jev-demo
```

在 DSH 界面选择 `.demo-workspace-01` 作为工作目录，创建新会话，选择“Jev 决策协作”。每个案例使用独立会话；需要重新修改源码时再复制一份练习材料。

### 案例 A：明确任务

只输入任务，不额外提醒它调用 Jev：

> 请修复仓库中日期解析函数对空字符串的处理，并补一个回归测试。

观察完整过程：主模型自行调用 `jev_route_task` → 读取文件 → 修改函数 → 新增空字符串回归测试 → 执行测试 → 总结变更。合格结果是 `parseDate('') === null`，正常 ISO 日期行为仍通过，且实际产生了修改。只打印路由 JSON 不算任务完成。

### 案例 B：必要澄清后继续

在新会话先输入：

> 帮我把那个东西弄好。

观察它是否提出一个具体的必要问题。收到问题后回答：

> 是当前目录的 parseDate 函数。空字符串应返回 null，正常 ISO 日期行为保持不变，请补测试。

观察它使用新信息继续完成任务。新增信息影响判断时可以再调用一次分流；不应对相同输入反复调用，也不应对已明确的目标继续追问。

### 案例 C：先读资料

在新会话输入：

> 看看这份材料，代码和文案方面都处理一下。

观察它是否先读取 README，理解里面写明的修改范围，再处理日期函数、测试和 `description.md`。真实 Jev 可能给出 `review`、`clarify` 或 `proceed`，如实记录；若为 `review`，应先核对现有资料，不能仅因不确定就停住。如果需要分支覆盖演示，可另跑 `npm run demo`，明确那是人工夹具。

### 错误时的行为

离线自动化已覆盖缺少 Key、限流、超时和协议错误；不用为了录像故意消耗无效请求。真实联调若遇到错误，应说明原因，不产生有效路由建议、不自动反复重试。已授权且不依赖判断的资料检查仍可进行；修复配置后重新运行需要新建报告。

## 4. 保存一份诚实的演示记录

可将下面表格复制为 `reports/chat-acceptance.md`，完成后填入事实。无需录制所有案例，至少留下一次完整任务的截图或短录像。

| 项目 | 记录 |
| --- | --- |
| 日期、Node / DSH / 插件版本 | 待填写 |
| Jev 请求模型与实际响应模型 | 待填写 |
| 聊天主模型 | 待填写 |
| 模式是否可选 | 未验证 |
| 是否无需提醒就调用 Jev | 未验证 |
| 工具返回的 action / source / request_id | 待填写 |
| 后续实际行动与生成的文件 | 未验证 |
| 测试命令与实际结果 | 未验证 |
| 澄清回复后是否继续完成任务 | 未验证 |
| 是否出现无新增信息的重复分流 | 未验证 |
| 失败或与教学预期不同的结果 | 待填写，不删除反例 |
| 截图、录像或会话记录位置 | 待填写 |

## 完成边界

- 源码、两个工具、模式配置、离线演示、测试和可安装包：属于最小交付。
- 真实 Jev 请求及一条完整 DSH 对话：用于补齐真实联调证据，需要两套可用凭据。
- 同伴从零安装：推荐做一次；未执行时不写成已通过。
- 无凭据时可以交付离线版本，但应明确标注“真实联调待完成”，不能用传输模拟测试代替真实模型证据。
