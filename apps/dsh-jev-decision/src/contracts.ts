/** TypeSafe 的 JSON 契约与本插件的明确资源边界。 */
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type Content = string | Json[] | { [key: string]: Json };
export type Question =
  | { type: 'noul'; instructions: Content; criteria?: { true?: Content; false?: Content } }
  | { type: 'choice'; instructions: Content; criteria: Record<string, Content | null> }
  | { type: 'score'; instructions: Content; criteria: Content[] };
export type Questions = Record<string, Question>;
export type Answer =
  | { type: 'noul'; noul: number }
  | { type: 'choice'; choice: string; probabilities: Record<string, number>; confidence: number }
  | { type: 'score'; score: number; probabilities: Record<string, number>; confidence: number; legend: Record<string, Json> };
export type ResponseData = {
  model: string;
  answers: Record<string, Answer>;
  usage: { input_tokens: number; output_tokens: number };
};
export type ErrorCode = 'invalid_request' | 'missing_api_key' | 'authentication' | 'rate_limited'
  | 'server_error' | 'network_error' | 'timeout' | 'aborted' | 'invalid_response';

export class DecisionError extends Error {
  constructor(public readonly code: ErrorCode, message: string, public readonly retryable = false) {
    super(message);
    this.name = 'DecisionError';
  }
}

export function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && [null, Object.prototype].includes(Object.getPrototypeOf(value));
}

function invalid(message: string): never { throw new DecisionError('invalid_request', message); }
function malformed(message: string): never { throw new DecisionError('invalid_response', message); }

/** 拒绝循环、非有限数、非 JSON 值和过深嵌套，并生成无共享引用的快照。 */
export function snapshot(value: unknown, depth = 0): Json {
  if (depth > 20) return invalid('JSON 嵌套最多 20 层。');
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map(item => snapshot(item, depth + 1));
  if (record(value)) return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, snapshot(item, depth + 1)]));
  return invalid('输入必须是可序列化的 JSON，不能包含函数、undefined 或非有限数。');
}

function content(value: unknown): Content {
  if (typeof value === 'string') return value.trim() ? value : invalid('描述文字不能为空。');
  if (Array.isArray(value) && value.length) return snapshot(value) as Json[];
  if (record(value) && Object.keys(value).length) return snapshot(value) as Record<string, Json>;
  return invalid('state、instructions 和等级描述应为非空字符串、对象或数组。');
}

function identifier(value: string): void {
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(value) || ['constructor', 'prototype'].includes(value)) {
    invalid('问题 ID 和 Choice key 须为 1–64 位英文标识符，以字母开头。');
  }
}

export function parseRequest(state: unknown, input: unknown, maxInputBytes = 65536): { state: Content; questions: Questions } {
  // 在递归快照前先限制请求体积，避免对异常巨大的参数继续展开。
  let size: number;
  try { size = Buffer.byteLength(JSON.stringify({ state, questions: input })); }
  catch { return invalid('输入不是有效的 JSON。'); }
  if (size > maxInputBytes) return invalid(`state 与 questions 合计不能超过 ${maxInputBytes} 字节。`);
  const parsedState = content(state);
  if (!record(input) || Object.keys(input).length < 1 || Object.keys(input).length > 16) {
    return invalid('每次请求需要 1–16 个问题。');
  }
  const questions: Questions = {};
  for (const [id, raw] of Object.entries(input)) {
    identifier(id);
    if (!record(raw) || Object.keys(raw).some(key => !['type', 'instructions', 'criteria'].includes(key))) {
      return invalid('每个问题只接受 type、instructions 和 criteria。');
    }
    const instructions = content(raw.instructions);
    if (raw.type === 'noul') {
      const question: Extract<Question, { type: 'noul' }> = { type: 'noul', instructions };
      if (raw.criteria !== undefined) {
        if (!record(raw.criteria) || Object.keys(raw.criteria).some(key => !['true', 'false'].includes(key))) {
          return invalid('Noul criteria 只接受 true 和 false 描述。');
        }
        question.criteria = Object.fromEntries(Object.entries(raw.criteria).map(([key, value]) => [key, content(value)]));
      }
      questions[id] = question;
    } else if (raw.type === 'choice') {
      if (!record(raw.criteria) || Object.keys(raw.criteria).length < 2 || Object.keys(raw.criteria).length > 32) {
        return invalid('本插件每个 Choice 接受 2–32 个选项。');
      }
      const criteria = Object.fromEntries(Object.entries(raw.criteria).map(([key, value]) => {
        identifier(key);
        return [key, value === null ? null : content(value)];
      }));
      questions[id] = { type: 'choice', instructions, criteria };
    } else if (raw.type === 'score') {
      if (!Array.isArray(raw.criteria) || raw.criteria.length < 2 || raw.criteria.length > 10) {
        return invalid('Score 需要 2–10 个有序等级。');
      }
      questions[id] = { type: 'score', instructions, criteria: raw.criteria.map(content) };
    } else return invalid('问题类型只能是 choice、score 或 noul。');
  }
  return { state: parsedState, questions };
}

