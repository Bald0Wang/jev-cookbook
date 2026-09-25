// 由 smoke-install 在独立进程调用，避免污染开发终端或其他 DSH 实例。
import assert from 'node:assert/strict';
import { resolve, join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import { boot, loadOverlayPatches } from '@deepseek-ai/dsh-app-boot';
import { createScope } from '@deepseek-ai/dsh-scope';
import { discoverPresets, mountPreset } from '@deepseek-ai/dsh-agent-presets';

const home = process.env.DSH_HOME;
assert(home, '此脚本须由 test:install 提供隔离 DSH_HOME');
assert.equal(process.env.JEV_DECISION_MODE, 'mock');
globalThis.fetch = () => { throw new Error('安装验收不允许调用任何模型接口'); };
const profile = join(home, 'profiles', 'jev-smoke');
const installed = join(profile, 'node_modules', 'dsh-jev-decision');
const baseManifest = fileURLToPath(import.meta.resolve('@deepseek-ai/dsh-base/package.json'));
const presets = await discoverPresets([{ path: join(home, '.agent-presets'), trust: 'user' }], pathToFileURL(profile + '/').href);
const preset = presets.find(p => p.id === 'jev-decision');
assert(preset, 'DSH 应能发现 Jev 模式');
assert.equal(preset.broken, undefined);

// 实际发布版的完整 core 配方 + 已安装 bundle；不启动网页或聊天主模型。
const ctx = await boot('jev-smoke', join(profile, 'cordis.yml'), [
  ...loadOverlayPatches('jev-smoke', resolve(baseManifest, '..', 'cordis.patch.yml')),
  ...loadOverlayPatches('jev-smoke', join(installed, 'cordis.patch.yml')),
  { id: 'session-telemetry-otel', disabled: true },
]);
const key = {};
const scope = createScope(ctx, key);
try {
  await mountPreset(scope.ctx, preset);
  const assembly = await ctx.systemPrompt.assemble({ scope: key });
  assert.equal(assembly.sections.filter(s => s.name === 'jev-decision-mode').length, 1);
  for (const name of ['jev_decide', 'jev_route_task']) {
    assert.equal(ctx.tools.schemas(key).filter(t => t.name === name).length, 1);
  }
  const fixture = JSON.parse(await readFile(join(installed, 'examples', 'three-primitives.json'), 'utf8'));
  const result = await ctx.tools.execute({
    callId: 'packaged-tool-smoke', name: 'jev_decide', arguments: fixture,
    signal: new AbortController().signal,
  });
  assert.equal(result.isError, false, JSON.stringify(result));
  assert.equal(result.value.source, 'mock_fixture');
  assert.equal(result.value.status, 'ok');
  assert.equal(result.value.answers.category.type, 'choice');
  assert.equal(result.value.answers.is_actionable.type, 'noul');
  assert.equal(result.value.answers.complexity.type, 'score');
  console.log('PASS: 预设发现、完整 core 下的预设挂载、模式提示和已安装工具执行');
} finally { await scope.dispose(); await ctx.fiber.dispose(); }
