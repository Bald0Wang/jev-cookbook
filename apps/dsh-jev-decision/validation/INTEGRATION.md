# 学习仓库集成验证：2026-09-24

将 0.1.2 源码复制到本仓库 `apps/dsh-jev-decision/` 后重新验证。没有复制原项目的 `node_modules`、`.env`、DSH home 或会话数据。环境为同一台 macOS、Node.js 24.19.0、DSH 0.1.5-rc.2，**不是另一台机器验证**。

| 检查 | 实际结果 |
|---|---|
| `npm ci --ignore-scripts` | 新目录从锁文件安装成功，523 个包；安装时审计 0 个已知漏洞，仅代表该次 registry 结果 |
| `npm test` | TypeScript 编译成功，26/26 通过 |
| `npm run test:install` | 临时 home、官方 plugin add、预设发现、完整 core 挂载、已安装工具执行全部通过；不调用付费 API |
| 全新 profile 的核心会话检查 | `setup-chat-check.mjs` 与 `check-chat-live.mjs --inspect` 通过，确认模式提示及 10 个工具；补齐报告父目录自动创建，新克隆无需手动建立 reports |
| Notebook 生成器 | `py_compile` 通过；生成 29 格，其中 12 个代码单元 |
| Notebook 默认 live 模式 | 2026-09-24 11:28 UTC 从头执行，12 个代码单元全部通过、0 错误；4 次真实 TypeSafe 请求 |
| Notebook 显式 recorded 模式 | 无凭据从头执行 12 个代码单元通过；未覆盖提交的 live 输出 |
| Notebook 实时原语 | writing，Noul 0.91，Score 0.23；1323 ms |
| Notebook 实时分流 | proceed / clarify / review；Noul 0.14 / 0.96 / 0.26；与本次 recommend() 一致 |
| 归档产物独立测试 | clear 4/4，clarify 2/2，通过；不重新运行模型 |
| 网页完整交互 | 页面加载成功，随后桌面自动化报告窗口不可用；没有完成模式选择及任务提交，未通过完整界面验收 |
| 发布前检查 | 新文档本地链接可解析；待提交内容未包含本次两套密钥，新文件未包含个人 home 路径 |

提交的 Notebook 输出是上述 live 运行结果；第 3、4 节明确分析更早的真实会话归档。首次 Notebook 执行在读取旧报告缺失字段时失败；生成器已修正为显式展示“旧报告未记录”，并重新从头执行成功。没有给旧报告补造版本字段或澄清观测值。

独立机器复现与业务标注集评估仍待完成。网络根因调查按当前范围暂缓，已有失败记录保留。