function probability(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) {
    return malformed('API 返回了无效概率或 confidence。');
  }
  return value;
}

function sameKeys(value: Record<string, unknown>, expected: string[]): boolean {
  return Object.keys(value).length === expected.length && expected.every(key => Object.hasOwn(value, key));
}

function distribution(value: unknown, keys: string[]): Record<string, number> {
  if (!record(value) || !sameKeys(value, keys)) return malformed('答案的概率标签与问题不一致。');
  const result = Object.fromEntries(Object.entries(value).map(([key, p]) => [key, probability(p)]));
  if (Math.abs(Object.values(result).reduce((a, b) => a + b, 0) - 1) > 0.02) {
    return malformed('概率之和偏离 1。');
  }
  return result;
}

export function parseResponse(input: unknown, questions: Questions): ResponseData {
  if (!record(input) || typeof input.model !== 'string' || !input.model.trim()
    || !record(input.answers) || !sameKeys(input.answers, Object.keys(questions)) || !record(input.usage)) {
    return malformed('API 响应缺少模型、完整答案映射或用量。');
  }
  const answers: Record<string, Answer> = {};
  for (const [id, question] of Object.entries(questions)) {
    const raw = input.answers[id];
    if (!record(raw) || raw.type !== question.type) return malformed('答案类型与问题不一致。');
    if (question.type === 'noul') {
      answers[id] = { type: 'noul', noul: probability(raw.noul) };
      continue;
    }
    const confidence = probability(raw.confidence);
    if (question.type === 'choice') {
      const probabilities = distribution(raw.probabilities, Object.keys(question.criteria));
      if (typeof raw.choice !== 'string' || !Object.hasOwn(probabilities, raw.choice)) {
        return malformed('Choice 返回了选项之外的标签。');
      }
      if (probabilities[raw.choice]! + 0.001 < Math.max(...Object.values(probabilities))) {
        return malformed('Choice 标签并非最高概率选项。');
      }
      answers[id] = { type: 'choice', choice: raw.choice, probabilities, confidence };
    } else {
      const keys = question.criteria.map((_, i) => String(i));
      const probabilities = distribution(raw.probabilities, keys);
      const expected = Object.entries(probabilities).reduce((sum, [key, p]) => sum + Number(key) * p, 0);
      if (typeof raw.score !== 'number' || !Number.isFinite(raw.score) || raw.score < 0
        || raw.score > keys.length - 1 || Math.abs(raw.score - expected) > 0.03
        || !record(raw.legend) || !sameKeys(raw.legend, keys)) {
        return malformed('Score 分数、等级或概率加权期望不一致。');
      }
      let legend: Record<string, Json>;
      try { legend = snapshot(raw.legend) as Record<string, Json>; }
      catch { return malformed('Score 的等级说明不是有效或适当深度的 JSON。'); }
      answers[id] = { type: 'score', score: raw.score, confidence, probabilities, legend };
    }
  }
  const { input_tokens, output_tokens } = input.usage;
  if (!Number.isSafeInteger(input_tokens) || !Number.isSafeInteger(output_tokens)
    || (input_tokens as number) < 0 || (output_tokens as number) < 0) return malformed('API 用量字段无效。');
  return { model: input.model, answers, usage: { input_tokens: input_tokens as number, output_tokens: output_tokens as number } };
}
