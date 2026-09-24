import type { Context } from '@deepseek-ai/cordis';
import Schema from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { JevClient, type ClientOptions } from './client.js';
import { recommend, ROUTER_QUESTIONS } from './router.js';

export const name = 'jev-decision';
export const inject = ['tools'];
export interface Config extends ClientOptions { confidenceThreshold?: number }
export const Config: Schema<Config> = Schema.object({
  mode: Schema.union(['live', 'mock']).description('省略时读取 JEV_DECISION_MODE，默认 live。'),
  model: Schema.string().description('省略时读取 TYPESAFE_DEFAULT_MODEL，默认 jev-1.13.0。'),
  timeoutMs: Schema.number().min(100).max(120000).step(1).default(20000),
  maxInputBytes: Schema.number().min(1024).max(262144).step(1).default(65536),
  confidenceThreshold: Schema.number().min(0).max(1).default(0.8),
});

export function apply(ctx: Context, config: Config = {}) {
  const client = new JevClient(config);
  const confidenceThreshold = config.confidenceThreshold ?? 0.8;
  const output = {
    schema: { type: 'json' as const },
    render: (_args: unknown, value: unknown) => [{ type: 'text' as const, text: JSON.stringify(value, null, 2) }],
  };
  ctx.effect(() => ctx.tools.register(defineTool({
    name: 'jev_decide',
    description: '调用 Jev 对给定 state 回答独立的 Choice、Score、Noul 问题。仅发送传入的材料到 TypeSafe。结果标明真实 API 或人工夹具；status=error 时没有有效判断。它不执行其他工具，也不授予权限。',
    parameters: {
      state: { type: 'json', required: true, description: '非空文本、JSON 对象或数组；仅提供本次判断所需的材料。' },
      questions: { type: 'json', required: true, description: '1–16 个问题的映射；type 必须小写 choice、score 或 noul。每题含完整 instructions；choice 的 criteria 为选项描述对象，score 为 2–10 个等级数组，noul 可省略 criteria。例如 {"ready":{"type":"noul","instructions":"材料是否足以完成目标？"}}。问题 ID 不参与推理，判断条件必须写入 instructions。' },
    },
    output,
    timeoutMs: client.timeoutMs,
    isConcurrencySafe: () => true,
    async execute(args, exec) { return client.decide(args.state, args.questions, exec.signal); },
  })));
  ctx.effect(() => ctx.tools.register(defineTool({
    name: 'jev_route_task',
    description: '用 Jev 判断任务类别、核心目标是否需要澄清和复杂度，返回 proceed、clarify 或 review 建议。建议不构成授权，不改变 DSH 权限。失败时 action=error，不能当成允许执行。',
    parameters: {
      task: { type: 'string', required: true, description: '用户的当前任务，保留必要的约束。' },
      context: { type: 'string', description: '已确认的背景；不自动读取文件、历史会话或凭据。' },
    },
    output,
    timeoutMs: client.timeoutMs,
    isConcurrencySafe: () => true,
    async execute(args, exec) {
      const task = args.task.trim();
      if (!task) return { status: 'error', action: 'error', error: {
        code: 'invalid_request', message: 'task 不能为空。', retryable: false,
      }, request_attempted: false, source: client.mode === 'mock' ? 'mock_fixture' : 'typesafe_api' };
      const result = await client.decide({ task, context: args.context ?? '未提供额外背景。' }, ROUTER_QUESTIONS, exec.signal);
      if (result.status === 'error') return { ...result, action: 'error' };
      return { ...result, recommendation: recommend(result, confidenceThreshold) };
    },
  })));
}
