import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, symlink } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createScope } from '@deepseek-ai/dsh-scope';
import { createHarness } from '../scripts/harness.mjs';
import { installPreset } from '../scripts/install-preset.mjs';
import * as decision from '../dist/index.js';
import * as mode from '../dist/mode.js';
import { DEMO_CASES, mockResponse } from '../dist/mock.js';
import { ROUTER_QUESTIONS, recommend } from '../dist/router.js';

test('DSH 原生注册、Schema、三条分流、渲染值、模式提示及卸载清理', async () => {
  const harness = await createHarness();
  try {
    assert.deepEqual(harness.ctx.tools.schemas().map(t => t.name), ['jev_decide', 'jev_route_task']);
    for (const example of DEMO_CASES) {
      const result = await harness.execute('jev_route_task', { task: example.task });
      assert.equal(result.isError, false);
      assert.equal(result.value.recommendation.action, example.expected);
      assert.equal(result.value.source, 'mock_fixture');
      assert.deepEqual(JSON.parse(result.content[0].text), result.value);
    }
    const invalid = await harness.execute('jev_route_task', { task: ' ' });
    assert.equal(invalid.value.status, 'error');
    assert.equal(invalid.value.action, 'error');
    const badType = await harness.execute('jev_route_task', { task: 42 });
    assert.equal(badType.isError, true);
    const assembled = await harness.ctx.systemPrompt.assemble();
    assert(assembled.sections.some(s => s.name === 'jev-decision-mode'));
    await harness.toolsFiber.dispose();
    await harness.modeFiber.dispose();
    assert.equal(harness.ctx.tools.schemas().length, 0);
    assert.equal((await harness.ctx.systemPrompt.assemble()).sections.some(s => s.name === 'jev-decision-mode'), false);
  } finally { await harness.dispose(); }
});

test('DSH 宿主已有同名工具时，preset 作用域可覆盖并独立卸载', async () => {
  const harness = await createHarness();
  const key = {};
  const scope = createScope(harness.ctx, key);
  try {
    await scope.ctx.plugin(decision, { mode: 'mock' }).await();
    await scope.ctx.plugin(mode).await();
    assert.equal(harness.ctx.tools.schemas(key).length, 2);
    const assembly = await harness.ctx.systemPrompt.assemble({ scope: key });
    assert.equal(assembly.sections.filter(s => s.name === 'jev-decision-mode').length, 1);
    await scope.dispose();
    assert.equal(harness.ctx.tools.schemas().length, 2);
  } finally { await scope.dispose(); await harness.dispose(); }
});

test('DSH 执行前策略仍能拒绝 Jev 工具，插件不绕过宿主', async () => {
  const harness = await createHarness();
  try {
    harness.ctx.on('tools/pre-execute', async () => ({ kind: 'deny', reason: '测试策略拒绝' }));
    const result = await harness.execute('jev_route_task', { task: DEMO_CASES[0].task });
    assert.equal(result.isError, true);
    assert.equal(Object.hasOwn(result, 'value'), false);
  } finally { await harness.dispose(); }
});

test('DSH 中的 live 失败不产生 proceed 或 mock 结果', async () => {
  const original = process.env.TYPESAFE_API_KEY;
  delete process.env.TYPESAFE_API_KEY;
  const harness = await createHarness({ mode: 'live' });
  try {
    const result = await harness.execute('jev_route_task', { task: DEMO_CASES[0].task });
    assert.equal(result.value.status, 'error');
    assert.equal(result.value.action, 'error');
    assert.equal(result.value.source, 'typesafe_api');
    assert.equal(result.value.request_attempted, false);
    assert.equal(Object.hasOwn(result.value, 'recommendation'), false);
  } finally {
    await harness.dispose();
    if (original === undefined) delete process.env.TYPESAFE_API_KEY;
    else process.env.TYPESAFE_API_KEY = original;
  }
});

test('分流阈值边界与低置信度不会越过 review', () => {
  const response = mockResponse({ task: DEMO_CASES[0].task }, ROUTER_QUESTIONS);
  response.answers.needs_clarification.noul = 0.2;
  response.answers.category.confidence = 0.8;
  assert.equal(recommend(response).action, 'proceed');
  response.answers.needs_clarification.noul = 0.2001;
  assert.equal(recommend(response).action, 'review');
  response.answers.needs_clarification.noul = 0.8;
  assert.equal(recommend(response).action, 'clarify');
  response.answers.needs_clarification.noul = 0.1;
  response.answers.category.confidence = 0.799;
  assert.equal(recommend(response).action, 'review');
  response.answers.category.confidence = 0.99;
  response.answers.category.choice = 'other';
  assert.equal(recommend(response).action, 'review');
});

test('preset 复制到正确目录，拒绝覆盖且保留原文件', async () => {
  const root = await mkdtemp(join(tmpdir(), 'jev-preset-test-'));
  try {
    const target = await installPreset(root);
    assert.equal(target, join(root, '.agent-presets', 'jev-decision'));
    const before = await readFile(join(target, 'agent.cordis.yml'), 'utf8');
    assert.match(before, /name: dsh-jev-decision\/mode/);
    await assert.rejects(installPreset(root), /未覆盖/);
    assert.equal(await readFile(join(target, 'agent.cordis.yml'), 'utf8'), before);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('模式安装 CLI 经符号链接调用仍执行（覆盖 macOS /var 与 /private/var）', async () => {
  const root = await mkdtemp(join(tmpdir(), 'jev-preset-cli-'));
  try {
    const entry = join(root, 'linked-installer.mjs');
    await symlink(fileURLToPath(new URL('../scripts/install-preset.mjs', import.meta.url)), entry);
    const output = execFileSync(process.execPath, [entry, '--home', root], { encoding: 'utf8' });
    assert.match(output, /已安装/);
    assert.match(await readFile(join(root, '.agent-presets/jev-decision/preset.yml'), 'utf8'), /Jev 决策协作/);
  } finally { await rm(root, { recursive: true, force: true }); }
});
