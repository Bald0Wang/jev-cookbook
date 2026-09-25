import test from 'node:test';
import assert from 'node:assert/strict';
import { parseRequest, parseResponse } from '../dist/contracts.js';
import { mockResponse } from '../dist/mock.js';

const questions = {
  label: { type: 'choice', instructions: { question: '选择分类', evidence: ['参考资料'] }, criteria: { a: null, b: ['描述'] } },
  yes: { type: 'noul', instructions: '是否明确？' },
  size: { type: 'score', instructions: '复杂度？', criteria: ['低', { level: '中' }, ['高']] },
};
const rejects = (fn, code) => assert.throws(fn, error => error.code === code);

test('结构化 state / instructions / criteria 与三种原语往返，Noul 没有伪造 confidence', () => {
  const request = parseRequest([{ text: '材料', enabled: true }], questions);
  const response = parseResponse(mockResponse(request.state, request.questions), request.questions);
  assert.equal(response.answers.yes.noul, 0.5);
  assert.equal(Object.hasOwn(response.answers.yes, 'confidence'), false);
  assert.equal(response.answers.size.score, 1);
  assert.equal(request.questions.label.criteria.a, null);
  request.questions.label.instructions.evidence.push('另一条');
  assert.equal(questions.label.instructions.evidence.length, 1);
});

test('不接受空材料、非法问题、循环、过深、非 JSON 和超量输入', () => {
  for (const state of ['', '   ', {}, [], null, 2, { x: undefined }, { x: NaN }, { x: new Date() }]) {
    rejects(() => parseRequest(state, questions), 'invalid_request');
  }
  const cycle = {}; cycle.self = cycle;
  rejects(() => parseRequest(cycle, questions), 'invalid_request');
  let deep = 'end'; for (let i = 0; i < 24; i++) deep = { next: deep };
  rejects(() => parseRequest(deep, questions), 'invalid_request');
  rejects(() => parseRequest('中'.repeat(100), questions, 100), 'invalid_request');
  const badQuestions = [
    {}, { 'bad id': questions.yes }, { constructor: questions.yes },
    { x: { ...questions.yes, confidence: 1 } },
    { x: { ...questions.yes, type: 'boolean' } },
    { x: { ...questions.yes, criteria: { unknown: 'yes' } } },
    { x: { ...questions.label, criteria: { single: null } } },
    { x: { ...questions.size, criteria: ['only'] } },
    { x: { ...questions.size, criteria: Array(11).fill('level') } },
    Object.fromEntries(Array.from({ length: 17 }, (_, i) => [`q${i}`, questions.yes])),
    { x: { ...questions.label, criteria: Object.fromEntries(Array.from({ length: 33 }, (_, i) => [`k${i}`, null])) } },
  ];
  for (const bad of badQuestions) rejects(() => parseRequest('材料', bad), 'invalid_request');
});

test('拒绝缺答案、类型错、概率错、最高选项错、Score 期望不一致和非法用量', () => {
  const changes = [
    r => delete r.answers.yes,
    r => r.answers.extra = r.answers.yes,
    r => r.answers.yes.type = 'choice',
    r => r.answers.yes.noul = 1.01,
    r => r.answers.label.confidence = -1,
    r => r.answers.label.choice = 'outside',
    r => r.answers.label.probabilities = { a: 0.1, b: 0.9 },
    r => r.answers.label.probabilities = { a: 0.1, b: 0.1 },
    r => r.answers.label.probabilities = { a: 0.5, c: 0.5 },
    r => r.answers.size.score = 2,
    r => r.answers.size.legend = { '0': '低' },
    r => r.usage.input_tokens = -1,
    r => r.usage.output_tokens = 0.5,
    r => r.model = '',
  ];
  for (const change of changes) {
    const response = mockResponse('材料', questions);
    change(response);
    rejects(() => parseResponse(response, questions), 'invalid_response');
  }
});
