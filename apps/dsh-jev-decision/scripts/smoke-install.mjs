import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const run = promisify(execFile);
const root = fileURLToPath(new URL('../', import.meta.url));
const temporary = await mkdtemp(join(tmpdir(), 'dsh-jev-install-'));
const home = join(temporary, 'home');
const cli = join(root, 'node_modules/@deepseek-ai/dsh/lib/bin.js');
const env = { ...process.env, DSH_HOME: home, JEV_DECISION_MODE: 'mock', DSH_TELEMETRY_DISABLED: '1' };
delete env.TYPESAFE_API_KEY;
delete env.DEEPSEEK_API_KEY;
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const command = (file, args) => run(file, args, { cwd: root, env, timeout: 180000, maxBuffer: 4 * 1024 * 1024 });
const dsh = args => command(process.execPath, [cli, ...args]);
try {
  console.log('1/5 打包预编译产物（临时目录）');
  const packed = await command(npm, ['pack', '--ignore-scripts', '--json', '--cache', join(temporary, 'npm-cache'), '--pack-destination', temporary]);
  const info = JSON.parse(packed.stdout)[0];
  for (const file of ['dist/index.js', 'dist/mode.js', 'cordis.patch.yml', 'presets/jev-decision/agent.cordis.yml', 'scripts/install-preset.mjs', 'scripts/check-live.mjs', 'examples/three-primitives.json', 'examples/routing-cases.json', 'examples/chat-workspace/date.mjs', 'docs/ACCEPTANCE.md']) {
    assert(info.files.some(item => item.path === file), `安装包缺少 ${file}`);
  }
  console.log('2/5 初始化 DSH web profile 并通过官方 plugin add 安装');
  await dsh(['--profile', 'jev-smoke', '--from-default-profile', 'web', '--dump-config']);
  await dsh(['plugin', '--profile', 'jev-smoke', 'add', join(temporary, info.filename), '--ignore-scripts', '--store-dir', join(temporary, 'pnpm-store')]);
  console.log('3/5 校验 bundle 合成配置与已安装的模式复制脚本');
  const dumped = await dsh(['--profile', 'jev-smoke', '--dump-config']);
  assert.match(dumped.stdout, /name: dsh-jev-decision/);
  const profile = join(home, 'profiles/jev-smoke');
  const manifest = JSON.parse(await readFile(join(profile, 'package.json'), 'utf8'));
  assert(manifest.dsh.profile.bundles.includes('dsh-jev-decision'));
  await command(process.execPath, [join(profile, 'node_modules/dsh-jev-decision/scripts/install-preset.mjs'), '--home', home]);
  console.log('4/5 通过 Web 帮助入口完成 DSH 首次启动和宿主依赖链接');
  const help = await dsh(['--profile', 'jev-smoke', '--help']);
  assert.match(help.stdout, /Serve the DeepSeek Harness browser UI/);
  console.log('5/5 启动发布版 core，实际发现、挂载预设并执行安装包工具');
  const verified = await command(process.execPath, [join(root, 'scripts/verify-profile.mjs')]);
  process.stdout.write(verified.stdout);
  console.log('PASS: DSH 官方安装流程、预设与运行时集成验收完成；未调用付费 API。');
} catch (error) {
  console.error(error.stderr || error.message);
  process.exitCode = 1;
} finally { await rm(temporary, { recursive: true, force: true }); }
