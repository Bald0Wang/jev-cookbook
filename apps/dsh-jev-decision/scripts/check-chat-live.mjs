// Real DSH core + explicitly mounted Jev preset. No mock model or tool transport.
import assert from 'node:assert/strict';
import { randomUUID, createHash } from 'node:crypto';
import { mkdir, open, readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { boot, loadOverlayPatches } from '@deepseek-ai/dsh-app-boot';
import { installModelSelection } from '@deepseek-ai/dsh-agent';
import { createUserMessage } from '@deepseek-ai/dsh-llm';

const { values } = parseArgs({ options: {
  workspace: { type: 'string' }, output: { type: 'string' },
  inspect: { type: 'boolean', default: false },
  case: { type: 'string', default: 'clear' },
} });
const tasks = {
  clear: '请修复仓库中日期解析函数对空字符串的处理，并补一个回归测试。',
  clarify: '帮我把那个东西弄好。',
  review: '看看这份材料，代码和文案方面都处理一下。',
};
assert(tasks[values.case], 'Unsupported case');
assert(values.workspace && values.output && process.env.DSH_HOME, 'Specify workspace, output and DSH_HOME');
if (!values.inspect) assert(process.env.TYPESAFE_API_KEY && process.env.DEEPSEEK_API_KEY, 'Both credentials required');
const root = fileURLToPath(new URL('../', import.meta.url));
const workspace = resolve(values.workspace);
assert(workspace.startsWith(root + '.demo-workspace-'), 'Use an isolated sample directory');
const original = await readFile(resolve(workspace, 'date.mjs'), 'utf8');
await mkdir(dirname(resolve(values.output)), { recursive: true });
const reportFile = await open(resolve(values.output), 'wx', 0o600);
const report = { mode: values.inspect ? 'inspect' : 'live', case: values.case,
  created_at: new Date().toISOString(), status: 'error', workspace,
  plugin_version: JSON.parse(await readFile(resolve(root, 'package.json'), 'utf8')).version,
  mode_sha256: createHash('sha256').update(await readFile(resolve(root, 'dist/mode.js'))).digest('hex'),
  entry: 'DSH core API with explicit agentPresets.mount; browser UI not exercised',
  scripted_answers: [], events: [] };
let ctx, handle, timer;
function redact(value) {
  let result = JSON.stringify(value, null, 2);
  for (const key of [process.env.TYPESAFE_API_KEY, process.env.DEEPSEEK_API_KEY]) {
    if (key) result = result.replaceAll(key, '[REDACTED]');
  }
  return result;
}
try {
  process.chdir(workspace);
  const profile = resolve(process.env.DSH_HOME, 'profiles/jev-live');
  const base = dirname(fileURLToPath(import.meta.resolve('@deepseek-ai/dsh-base/package.json')));
  ctx = await boot('jev-chat-check', resolve(profile, 'cordis.yml'), [
    ...loadOverlayPatches('jev-chat-check', resolve(base, 'cordis.patch.yml')),
    ...loadOverlayPatches('jev-chat-check', resolve(profile, 'cordis.patch.yml')),
  ]);
  const selection = ctx.agentDefaultModel.currentSelection();
  handle = await ctx.agents.create({
    sessionId: `session-${randomUUID()}`,
    meta: { cwd: workspace, agentPreset: 'jev-decision' },
    agentOptions: { ...selection, maxTokens: 4096 },
    setup: async (agentCtx) => {
      installModelSelection(agentCtx, { current: selection, assembled: undefined });
      await ctx.agentPresets.mount(agentCtx, 'jev-decision');
    },
  });
  const { agent } = handle;
  report.session_id = agent.id;
  report.model_selection = selection;
  report.preset = ctx.agentPresets.composedPreset(agent.ctx);
  assert.equal(report.preset, 'jev-decision');
  // Assemble through the agent's scope, matching the model request path.
  const assembly = await agent.ctx.systemPrompt.assemble({ scope: agent });
  report.mode_prompt_present = assembly.sections.some(s => s.name === 'jev-decision-mode');
  report.tools = ctx.tools.schemas(agent).map(t => t.name);
  assert(report.mode_prompt_present, 'Jev instructions not mounted');
  assert(report.tools.includes('jev_route_task'), 'Jev tool not mounted');
  if (values.inspect) {
    report.status = 'ok';
  } else {
    const answer = '是当前目录的 parseDate 函数。空字符串应返回 null，正常 ISO 日期行为保持不变，请补测试。';
    agent.ctx.on('user-questions/request', async (request, next) => {
      if (values.case !== 'clarify') return next();
      report.scripted_answers.push({ questions: request.questions, answer,
        source_changed_before_answer: (await readFile(resolve(workspace, 'date.mjs'), 'utf8')) !== original });
      return { answers: request.questions.map(q => ({ id: q.id, selected: [], custom: answer })) };
    });
    timer = setTimeout(() => { report.timed_out = true; agent.cancel({ kind: 'disposed' }); }, 180000);
    const send = async text => {
      agent.followup(createUserMessage({ content: [{ type: 'text', text }], source: { kind: 'user' } }));
      await agent.whenIdle();
    };
    await send(tasks[values.case]);
    const firstTurnEvents = agent.session.snapshotEvents();
    const lastText = firstTurnEvents.filter(e => e.type === 'assistant/message').at(-1)
      ?.data.message.content.filter(b => b.type === 'text').map(b => b.text).join('\n') ?? '';
    report.clarification_observed = report.scripted_answers.length > 0 ||
      ((/[?？]/.test(lastText) || /请.*(告诉|说明|指定|提供)/.test(lastText)) &&
        /(哪个|什么|具体|哪一|哪份|指的|哪段|which|what|clarif)/i.test(lastText));
    report.changed_before_scripted_followup = !report.scripted_answers.length &&
      (await readFile(resolve(workspace, 'date.mjs'), 'utf8')) !== original;
    if (values.case === 'clarify' && report.clarification_observed && !report.scripted_answers.length && !report.timed_out) {
      report.scripted_answers.push({ followup: answer });
      await send(answer);
    }
    await ctx.sessions.flush(agent.session);
    report.events = agent.session.snapshotEvents();
    report.source_changed = (await readFile(resolve(workspace, 'date.mjs'), 'utf8')) !== original;
    // Preserve raw events; completion is assessed from tool calls, test results and files.
    report.status = report.timed_out ? 'timeout' : 'captured';
  }
} catch (error) {
  report.error = { name: error.name, message: error.message };
  process.exitCode = 1;
} finally {
  clearTimeout(timer);
  if (handle) await handle.dispose();
  if (ctx) await ctx.fiber.dispose();
  await reportFile.writeFile(redact(report) + '\n');
  await reportFile.close();
}
console.log(redact({ ...report, events: `${report.events.length} events saved` }));
