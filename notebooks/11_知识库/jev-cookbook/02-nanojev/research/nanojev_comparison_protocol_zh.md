# NanoJev 三方闭环对照与 README 视频协议

协议记录日期：2026-09-17。该对照用于 NanoJev 发布演示，不替换、覆盖或重新选择已经冻结的 V2／V3 实验结果。

## 三个系统与解释边界

| 系统 | 固定实现 | 概率含义 |
|---|---|---|
| NanoJev | `v3_teacher_coords_multi_seed17`，沿用冻结 best checkpoint | 训练后动态候选头输出的 T=1 归一化动作分布 |
| Jev | 本次由真实 Jev API 对当前运行状态执行请求 | 原始 native rounded 数值完整保留；必要时仅为动作采样构造归一化 rounded proxy |
| 原始 Qwen | `Qwen/Qwen3-0.6B`，revision `c1899de289a04d12100db370d81485cdf75e47ca`，原生 LM head | 对当前合法动作映射的 A–D token logits 取条件 softmax；不是完整词表概率，也不是原生动作头 |

NanoJev 的固定权重 SHA-256 为 `fff62d1412685c1714eaa386acb603f9690371fb3cc8ad03dc41319302597c28`。该模型与 Jev 输出分布监督路线对应，选择理由是演示该路线；原 V3 的事前主模型仍为 `v3_gold_coords_multi_seed17`，其结果全部保留。

“原始／未训练 Qwen”指已经预训练、但没有接受本任务微调的模型；不是随机权重，也不是附加随机决策头。输入包括相同几何状态、动作问题和全部合法候选，并加入 A–D 选项表达。原始 LM head 与 NanoJev 新决策头、输入编码均不同，因此三方对照是系统对照，不能解释为只改变训练这一因素的因果消融。

三个系统都不生成自然语言或 CoT。Qwen 的 A–D 映射按合法 action ID 的字典序固定，必须保存 token ID、选项 logits、各选项在全词表下的原始概率及全部所提供选项的总概率质量。采样概率为在所提供 A–D token 集合内归一化后的分布；视频中称为“选项条件概率”。

## 冻结环境与控制器

使用原 V3 的 40 个初始状态：test 与 OOD 各按冻结文件顺序取前 20 张不同、可达且非终局的源地图。初始状态集合 SHA-256 固定为：

`1132e0791ccd2f07be1a470f4612dd0f5787fb49077212d7e91a730dab60b4da`

原始 canonical 文件与删除 teacher／oracle 字段的 `eval_minimal` 包可以拥有不同文件 SHA；地图身份、顺序、初始状态及训练地图集合必须逐项相同。两套来源都记录，不用不同序列化哈希掩盖或虚构数据变化。

- 三个系统各执行 greedy 与 T=1 categorical sampling，共 6 份报告、240 局；两个控制器均保留，不仅展示表现较好者。
- greedy 取概率最大动作，相同最大值按 action ID 字典序打破平局。
- sampling 使用 `seed=20260917`。每局 RNG 由 `SHA256(seed, source_map_id, initial_state)` 派生；强制动作不消耗随机数，其他局结束的顺序不能改变本局 RNG 序列。
- 每局固定最多 `2×size²` 步。成功后停止；未成功的局保留到完整 horizon。静态网格可达状态不会在运行中成为无合法动作的孤立状态。
- 只有一个合法动作时直接执行并计为 forced，不调用任一模型。合法候选只根据边界和墙判断；不根据 BFS 最优性过滤。
- 不增加访问惩罚、epsilon、温度调参、循环提前停止、历史轨迹提示或 oracle 回退。
- BFS 只用于确定冻结可达 cohort、评价最优动作和最短路，不进入模型的 state／question／criteria，也不参与学生或 Qwen 的动作选择。
- NanoJev／Qwen 使用多状态批处理；Jev API 的并发 HTTP 请求数量单独记录，不能称为一个跨 state 原生模型 forward。

所有成功和失败均保留。报告完成率、成功路径效率（失败置 0）、步数、强制决策次数、重复访问率、非强制决策的最优动作质量与实际最优动作率。闭环质量受各控制器访问状态分布影响，不把它当作固定同一组状态上的概率能力差。

该比较只有一个训练 checkpoint 和一个控制器采样 seed。若给地图配对 bootstrap，区间只描述固定系统与固定 RNG 下的地图采样不确定性，不覆盖训练或采样 seed 的变化。

