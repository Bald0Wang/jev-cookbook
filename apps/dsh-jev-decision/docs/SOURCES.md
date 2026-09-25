# 参考资料与版本

核对日期：2026-09-22。

| 资料 | 在本项目中的用途 |
| --- | --- |
| [DeepSeek Harness 官方仓库](https://github.com/deepseek-ai/deepseek-harness) | 确认 DSH 项目、Node/Cordis 架构和插件入口 |
| [DSH npm 发布包](https://www.npmjs.com/package/@deepseek-ai/dsh/v/0.1.5-rc.2) | 本项目的安装与接口兼容基线 |
| [DSH 编写工具文档](https://github.com/deepseek-ai/deepseek-harness/blob/c36a83ff6bb95e3f82cf79f9be7c724270a8aa61/docs/user/develop/basic/tool.md) | 工具 schema、执行与渲染思路；签名以已安装发布包核实 |
| [DSH 发布插件文档](https://github.com/deepseek-ai/deepseek-harness/blob/c36a83ff6bb95e3f82cf79f9be7c724270a8aa61/docs/user/develop/basic/publish.md) | `dsh.bundle.patch`、安装与依赖边界 |
| [TypeSafe API](https://docs.typesafe.ai/api) | HTTP 端点、认证、state/questions/answers/usage、三种原语 |
| [TypeSafe 模型](https://docs.typesafe.ai/models) | 模型名与别名；本项目默认固定 `jev-1.13.0` |
| [中文 Jev System One 文档](https://bald0wang.github.io/jev-docs-zh/concepts/system-one/) | 与此前中文 cookbook 的概念衔接 |

实际接口还核对了锁定 npm 包中的 `.d.ts`、运行时代码和预设示例：`@deepseek-ai/cordis@4.0.2`、`@deepseek-ai/dsh-tools@0.1.5-rc.2`、`@deepseek-ai/dsh-system-prompt@0.1.5-rc.2`、`@deepseek-ai/dsh-agent-presets@0.1.5-rc.2`。

主分支与发布版不能混用：核对时主分支处于 `0.1.7-alpha.1`，其 preset registry 设计已改变；本项目按照 `0.1.5-rc.2` 的本地模式目录和 `agent.cordis.yml` 实现。`package-lock.json` 固定依赖，`overrides` 将 DSH 包对齐至同一发布版本，防止预发布版本的宽松范围引入更高版本。

本次项目是原生插件实现。教程采用目标→示例→解释→验证的组织方式；没有复制 Datawhale 文章，也不声称它是 Datawhale 官方教程。
