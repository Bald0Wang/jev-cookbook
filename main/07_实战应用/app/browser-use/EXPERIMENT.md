# 浏览器智能体（Jev Ultrafast）验证测试报告 · 原作者 browser-use（MIT），提取收录

## 1. 这是什么

自然语言目标的浏览器智能体：TypeSafe Jev 每次只做「选哪个操作 + 选哪个元素」两个 Choice（一次往返），**不生成代码**——输出永远是元素索引。原项目 12,748 star，README 实测「Google Flights 7.1 秒」。

## 2. 实验意义

把网页控制从「写脚本/生成代码」改成「在可见动作里做选择题」：选择器、坐标、shell 命令、可执行 JS 都被禁止——限权与校验天然成立。这是判断模型在 Agent 工具执行层最干净的用法。

## 3. 要回答的问题（本轮验证）

1. 21 项浏览器守卫回归（新鲜度/失效判定/原生控件）在本机能否通过？
2. 真 Jev 能否在本地 travel 夹具上完成完整目标（搜索 → Design → Free cancellation → Casa Flora）？

## 4. 实验怎么做的

两步：`scripts/check_guards.py`（21 项守卫，**零模型调用**）+ `scripts/smoke.py --max-actions 6`（本地 fixture 8766 + 真 Jev API + StepFun 作 TYPE_TEXT 文本模型，文本助手仅在 TYPE_TEXT 时使用）。

## 5. Jev 每一步怎么工作

一次请求两个 Choice：`operation`（CLICK/TYPE_TEXT/SELECT/SCROLL/WAIT/DONE/BLOCKED）与一个**推测式**目标头（`click_target` 等的前提里显式写"假设下一步是 CLICK"——两个决策一次往返，第 3 章扇出模式的微缩版）。执行器只消费被选中的目标头。

## 6. 实验结果与说明

- **守卫回归：21 项全过**（`figures/guards-cli.png`）：移动目标命中当前位置、视口外无关文本不失效、下拉选项失效、遮罩拦截、表单值失效动作特定守卫、原生控件只暴露受支持操作、真实文本输入等待异步建议、导航失效旧文档……
- **Live smoke：6 次决策 / 5 步动作 / verified: true**，轨迹完全命中目标：Destination → Find stays → Stay category→Design → Free cancellation → View Casa Flora；步延迟 1879→3647ms（含页面加载等待）；完整 trace 存 `figures/smoke-trace/`（state.json + summary.json）。

## 7. 成本与耗时

6 次决策 × ~700 token ≈ 4.2K token ≈ **$0.0002**；全程 3.65s（夹具页；原站真实航班 7.1s）。

## 8. 结论与后续

两层验证全绿：确定性守卫（不发请求）+ 真 Jev 端到端（含文本模型协作）。TYPE_TEXT 依赖 `TEXT_MODEL_API_KEY`（OpenAI 兼容即可，本机用 StepFun turbo）——**判断与文本生成各用各的模型**在这套代码里是硬约束，不是建议。后续可跑 `measure_flights.py` 复现 7.1s 官方数字。
