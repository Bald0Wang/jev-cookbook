import { Context } from '@deepseek-ai/cordis';
import { SystemPrompt } from '@deepseek-ai/dsh-system-prompt';
import { ToolRuntime } from '@deepseek-ai/dsh-tools';
import * as decision from '../dist/index.js';
import * as mode from '../dist/mode.js';

/** 使用实际 DSH 服务；这里只省略主模型和界面。 */
export async function createHarness(config = { mode: 'mock' }) {
  const ctx = new Context();
  try {
    await ctx.plugin(SystemPrompt, {}).await();
    await ctx.plugin(ToolRuntime, {}).await();
    const toolsFiber = await ctx.plugin(decision, config).await();
    const modeFiber = await ctx.plugin(mode).await();
    let sequence = 0;
    return {
      ctx, toolsFiber, modeFiber,
      execute(name, args, signal = new AbortController().signal) {
        return ctx.tools.execute({ callId: `jev-demo-${++sequence}`, name, arguments: args, signal });
      },
      dispose: () => ctx.fiber.dispose(),
    };
  } catch (error) {
    await ctx.fiber.dispose();
    throw error;
  }
}
