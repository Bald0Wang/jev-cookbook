import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { JevClient, TYPESAFE_ENDPOINT } from '../dist/client.js';

const originalFetch = globalThis.fetch;
const originalKey = process.env.TYPESAFE_API_KEY;
afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalKey === undefined) delete process.env.TYPESAFE_API_KEY;
  else process.env.TYPESAFE_API_KEY = originalKey;
});
const questions = { yes: { type: 'noul', instructions: '是否足够明确？' } };
const payload = { model: 'jev-test-fixture', answers: { yes: { type: 'noul', noul: 0.93 } }, usage: { input_tokens: 12, output_tokens: 4 } };
const live = () => new JevClient({ mode: 'live', model: 'jev-test', timeoutMs: 100 });
function mockFetch(fn) { process.env.TYPESAFE_API_KEY = 'test-key-must-not-leak'; globalThis.fetch = fn; }

test('缺少密钥和显式 mock 均不发出网络请求；live 不回退为 mock', async () => {
  delete process.env.TYPESAFE_API_KEY;
  globalThis.fetch = () => assert.fail('不应调用 fetch');
  const error = await live().decide('材料', questions);
  assert.equal(error.error.code, 'missing_api_key');
  assert.equal(error.source, 'typesafe_api');
  assert.equal(error.request_attempted, false);
  const fixture = await new JevClient({ mode: 'mock' }).decide('材料', questions);
  assert.equal(fixture.source, 'mock_fixture');
  assert.equal(fixture.request_attempted, false);
});

test('真实模式正确构造固定端点、Bearer、模型、state 和问题，并透传实际模型和用量', async () => {
  mockFetch(async (url, options) => {
    assert.equal(url, TYPESAFE_ENDPOINT);
    assert.equal(options.method, 'POST');
    assert.equal(options.redirect, 'error');
    assert.equal(options.headers.Authorization, 'Bearer test-key-must-not-leak');
    assert.deepEqual(JSON.parse(options.body), { model: 'jev-test', state: { task: '材料' }, questions });
    return Response.json(payload, { headers: { 'x-request-id': 'trace-test' } });
  });
  const result = await live().decide({ task: '材料' }, questions);
  assert.equal(result.status, 'ok');
  assert.equal(result.source, 'typesafe_api');
  assert.equal(result.model, 'jev-test-fixture');
  assert.equal(result.requested_model, 'jev-test');
  assert.equal(result.request_id, 'trace-test');
  assert.deepEqual(result.usage, payload.usage);
  assert.equal(JSON.stringify(result).includes('test-key'), false);
});

for (const [status, code] of [[400, 'invalid_request'], [401, 'authentication'], [403, 'authentication'], [429, 'rate_limited'], [503, 'server_error']]) {
  test(`HTTP ${status} 映射为 ${code}，不重试且不回显服务端敏感消息`, async () => {
    let calls = 0;
    mockFetch(async () => { calls++; return new Response('test-key-must-not-leak internal details', { status }); });
    const result = await live().decide('材料', questions);
    assert.equal(result.error.code, code);
    assert.equal(result.request_attempted, true);
    assert.equal(calls, 1);
    assert.equal(JSON.stringify(result).includes('test-key'), false);
    assert.equal(Object.hasOwn(result, 'answers'), false);
  });
}

test('网络异常不回显底层错误', async () => {
  mockFetch(async () => { throw new Error('test-key-must-not-leak'); });
  const result = await live().decide('材料', questions);
  assert.equal(result.error.code, 'network_error');
  assert.equal(JSON.stringify(result).includes('test-key'), false);
});

test('错误 JSON、缺失答案、超大响应（含无 Content-Length）都返回 invalid_response', async () => {
  const factories = [
    () => new Response('not json'),
    () => Response.json({ ...payload, answers: {} }),
    () => new Response('{}', { headers: { 'content-length': '2000000' } }),
    () => new Response(' '.repeat(1024 * 1024 + 1)),
  ];
  for (const make of factories) {
    mockFetch(async () => make());
    assert.equal((await live().decide('材料', questions)).error.code, 'invalid_response');
  }
});

test('超时会中止请求，不自动重试', async () => {
  let calls = 0;
  mockFetch((_url, { signal }) => new Promise((_resolve, reject) => {
    calls++;
    signal.addEventListener('abort', () => reject(signal.reason), { once: true });
  }));
  const result = await live().decide('材料', questions);
  assert.equal(result.error.code, 'timeout');
  assert.equal(calls, 1);
});

test('取消信号在请求前与响应体读取期间都有效', async () => {
  const aborted = AbortSignal.abort();
  mockFetch(() => assert.fail('已取消的请求不应发出'));
  assert.equal((await live().decide('材料', questions, aborted)).error.code, 'aborted');
  const controller = new AbortController();
  mockFetch(async (_url, { signal }) => new Response(new ReadableStream({
    start(stream) {
      stream.enqueue(new TextEncoder().encode('{'));
      signal.addEventListener('abort', () => stream.error(signal.reason), { once: true });
      queueMicrotask(() => controller.abort());
    },
  })));
  const result = await live().decide('材料', questions, controller.signal);
  assert.equal(result.error.code, 'aborted');
});

test('错误输入在请求前拒绝，超时/模型配置需有效', async () => {
  mockFetch(() => assert.fail('非法输入不应发出请求'));
  const result = await live().decide('', questions);
  assert.equal(result.error.code, 'invalid_request');
  assert.equal(result.request_attempted, false);
  assert.throws(() => new JevClient({ timeoutMs: 1 }));
  assert.throws(() => new JevClient({ model: 'bad model' }));
});
