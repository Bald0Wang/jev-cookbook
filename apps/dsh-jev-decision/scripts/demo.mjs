import assert from 'node:assert/strict';
import { createHarness } from './harness.mjs';
import { DEMO_CASES } from '../dist/mock.js';

console.log('DSH × Jev 离线演示：人工夹具，无模型请求、无真实推理。');
const harness = await createHarness({ mode: 'mock' });
try {
  for (const example of DEMO_CASES) {
    const result = await harness.execute('jev_route_task', { task: example.task });
    assert.equal(result.isError, false);
    assert.equal(result.value.status, 'ok');
    assert.equal(result.value.recommendation.action, example.expected);
    console.log(JSON.stringify({
      task: example.task,
      source: result.value.source,
      action: result.value.recommendation.action,
      reason: result.value.recommendation.reason,
      request_attempted: result.value.request_attempted,
    }, null, 2));
  }
  console.log('三条演示分支均通过 DSH ToolRuntime 执行。');
} finally { await harness.dispose(); }
