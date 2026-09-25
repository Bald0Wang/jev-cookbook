// Prepare a separate development profile for check-chat-live.mjs; never overwrite a profile.
import { mkdir, writeFile, symlink, access } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { installPreset } from './install-preset.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
if (!process.env.DSH_HOME) throw new Error('Set DSH_HOME to a new isolated directory');
const home = resolve(process.env.DSH_HOME);
const profile = resolve(home, 'profiles/jev-live');
try { await access(profile); throw new Error('Profile exists; use another DSH_HOME'); }
catch (e) { if (e.code !== 'ENOENT') throw e; }
const cli = resolve(root, 'node_modules/@deepseek-ai/dsh/lib/bin.js');
const env = { ...process.env, DSH_HOME: home, DSH_TELEMETRY_DISABLED: '1' };
execFileSync(process.execPath, [cli, '--profile', 'jev-live', '--from-default-profile', 'headless', '--dump-config'], { cwd: root, env, stdio: 'pipe' });
await mkdir(resolve(profile, 'node_modules'), { recursive: true });
await symlink(root, resolve(profile, 'node_modules/dsh-jev-decision'), 'dir');
await installPreset(home);
// Follow the locked Web bundle's division between host services and preset tools.
const web = readFileSync(resolve(root, 'node_modules/@deepseek-ai/dsh-web-app/cordis.patch.yml'), 'utf8');
const agentPlane = web.slice(web.indexOf('# ── the agent plane'));
const disabled = [...agentPlane.matchAll(/^- id: ([\w-]+)\n  disabled: true/gm)].map(m => m[1]);
if (!disabled.includes('tool-bash')) throw new Error('Unsupported DSH bundle layout');
disabled.push('session-title-llm', 'session-telemetry-otel', 'llm-retry');
const patch = disabled.map(id => `- id: ${id}\n  disabled: true\n`).join('') + `- id: llm-deepseek
  config:
    apiKeyEnv: DEEPSEEK_API_KEY
    thinking: disabled
    maxTokens: 4096
- insert:
    - id: agent-presets
      name: '@deepseek-ai/dsh-agent-presets'
      config:
        default: jev-decision
`;
await writeFile(resolve(profile, 'cordis.patch.yml'), patch);
execFileSync(process.execPath, [cli, '--profile', 'jev-live', '--help'], { cwd: root, env, stdio: 'pipe' });
console.log(`Prepared ${profile}. Run scripts/check-chat-live.mjs (plain headless does not mount presets).`);
