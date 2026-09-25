# V3 导航输入边界：独立源码补审查

本次只读审查 `build_navigation_v3.py`、`assemble_navigation_v3_views.py`、`evaluate_navigation_v3.py`、`train_pipeline_decisions.py` 和 `predict_toy_decisions.py`。没有运行学生、训练或 API。审查版本的文件 SHA256 及实际 CPU 检查见 [navigation_v3_source_audit.json](navigation_v3_source_audit.json)；较早两例检查保留在 [navigation_v3_input_audit.json](navigation_v3_input_audit.json)，未覆盖或更改。

结论是：**所审版本的两个 renderer 都只把地图几何、题目与合法候选交给学生；没有把 BFS 距离或最优动作写进输入。** 这不证明学生已学会寻路，也不代替全数据分区或真实闭环评测。

实际 CPU 检查使用三个手写状态，包含普通障碍、需要绕路的几何和不可达目标，分别渲染 ASCII 与坐标表示，共六例。检查时将可见模块内的 `solve`、`grid_distances` 替换为立即报错函数，所有 renderer 仍成功。额外向状态注入 oracle、distance、reachable 字段后，输出逐字不变。坐标候选的 destination 与一步合法 `step` 相同；ASCII 候选只写方向，没有坐标或答案。保存的是检查摘要和公开输入哈希，不包含私有训练标签。

源码边界如下：

- `make_record` 先渲染公开输入，再单独求解并写 `gold`、`gold_probs` 与 metadata。求解器提供监督，不进入文字状态。
- `load_training_examples` 传给 `prepare_examples` 的字段只有 `id/state/questions`；target、source 和审计 metadata 在 token 输入准备后附加。推理 API 也拒绝这三个字段之外的状态项。
- V3 学生控制器检查 renderer 仅返回 `state/questions`，随后组成学生请求。唯一合法动作直接执行，单列 `forced_legal_action`，不算学生决定。
- greedy 使用学生原概率的 argmax；sample 使用原概率的 `T=1` 分类采样。真正执行动作保存在 `step.action`，另保留 `distribution_argmax` 和原始 answers；二者可能不同，阅读页不应互相覆盖。
- rollout 进程确实会调用 BFS 验证初始地图、计算评测指标，独立 oracle 基线也使用 BFS。学生分支没有依据这些指标替换动作；应表述为“BFS 不参与学生动作选择”，不能夸成整个评测进程从不调用 BFS。
- CPU oracle 控制流测试有单独的 `validation_engine`/actor 标识且 forward 为零，不能算作真实模型成绩。

一个非阻断观察：`HEADERS` 会把 split 名写进状态标题，坐标和 ASCII 两种表示均保留它。这不是答案泄漏，但会额外改变输入表述，应如实说明；不能等测试结果出来后仅修改测试标题再当作原协议成绩。

本审查只覆盖三个手写状态和记录的代码版本。全部地图独立性、实际训练起点、曝光次数、checkpoint 选择以及各控制器结果，应分别由冻结数据协议、训练日志和真实评测产物证明；后续代码变化也不能自动继承本次 SHA 对应的结论。
