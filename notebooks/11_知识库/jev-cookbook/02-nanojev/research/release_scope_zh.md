# NanoJev 发布范围与复现边界

NanoJev 发布自写源码、数据生成器、训练与推理入口、实际评测结果、交互回放和三方视频。**Git 仓库不包含训练权重、历史私有教师训练标签、凭证或第三方私人聊天原文。** 历史报告中的“本地源码包／尚未发布”描述其当时状态；当前项目名为 NanoJev，原文件名与实验 schema 保留以便追溯。

## 明确的文件清单

`scripts/package_source.py` 仅枚举 `scripts/` 顶层自写 `.py` 和 `.mjs`，其他内容使用固定清单；不递归复制整个工作区或 `research/`。`scripts/prepare_repository.py` 在此基础上创建新的待发布目录，并生成空密钥模板和忽略规则，不执行网络或 Git 操作。

| 内容 | 来源与范围 |
|---|---|
| 源码与依赖声明 | 自写数据、标注、训练、评估、服务、视频渲染与核验脚本；不含安装的依赖实现 |
| 研究报告 | 公开来源、算法决定、Fable 讨论的自写总结、实际实验协议和结果；不复制私有原始讨论 |
| V2/V3 历史回放 | 完整学生和程序基线结果，保留失败；teacher 命名指学生采用 Jev 输出分布作为训练目标 |
| 新三方对照 | 固定 40 图上 NanoJev、Jev API、原始 Qwen 的 240 局，含实际概率、转移和必要的调用来源引用 |
| Jev 测评来源 | 本次自写环境上新的最小请求/响应记录；不含账户、Authorization、完整供应商 envelope 或历史教师训练集 |
| GIF、MP4、PNG | 隔离 Chrome 从真实轨迹页面渲染，按环境步数同步；不是模型延迟测量 |
| 清单与审计 | 文件 SHA256、大小、来源、逐局核验和媒体检查结果 |

`SOURCE_MANIFEST.json` 记录每个已选文件的哈希与来源；它本身不递归列出自哈希。原始 V3 完整私有来源核验和新的公开核验是不同范围：公开文件能核验转移、控制器、概率、内嵌来源链，不能仅靠本地日志证明供应商实际执行或重新证明未随包发布的全部训练资料。

排除 `.env`、密钥、`private*`、Claude 原始日志、官方网页快照、`node_modules`、虚拟环境、缓存、权重和优化器。固定清单配合凭据样式扫描；扫描失败只报告文件名，不输出匹配值。两份新 Jev 测评结果是显式白名单例外，不扩大为允许发布教师训练标签。

## 能直接运行什么

静态回放无需 API、GPU、模型或前端依赖：

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory web
```

打开 `http://127.0.0.1:8080/comparison.html` 查看新的三方对照；根页面提供更多历史案例。静态服务器不提供 `/api/evaluate`。真正在线推理需要安装运行依赖并提供兼容 checkpoint，服务入口不会调用教师。

[完整执行手册](pipeline_runbook_zh.md) 提供零 API 的 V2 程序监督数据组装与新训练路径，以及可切换的 Jev 标注路径。已实际验证完整 2,312 状态 / 6,936 题的数据组装与 schema；这不是声称在发布步骤重新训练了模型。

新三方原始 Qwen 基线需要显式下载固定 revision 并准备本地 CUDA 环境，见 [基线说明](navigation_v3_native_qwen_zh.md)。新的 Jev 请求需要 Node.js ≥22、锁定依赖和用户自己的本机密钥；重新请求可能因服务版本变化而得到不同结果。

## 权重谱系与结果复现

底座为 `Qwen/Qwen3-0.6B`，revision `c1899de289a04d12100db370d81485cdf75e47ca`。三方演示固定使用 `v3_teacher_coords_multi_seed17`，权重 SHA-256 为 `fff62d1412685c1714eaa386acb603f9690371fb3cc8ad03dc41319302597c28`。本次用户服务器上保留完整权重、tokenizer、配置及日志；Git 仓库未上传这些材料。

从生成器重新构建程序监督数据并训练新的学生是可执行路径。精确重训已有教师监督模型另需冻结标签、分区、指定 V2 warm-start checkpoint 和配置。全部 V3 五组均从 V2 teacher checkpoint 继续训练，gold 指 V3 的更新目标，不表示从未接触教师。不可通过公开摘要反推缺失的逐题预测或私有训练目标。

发布的源码、真实轨迹及三方比较证据可供审阅，但不把“公开代码”称为“已发布模型权重”。原有汇总器若依赖私有 run 目录，其历史聚合结果仍随仓库提供；公共核验模式明确标记能够独立复核的范围。

## 许可

项目代码及自写说明采用 [MIT License](../LICENSE)，自写程序生成环境数据标记 CC0-1.0。生成器属于代码；第三方模型、服务输出、品牌和摘引保留适用权利，不因纳入研究结果而统一变为 MIT。代码许可不重新许可 Qwen 底座或教师监督训练的 checkpoint。NanoJev 与 TypeSafe/Jev 无官方关联。

## 重建源码交付目录

```bash
python3 scripts/package_source.py --self-test
python3 scripts/prepare_repository.py --output /tmp/nanojev-review
# 可选生成新的本地 ZIP；不会上传，已有目标会被拒绝覆盖
python3 scripts/package_source.py --build --output /tmp/nanojev-source.zip
```

打包不是训练、评估或媒体验收；最终发布使用冻结实验的核验结果和实际浏览器检查，不能用打包成功代替它们。
