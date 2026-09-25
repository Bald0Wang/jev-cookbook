/** 明确标识的人工夹具。只用于演示、安装验收和代码路径测试。 */
import type { Content, Questions, ResponseData } from './contracts.js';

export const DEMO_CASES = [
  { id: 'clear', task: '请修复仓库中日期解析函数对空字符串的处理，并补一个回归测试。', expected: 'proceed' },
  { id: 'ambiguous', task: '帮我把那个东西弄好。', expected: 'clarify' },
  { id: 'uncertain', task: '看看这份材料，代码和文案方面都处理一下。', expected: 'review' },
] as const;

export function mockResponse(state: Content, questions: Questions): ResponseData {
  const task = typeof state === 'object' && !Array.isArray(state) ? state.task : undefined;
  const fixture = DEMO_CASES.find(item => item.task === task);
  const answers: ResponseData['answers'] = {};
  for (const [id, question] of Object.entries(questions)) {
    if (question.type === 'noul') {
      answers[id] = { type: 'noul', noul: fixture && id === 'needs_clarification'
        ? ({ clear: 0.04, ambiguous: 0.96, uncertain: 0.5 }[fixture.id]) : 0.5 };
    } else if (question.type === 'choice') {
      const keys = Object.keys(question.criteria);
      const selected = fixture && keys.includes('coding') ? 'coding' : keys[0]!;
      const high = fixture?.id === 'clear';
      const probabilities = Object.fromEntries(keys.map(key => [key, high
        ? (key === selected ? 0.97 : 0.03 / (keys.length - 1)) : 1 / keys.length]));
      answers[id] = { type: 'choice', choice: selected, probabilities, confidence: high ? 0.94 : 0.3 };
    } else {
      const probabilities = Object.fromEntries(question.criteria.map((_, i) => [String(i), 1 / question.criteria.length]));
      answers[id] = { type: 'score', score: (question.criteria.length - 1) / 2,
        confidence: 0.3, probabilities, legend: Object.fromEntries(question.criteria.map((value, i) => [String(i), value])) };
    }
  }
  return { model: 'mock-fixture-not-a-model', answers, usage: { input_tokens: 0, output_tokens: 0 } };
}
