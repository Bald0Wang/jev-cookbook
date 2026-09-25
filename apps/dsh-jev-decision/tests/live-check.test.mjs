import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { checkLive } from '../scripts/check-live.mjs';
import { mockResponse } from '../dist/mock.js';

const originalFetch = globalThis.fetch;
const originalKey = process.env.TYPESAFE_API_KEY;
const originalModel = process.env.TYPESAFE_DEFAULT_MODEL;
afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalKey === undefined) delete process.env.TYPESAFE_API_KEY;
  else process.env.TYPESAFE_API_KEY = originalKey;
  if (originalModel === undefined) delete process.env.TYPESAFE_DEFAULT_MODEL;
  else process.env.TYPESAFE_DEFAULT_MODEL = originalModel;
});

test('联调缺少 Key 不联网，保存错误报告并跳过剩余案例', async () => {
  delete process.env.TYPESAFE_API_KEY;
  globalThis.fetch = () => assert.fail('缺少凭据不应联网');
  const dir = await mkdtemp(join(tmpdir(), 'jev-live-check-'));
  try {
    const output = join(dir, 'reports', 'missing-key.json');
    const report = await checkLive({ routes: true, output });
    assert.equal(report.status, 'error');
    assert.equal(report.request_attempts, 0);
    assert.equal(report.planned_requests, 3);
    assert.equal(report.results[0].result.error.code, 'missing_api_key');
    assert.equal(report.results[0].matches_intended_action, null);
    assert.deepEqual(report.skipped_cases, ['ambiguous', 'uncertain']);
    assert.deepEqual(JSON.parse(await readFile(output, 'utf8')), report);
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test('三个真实调用路径保留原始答案和不匹配分支；预期标签不发送给接口', async () => {
  // 这里只替换 HTTP 传输；这条测试不构成真实模型验收。
  process.env.TYPESAFE_API_KEY = 'test-secret-not-in-report';
  process.env.TYPESAFE_DEFAULT_MODEL = 'jev-test';
  let calls = 0;
  globalThis.fetch = async (_url, options) => {
    calls++;
    const body = JSON.parse(options.body);
    assert.equal(body.model, 'jev-test');
    assert.deepEqual(Object.keys(body.state).sort(), ['context', 'task']);
    assert.equal(options.body.includes('intended_action'), false);
    const response = mockResponse(body.state, body.questions);
    if (calls === 1) response.answers.needs_clarification.noul = 0.95;
    return Response.json({ ...response, model: 'jev-test-response', usage: { input_tokens: 20, output_tokens: 6 } },
      { headers: { 'x-request-id': `request-${calls}` } });
  };
  const report = await checkLive({ routes: true });
  assert.equal(calls, 3);
  assert.equal(report.request_attempts, 3);
  assert.equal(report.status, 'ok');
  assert.equal(report.results[0].result.recommendation.action, 'clarify');
  assert.equal(report.results[0].matches_intended_action, false);
  assert.equal(report.results[2].result.request_id, 'request-3');
  assert.equal(report.results[0].result.model, 'jev-test-response');
  assert.deepEqual(report.results[0].result.usage, { input_tokens: 20, output_tokens: 6 });
  assert.equal(report.chat_verified, false);
  assert.equal(JSON.stringify(report).includes('test-secret'), false);
});

test('联调遇到限流即停止，无额外请求且不回显错误正文', async () => {
  process.env.TYPESAFE_API_KEY = 'test-secret-not-in-report';
  let calls = 0;
  globalThis.fetch = async () => { calls++; return new Response('sensitive-response-body', { status: 429 }); };
  const report = await checkLive({ routes: true });
  assert.equal(calls, 1);
  assert.equal(report.status, 'error');
  assert.equal(report.request_attempts, 1);
  assert.equal(report.results[0].result.error.code, 'rate_limited');
  assert.equal(report.skipped_cases.length, 2);
  assert.equal(JSON.stringify(report).includes('sensitive-response-body'), false);
});

test('已有报告在发起请求前拒绝覆盖', async () => {
  process.env.TYPESAFE_API_KEY = 'test-secret-not-in-report';
  globalThis.fetch = () => assert.fail('已有报告时不应发起付费请求');
  const dir = await mkdtemp(join(tmpdir(), 'jev-live-check-'));
  try {
    const output = join(dir, 'previous.json');
    await writeFile(output, 'previous-result');
    await assert.rejects(checkLive({ output }), { code: 'EEXIST' });
    assert.equal(await readFile(output, 'utf8'), 'previous-result');
  } finally { await rm(dir, { recursive: true, force: true }); }
});