## Jev 新状态请求与舍入处理

Jev 对照必须基于本次运行中当前状态的真实 API 请求，不能查询旧 `labeled.jsonl`，也不能把已记录训练标签当作当前状态响应。只允许复用本次对照期间建立、可追溯到真实调用的 exact-input cache：命中键须覆盖发送的 state、完整动作问题、候选及 model ID；缓存命中与其原始请求引用分别记录。这样避免重复访问同一状态时重复计费，同时明确缓存改变的是调用次数，不是已取得的概率。

原生值与采样值分开保存：

1. `native_probs` 必须完整覆盖当前全部合法动作；记录原始值、原始和、模型标识及调用关联。不得静默补齐缺失候选或把 top-k 当作完整分布。
2. 检查所有值为有限数且在 `[0,1]` 内。候选集合错误、负数、非有限数或原始和为 0 时，本次请求无效；不使用均匀分布或 oracle 兜底。失败及明确的重试单独记录，不能按好坏答案择取。
3. 对合法的非单位和响应，动作采样使用 `sampling_probs[a] = native_probs[a] / sum(native_probs)`，并记录 `normalization_applied` 和 `native_sum`。greedy 的排序不因这项归一化改变。
4. 公开结果把 Jev 概率称为“归一化 rounded proxy”。原样 native 数值保留在旁，不把该 proxy 称为服务端未舍入完整概率。浮点求和尾差与明显十进制舍入偏差可分别计数，但不得删除非单位和事实。
5. 视频应分别标明 NanoJev 动作分布、Qwen 选项条件分布、Jev rounded proxy，避免同名柱图隐藏概率来源差异。

最小可审计调用记录包括本次 run ID／开始时间、模型 ID、请求内容 hash、响应内容 hash、是否真实新调用或 exact-input cache hit、可追溯的本次调用关联，以及成功／失败和计费统计。API 密钥、Authorization/header、账户或项目标识、完整供应商响应 envelope 不进入公开报告。公开轨迹只保留自写游戏状态、动作、概率、控制器随机数、最小来源证明和汇总指标。

验证器能证明文件之间的一致性、请求内容匹配及日志来源链，不能仅靠一个本地布尔字段独立证明外部服务确实执行；真实 API 来源还依赖本次工具调用日志与执行脚本。

## 固定视频样例与同步方式

视频使用同一个冻结 cohort 中 test 前 2 例、OOD 前 2 例，不依据任何一方的成功或失败重新挑选：

| 分区／顺序 | episode ID |
|---|---|
| test 1 | `navigation_v3:c53720549630bd7dcd3f803c` |
| test 2 | `navigation_v3:949e76c0d9a26606cb3373b6` |
| OOD 1 | `navigation_v3:06b38a6ade0754de661819ad` |
| OOD 2 | `navigation_v3:e3d96e8974464786ca16801a` |

每例同时呈现 NanoJev、Jev API、原始 Qwen 三列；greedy 和 sampling 可上下两排，或分别制作两段同样四例的合集。画面按环境 step 同步；每列最多推进一步，已经成功的列停在终点并显示完成步数。强制步也计入环境步。不同策略的轨迹长度差异完整显示。

该同步是可视化播放安排，不是延迟竞争；不得使用“谁先抵达视频终点就推理更快”的表述。模型时间、HTTP 延迟、缓存和 GPU 批处理统计如需展示，应另列测量口径。视频正文注明“环境步同步；非延迟对比”。

## GitHub README 媒体方案（官方资料核查）

最稳妥的可克隆方案是将短 GIF 和 H.264 MP4 都作为仓库文件：README 以内联图片引用 GIF，并以普通相对链接提供 MP4。GitHub 官方明确支持 GIF 图片，以及 README 内的相对图片和文件路径；相对路径会按当前分支解析。[非代码文件支持](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files)、[README 相对路径](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)

```markdown
![NanoJev、Jev 与原始 Qwen：环境步同步对照](assets/nanojev-comparison.gif)

[观看高清 MP4](assets/nanojev-comparison.mp4)
```

如果需要原生视频播放器，可使用 GitHub 正式附件上传得到的 URL。官方附件支持 `.mp4`、`.mov`、`.webm`，推荐 H.264；当前 GitHub.com 免费账户视频附件上限为 10 MB，付费账户为 100 MB，图片／GIF 附件为 10 MB。这里是附件上传限制，不应当作所有 Git 仓库文件的统一限制。[GitHub 附件文档](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files)

