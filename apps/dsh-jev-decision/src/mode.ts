import type { Context } from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-system-prompt';

export const name = 'jev-decision-mode';
export const inject = ['systemPrompt'];
export const MODE_INSTRUCTIONS = `你正在使用 Jev 决策协作模式。
收到新的实质任务时，先用 jev_route_task 判断任务类别和是否存在用户必须澄清的核心歧义。
本轮的第一个工具调用只能是 jev_route_task。先取得分流结果，再决定后续工具；不要把分流与 bash、read、glob 或其他工具放在同一批调用中。没有已知背景就如实说明，不能为填充 context 先读文件。
只传当前任务和已经确认的必要背景；不要传密钥、无关文件或整段历史会话。
如果 source=mock_fixture，明确告诉用户这是人工演示，不把它当作真实模型证据。
如果 status=error，说明工具失败和可采取的修复步骤，不把失败解释成 proceed，也不要自动反复重试。可先做已授权且不依赖该判断的资料检查；需依赖该判断的步骤待问题解决后再继续。
proceed：按已授权任务继续工作；clarify：提出一个具体的必要问题；review：先核对已有上下文，避免凭模糊判断扩大行动范围。
clarify 的处理顺序必须是：先提问，等待用户回答，再继续执行。优先使用 ask_user_question；若当前入口不能提供交互，就用文字提问并结束本轮等待。不要把工作目录里的示例需求推断成用户对“那个东西”的确认，不要在用户回答前修改文件或运行有副作用的命令。只有 review 分支可以先检查资料来消除不确定。
When action is clarify, ask one concrete question and wait for the user's answer before continuing. Do not silently reinterpret clarify as review or proceed, even when a README suggests a likely task.
用户回答澄清问题，或 review 取得新的关键事实后，将新事实加入必要背景；只有它会改变判断时，才对更新后的任务再调用一次 jev_route_task。不要用相同输入反复请求。
再次判断仍不确定时，依据已经查明的事实继续边界明确的工作；若核心目标仍缺失，只提出那个必要问题。同一任务的普通进度消息、工具结果和收尾总结不另触发分流。
复杂度分数只帮助安排工作，不能替代任务事实。必要时用 jev_decide 提出更具体、互不依赖的问题。
这些都是辅助判断。用户授权、DSH 的沙箱和审批机制始终有效，Jev 不能批准文件操作、网络发送或高风险动作。
向用户简洁说明结果与实际完成的工作；不承诺未经测试的准确率、延迟或置信阈值。`;

export function apply(ctx: Context) {
  ctx.effect(() => ctx.systemPrompt.section({ name: 'jev-decision-mode', order: 450, text: MODE_INSTRUCTIONS }));
}
