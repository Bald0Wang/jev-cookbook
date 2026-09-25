import { mkdir, open, readFile } from 'node:fs/promises';
import { realpathSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { createHarness } from './harness.mjs';

// 显式运行才调用真实接口；不会启动聊天主模型，不自动读取 .env。
export async function checkLive({ routes = false, output } = {}) {
  const cases = routes
    ? JSON.parse(await readFile(new URL('../examples/routing-cases.json', import.meta.url), 'utf8')).cases
      .map(({ id, task, context, intended_action }) => ({
        id, tool: 'jev_route_task', arguments: { task, context }, intended_action,
      }))
    : [{ id: 'three-primitives', tool: 'jev_decide', arguments:
      JSON.parse(await readFile(new URL('../examples/three-primitives.json', import.meta.url), 'utf8')) }];
  // 先确保报告可写，避免调用付费接口后才发现文件已存在或目录不可写。
  let file;
  if (output !== undefined) {
    if (!output.trim()) throw new Error('--output 不能为空。');
    const target = resolve(output);
    await mkdir(dirname(target), { recursive: true });
    file = await open(target, 'wx', 0o600);
  }
  const report = {
    schema_version: 1,
    suite: routes ? 'routes' : 'primitives',
    mode: 'live',
    created_at: new Date().toISOString(),
    notice: '固定教学案例的接口联调记录；不是准确率评测，也没有验证 DSH 聊天主模型。预期分支仅供人工比较，不会强制模型输出或因分支不同自动重试。',
    status: 'ok',
    planned_requests: cases.length,
    request_attempts: 0,
    results: [],
    skipped_cases: [],
    chat_verified: false,
  };
  let harness;
  try {
    harness = await createHarness({ mode: 'live' });
    for (const item of cases) {
      const executed = await harness.execute(item.tool, item.arguments);
      const result = executed.isError ? {
        status: 'error', error: { code: 'tool_runtime', message: 'DSH 工具执行失败；未取得有效判断。' },
      } : executed.value;
      report.request_attempts += Number(result.request_attempted === true);
      report.results.push({ ...item, result,
        ...(item.intended_action ? { matches_intended_action: result.status === 'ok'
          ? result.recommendation.action === item.intended_action : null } : {}),
      });
      if (result.status !== 'ok') { report.status = 'error'; break; }
    }
  } catch {
    report.status = 'error';
    report.error = { code: 'check_setup', message: '联调未能完成，请核对依赖、模型配置与运行环境。' };
  } finally {
    try {
      if (harness) await harness.dispose();
    } catch {
      report.status = 'error';
      report.error = { code: 'check_cleanup', message: 'DSH 测试运行时未能正常释放。' };
    }
    report.skipped_cases = cases.slice(report.results.length).map(item => item.id);
    if (file) {
      try { await file.writeFile(JSON.stringify(report, null, 2) + '\n'); }
      finally { await file.close(); }
    }
  }
  return report;
}

if (process.argv[1] && realpathSync(fileURLToPath(import.meta.url)) === realpathSync(process.argv[1])) {
  try {
    const { values } = parseArgs({ options: {
      routes: { type: 'boolean', default: false },
      output: { type: 'string' },
      help: { type: 'boolean', default: false },
    } });
    if (values.help) {
      console.log('node scripts/check-live.mjs [--routes] [--output <新文件.json>]\n默认 1 次通用判断；--routes 最多 3 次任务分流。出错即停止，不重试。\n只读取进程环境；Node 24 可用 node --env-file=.env scripts/check-live.mjs。报告拒绝覆盖已有文件。');
    } else {
      const report = await checkLive(values);
      console.log(JSON.stringify(report, null, 2));
      if (report.status !== 'ok') process.exitCode = 1;
    }
  } catch (error) {
    console.error(error.code === 'EEXIST' ? '报告文件已存在，未覆盖，也未发起请求；请使用新的文件名。'
      : '无法开始联调或保存报告，请检查参数、输出路径与权限。使用 --help 查看用法。');
    process.exitCode = 1;
  }
}
