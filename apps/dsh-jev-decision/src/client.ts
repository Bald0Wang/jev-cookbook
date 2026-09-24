import { DecisionError, parseRequest, parseResponse, type Content, type ErrorCode, type Questions, type ResponseData } from './contracts.js';
import { mockResponse } from './mock.js';

export const TYPESAFE_ENDPOINT = 'https://api.typesafe.ai/v1/systemone';
export type RunMode = 'live' | 'mock';
export type Success = ResponseData & {
  status: 'ok'; source: 'typesafe_api' | 'mock_fixture'; requested_model: string;
  request_attempted: boolean; request_id: string | null; duration_ms: number | null;
};
export type Failure = {
  status: 'error'; source: 'typesafe_api' | 'mock_fixture'; request_attempted: boolean;
  error: { code: ErrorCode; message: string; retryable: boolean };
};
export type DecisionResult = Success | Failure;
export type ClientOptions = {
  mode?: RunMode;
  model?: string;
  timeoutMs?: number;
  maxInputBytes?: number;
};

function httpError(status: number): DecisionError {
  if (status === 401 || status === 403) return new DecisionError('authentication', 'TypeSafe 认证或访问权限无效，请检查环境变量与账户权限。');
  if (status === 429) return new DecisionError('rate_limited', 'TypeSafe 请求被限流；本插件没有自动重试。', true);
  if (status >= 500) return new DecisionError('server_error', 'TypeSafe 服务暂时失败。', true);
  return new DecisionError('invalid_request', 'TypeSafe 拒绝了请求，请核对模型和问题定义。');
}

async function readJson(response: Response): Promise<unknown> {
  const limit = 1024 * 1024;
  if (Number(response.headers.get('content-length')) > limit) {
    await response.body?.cancel();
    throw new DecisionError('invalid_response', 'API 响应超过 1 MiB。');
  }
  const reader = response.body?.getReader();
  if (!reader) throw new DecisionError('invalid_response', 'API 返回空响应。');
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      length += next.value.byteLength;
      if (length > limit) {
        await reader.cancel();
        throw new DecisionError('invalid_response', 'API 响应超过 1 MiB。');
      }
      chunks.push(next.value);
    }
  } finally { reader.releaseLock(); }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw new DecisionError('invalid_response', 'API 返回的内容不是有效 JSON。'); }
}

/** 固定 TypeSafe 端点；密钥只在发起请求时读取，不进入参数、日志或配置。 */
export class JevClient {
  readonly mode: RunMode;
  readonly model: string;
  readonly timeoutMs: number;
  readonly maxInputBytes: number;

  constructor(options: ClientOptions = {}) {
    const mode = options.mode ?? process.env.JEV_DECISION_MODE ?? 'live';
    if (mode !== 'live' && mode !== 'mock') throw new Error('JEV_DECISION_MODE 必须为 live 或 mock。');
    this.mode = mode;
    this.model = options.model ?? process.env.TYPESAFE_DEFAULT_MODEL ?? 'jev-1.13.0';
    this.timeoutMs = options.timeoutMs ?? 20000;
    this.maxInputBytes = options.maxInputBytes ?? 65536;
    if (!/^[A-Za-z0-9._-]{1,128}$/.test(this.model)) throw new Error('模型名无效。');
    if (!Number.isInteger(this.timeoutMs) || this.timeoutMs < 100 || this.timeoutMs > 120000) throw new Error('timeoutMs 必须在 100–120000 之间。');
    if (!Number.isInteger(this.maxInputBytes) || this.maxInputBytes < 1024 || this.maxInputBytes > 262144) throw new Error('maxInputBytes 必须在 1024–262144 之间。');
  }

  async decide(state: unknown, questions: unknown, callerSignal?: AbortSignal): Promise<DecisionResult> {
    let attempted = false;
    const source = this.mode === 'mock' ? 'mock_fixture' : 'typesafe_api';
    try {
      if (callerSignal?.aborted) throw new DecisionError('aborted', '调用已取消。');
      const request = parseRequest(state, questions, this.maxInputBytes);
      if (this.mode === 'mock') {
        const data = parseResponse(mockResponse(request.state, request.questions), request.questions);
        return { status: 'ok', source, requested_model: this.model, ...data,
          request_attempted: false, request_id: null, duration_ms: null };
      }
      const key = process.env.TYPESAFE_API_KEY;
      if (!key?.trim()) throw new DecisionError('missing_api_key', '未配置 TYPESAFE_API_KEY 环境变量；没有发起 API 请求。');
      attempted = true;
      const result = await this.request(request, key, callerSignal);
      return { status: 'ok', source, requested_model: this.model, request_attempted: true, ...result };
    } catch (error) {
      const safe = error instanceof DecisionError ? error
        : new DecisionError('network_error', '请求未能完成；请检查网络与服务可用性。', true);
      return { status: 'error', source, request_attempted: attempted,
        error: { code: safe.code, message: safe.message, retryable: safe.retryable } };
    }
  }

  private async request(request: { state: Content; questions: Questions }, key: string, callerSignal?: AbortSignal) {
    const timeout = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; timeout.abort(); }, this.timeoutMs);
    const signal = callerSignal ? AbortSignal.any([callerSignal, timeout.signal]) : timeout.signal;
    const start = performance.now();
    try {
      const response = await fetch(TYPESAFE_ENDPOINT, {
        method: 'POST', redirect: 'error', signal,
        headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: this.model, ...request }),
      });
      if (!response.ok) {
        await response.body?.cancel();
        throw httpError(response.status);
      }
      const data = parseResponse(await readJson(response), request.questions);
      if (signal.aborted) throw new DecisionError('aborted', '调用已取消。');
      return { ...data, request_id: response.headers.get('x-request-id'),
        duration_ms: Math.round(performance.now() - start) };
    } catch (error) {
      if (callerSignal?.aborted) throw new DecisionError('aborted', '调用已取消。');
      if (timedOut) throw new DecisionError('timeout', 'TypeSafe 请求超时；本插件没有自动重试。', true);
      throw error;
    } finally { clearTimeout(timer); }
  }
}
