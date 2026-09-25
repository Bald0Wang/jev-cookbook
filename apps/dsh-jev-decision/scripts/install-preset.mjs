import { mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { realpathSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';

const source = fileURLToPath(new URL('../presets/jev-decision/', import.meta.url));

/** DSH 0.1.5-rc.2 的本地 preset 目录；已存在时拒绝覆盖。 */
export async function installPreset(home) {
  const expanded = home === '~' ? homedir() : home.startsWith('~/') ? join(homedir(), home.slice(2)) : home;
  const root = join(resolve(expanded), '.agent-presets');
  const target = join(root, 'jev-decision');
  const files = await Promise.all(['agent.cordis.yml', 'preset.yml'].map(async name => ({
    name, data: await readFile(join(source, name)),
  })));
  await mkdir(root, { recursive: true });
  // 独占建目录，确保失败清理只能影响本次新建的目录。
  try { await mkdir(target); }
  catch (error) {
    if (error.code === 'EEXIST') throw new Error(`已有模式，未覆盖：${target}。请先备份并手动移走旧目录。`);
    throw error;
  }
  try {
    for (const file of files) await writeFile(join(target, file.name), file.data, { flag: 'wx' });
  } catch (error) {
    await rm(target, { recursive: true, force: true });
    throw error;
  }
  return target;
}

if (process.argv[1] && realpathSync(fileURLToPath(import.meta.url)) === realpathSync(process.argv[1])) {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log('node scripts/install-preset.mjs [--home <DSH_HOME>]\n仅复制 Jev 模式；先在相同 DSH_HOME 的目标 profile 安装插件。默认读取 DSH_HOME，否则 ~/.dsh。');
  } else {
    try {
      if (args.length && (args.length !== 2 || args[0] !== '--home' || !args[1].trim())) {
        throw new Error('用法：node scripts/install-preset.mjs [--home <DSH_HOME>]');
      }
      const home = args[1] ?? (process.env.DSH_HOME?.trim() ? process.env.DSH_HOME : join(homedir(), '.dsh'));
      console.log(`已安装 Jev 决策协作模式：${await installPreset(home)}`);
      console.log('重启 DSH，在新会话的模式选择器中选择“Jev 决策协作”。');
    } catch (error) { console.error(error.message); process.exitCode = 1; }
  }
}