官方 CLI 附件功能通过 issue／PR／comment 的 `--attach` 上传，要求 push 权限。单独段落中的本地视频图片引用会被 CLI 改写为上传 URL 并呈现播放器；这些文档不能直接证明任意相对 `.mp4` 或自写 `<video>` 标签在仓库 README 中都有相同行为。实际 README 播放器应上传后检查；无需为了演示自动发表无关 issue 或评论。[CLI 附件与视频语法](https://docs.github.com/en/github-cli/github-cli/attaching-files-with-github-cli)

本子任务只提供方案和核验，不修改 README／网页、不注册或上传外部媒体、不发送 issue／评论。

## 新克隆的公开轨迹复核

在仓库根目录使用 Python 3 标准库执行，无需模型权重、GPU、API 密钥或私有数据：

```bash
python3 scripts/verify_nanojev_comparison.py --public-only --output research/public_comparison_check.json
```

该模式读取已发布的六份原始轨迹和 `research/nanojev_comparison_cohort.json`，后者只包含 40 个自写游戏初局、cohort 标识及六份轨迹的冻结 SHA-256，不含教师训练数据。核验器检查源文件 hash、全部 240 局的环境转移、合法动作分布、采样随机数、模型输入重建、嵌入 API receipt 的请求／响应 hash、缓存引用和重算汇总；检查通过后另写指定 JSON，保留原完整审计不变。

公开模式的 `complete=true` 仅表示这些公开证据检查通过。它不读取或重新核验私有 started／succeeded 日志，不重选原始 split 的前 20 张地图，不复核训练地图隔离，也不重新运行权重或独立证明远程服务执行。输出的 `verification_scope` 明列这些边界。它与完整来源可用时生成的 `nanojev_comparison_verification.json` 是两种审计范围，不能互相替代。

发布前已在不含任何 `private_*` 目录及 `.env` 的临时副本中实际执行该命令：240 局通过，六份源文件 hash 和全部重算指标与完整审计一致。将临时副本中的一条采样记录改写后，冻结 hash 检查按预期拒绝；原始发布轨迹未改动。

## README 成功案例展示更新

用户随后要求 README 视频展示 NanoJev 与 Jev 均成功、原始 Qwen 失败的真实案例。新版视频因此使用**按结果筛选的成功案例**，不再采用前文最初的视频四例，也不把这组新案例称为事前固定或预登记的 benchmark 子集。上述“test 前两例、OOD 前两例”只记录原先的视频选择方案；当前 README 视频以本节和 [选择记录](nanojev_showcase_selection.json) 为准。

筛选条件是：同一个冻结初局，在 greedy 和 T=1 sample 两种控制器下，都满足 NanoJev 成功、Jev 成功、原始 Qwen 失败。先完整检查 40 张地图，再分别按原 cohort 顺序，取 test 和 OOD 内最先满足条件的两例。test 有 11/20 例符合，OOD 有 6/20 例符合；两种控制器使用下面同四例。表内步数均为原轨迹的实际环境步，`greedy / sample` 分别列出。

| 分区 | episode ID | NanoJev 成功步数 | Jev 成功步数 | 原始 Qwen 失败步数 |
|---|---|---:|---:|---:|
| test | `navigation_v3:949e76c0d9a26606cb3373b6` | 2 / 4 | 2 / 4 | 32 / 32 |
| test | `navigation_v3:450cb63d0bbd444de9ae877c` | 3 / 3 | 3 / 3 | 32 / 32 |
| OOD | `navigation_v3:06b38a6ade0754de661819ad` | 3 / 3 | 3 / 3 | 72 / 72 |
| OOD | `navigation_v3:53d0165e341321ab56b81c37` | 3 / 3 | 3 / 3 | 72 / 72 |

此次更新只改变展示案例。完整 40 图、六份源轨迹、全部 240 局成功与失败、模型权重、采样 seed、horizon 和汇总成绩均未修改，也没有新增模型或 API 调用。筛选记录保存六份源文件 SHA、全部符合条件的 ID、选中初局及三系统两控制器的实际结果；CPU 重新检查了 240 局环境转移和成功判定。展示子集的完成率不能替代完整评测。视频仍按环境步同步播放，不作延迟比较。
