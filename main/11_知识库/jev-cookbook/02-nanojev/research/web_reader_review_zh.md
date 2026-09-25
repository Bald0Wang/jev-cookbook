# OpenJev 阅读页实际浏览器验收

2026-09-17。本文记录历史版本的浏览器验收；当时的截图和部分浏览器检查记录保留在本地，未随仓库发布。当前三方可视化见 [greedy 回放](../assets/comparison_greedy.mp4) 与 [采样回放](../assets/comparison_sample.mp4)。页面在 `web/`，无前端框架、第三方脚本或 CDN。数据来自主任务生成的真实 `demo_results.json`，不是 UI 内嵌成功样本。

验证使用临时目录安装的 Playwright 与本机 Chrome `153.0.8010.48`，新建隔离无登录上下文，没有读取用户 Chrome profile。测试 HTTP 服务只暴露 `web/`，没有读取 `.env`、访问私有站点或调用教师 API。

首轮真实 artifact 有 4 个模型/基线、每个 80 局，共 320 局。实际检查包括：

- 模型与对局切换；每个模型各抽查网格、井字棋一局。
- 格子数、初始与后续步骤 JSON、前后步进、最终 `next_state` 与记录逐项相同。
- 自动播放、暂停、速度切换、进度条和终局边界。
- 两个学生各自真实 `parallel_batches` 的状态数、完整 JSON 和 forward 次数；首批为 80 states、240 questions、1 次 forward，BF16。
- 390px 窄屏没有横向溢出；桌面和手机截图已目视检查。
- 缺失文件、错误 schema、非法请求 JSON、静态服务缺少实时 API 都有明确提示，没有预设结果。

浏览器 `pageerror=0`。这不是对全部 320 局每一帧的穷尽验收。

随后通过 `http://127.0.0.1:18766` 的现有 SSH 隧道，使用同一隔离 Chrome 页面向 GPU 学生服务发送了一次真实 POST。输入取公开 `parallel_example_v2.json` 的前三个业务状态，移除参考 answers，只保留 id/state/questions。实际响应为 3 states、9 questions、21 candidate paths、1 次 forward、0 decode、0 网络模型调用；persistent load count=1、call index=3。UI 的答案和原始 JSON 与 HTTP 200 返回逐项相同，pageerror=0。

该次浏览器往返约 132 ms，服务自身计时约 66.7 ms；单次观察不当作 p50 或硬延迟承诺。没有重新启动或停止 GPU 服务，没有 oracle/teacher fallback。证据：[实时检查](web_live_browser_check.json)、[真实请求与响应](web_live_browser_response.json)。

公开证据：[空状态检查 JSON](web_empty_browser_check.json)。真实 artifact 的历史检查 JSON 另存本地。

当时截图已检查的内容（历史截图未随仓库发布）：

- 网格：首个学生失败轨迹：顶部保留该学生 TEST 10%、OOD 5% 到达率，整局结果为达到 32 步上限。
- 井字棋：显示真实四候选概率及选中格。
- 并行概率：显示同批状态、Choice/Boolean/Score 和实际 1 次 forward 证据。
- 手机窄屏。

界面区分回放与可选实时接口，区分学生、对手与唯一合法动作；概率缺失时不补 one-hot，概率和偏差不静默归一化。完整 summary/cohort、当前步骤与批次 JSON 可展开复核。来源区说明自写游戏受官方 Jev 演示启发，不声称是其 Doom 同款或 RLCD 内部算法。

## V3 整合后的实际浏览器验收

随后对完整 V3+V2 artifact 重新使用同一隔离 Chrome 验收：16 个模型/控制器/基线展示项、800 局。这里并非 16 个独立训练模型：同 checkpoint 的 greedy/sample 分开显示，旧 V2 历史记录仍保留。全部展示项的对局数量、首步原始记录和 summary/cohort 标记与真实 JSON 对应；V3 的 `test/ood` 与 V2 的 `split/game` 按不同结构显示，页面明确两版地图不同。

初次载入默认预登记的 V3 gold coords_multi greedy；通过 `source_artifact` 或模型名识别，不按测试成绩选项。刷新后保留用户选择。概率条以实际 `step.action` 高亮，另列 `distribution_argmax` 与采样随机数。

已实际核对的非 argmax 采样步骤：`navigation_v3:c53720549630bd7dcd3f803c` 的第 0 步，原概率 east=0.3979384005、north=0.6020615697，随机数 0.2545104737，实际动作 east；页面金色标记 east，argmax 仍为 north。主模型首个 OOD 失败 `navigation_v3:e3d96e8974464786ca16801a` 也保留，棋盘顶角明确显示达到步数上限。没有为了截图替换轨迹或改变控制器。

首个并行批次为真实 6 states / 18 questions / 44 candidate paths / 1 forward，0 decode、0 网络模型调用。该独立捕获可以附在同权重的两种控制器下，不称作新发生的闭环批次。390px 窄屏没有横向溢出；JavaScript pageerror=0。验收覆盖全部展示项的摘要和首步，加主组的实际采样、失败、前后步进及并行批次；没有逐帧穷尽所有 800 局。

V3 历史浏览器检查记录与截图另存本地，内容包括主组 OOD 失败、实际非 argmax 采样、并行概率、手机页面。检查记录保留实际 artifact SHA256；后续结果文件变化不能自动沿用该哈希的验证。

最后通过已切换到预定主 V3 gold coords_multi checkpoint 的真实 GPU 服务，再完成一次隔离 Chrome POST。请求为三个业务状态，响应 3 states / 9 questions / 21 paths / 1 forward，0 decode、0 网络模型调用，persistent load count=1、call index=3。HTTP 200，页面答案与完整响应逐项一致，pageerror=0。浏览器往返约 130 ms，服务本次计时约 65.7 ms；仅为一次观察，不当作延迟分位数。响应记录的 checkpoint 目录为 `runs/v3_gold_coords_multi_seed17`，没有教师或预设答案兜底。证据：[V3 实时检查](web_v3_live_browser_check.json)、[实际请求/响应](web_v3_live_browser_response.json)。
