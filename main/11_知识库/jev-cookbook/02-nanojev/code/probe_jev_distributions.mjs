import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';

// 默认只做离线预览。付费调用必须显式传 --live；此文件从不读取 .env。
export const CONFIG = Object.freeze({
  schema_version: 1,
  model: 'typesafe-ai/jev',
  ks: [2, 5, 20, 64, 255],
  concurrency: 2,
  timeout_ms: 45_000,
  automatic_retries: 0,
  max_requests: 40,
  budget_usd: 1,
  minimum_request_reserve_usd: 0.02,
});
const QUESTION_ID = 'next_label';
const TOL = 1e-10;
const sum = xs => xs.reduce((a, b) => a + b, 0);
const sha256 = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const inputOf = row => ({ model: CONFIG.model, state: row.state, questions: row.questions });
export const inputHash = row => sha256(inputOf(row));

/** 自有、可验证的条件概率诊断；reference 不是一次抽样的实际 outcome。 */
export function buildCases() {
  const rows = [];
  for (const K of CONFIG.ks) {
    // 非整数键，确保 JavaScript 对象的候选插入顺序不会自动变成数值排序。
    const ids = Array.from({ length: K }, (_, i) => `label_${String(i).padStart(3, '0')}`);
    const certain = ids[Math.floor(K / 2)];
    const specs = [
      {
        family: 'explicit_unique',
        rule: `The selected label is explicitly known to be ${certain}. This fact is certain. No other label was selected.`,
        probs: ids.map(id => id === certain ? 1 : 0),
      },
      {
        family: 'unrevealed_uniform',
        rule: `A fair lottery chooses exactly one of the ${K} labels. Every label has exactly the same chance. The draw result has not been observed or revealed; no additional information about the result is available.`,
        probs: ids.map(() => 1 / K),
      },
      {
        family: 'two_support_half',
        rule: `A fair coin selects ${ids[0]} on heads and ${ids.at(-1)} on tails. Each has probability 0.5. All other labels have probability 0. The coin result has not been observed or revealed.`,
        probs: ids.map((_, i) => i === 0 || i === K - 1 ? 0.5 : 0),
      },
      {
        family: 'explicit_weighted',
        rule: K === 2
          ? `An unobserved random draw selects ${ids[0]} with probability 0.7 and ${ids[1]} with probability 0.3. These are the only possible outcomes. The result has not been observed or revealed.`
          : `An unobserved random draw selects ${ids[0]} with probability 0.7, ${ids[1]} with probability 0.2, and ${ids[2]} with probability 0.1. Every other label has probability 0. The result has not been observed or revealed.`,
        probs: ids.map((_, i) => (K === 2 ? [0.7, 0.3] : [0.7, 0.2, 0.1])[i] ?? 0),
      },
    ];
    for (const spec of specs) {
      const state = `This is a complete probability experiment. The possible labels are ${ids.join(', ')}.\n${spec.rule}\nCondition only on the facts above; the order of answer options has no significance.`;
      for (const permutation of ['original', 'reverse']) {
        const ordered = permutation === 'original' ? ids : [...ids].reverse();
        const row = {
          id: `${spec.family}_k${K}_${permutation}`,
          case_family: spec.family,
          K,
          permutation,
          canonical_candidate_ids: ids,
          candidate_id_mapping: ordered.map((id, presented_index) => ({
            presented_index, candidate_id: id, canonical_index: ids.indexOf(id),
          })),
          state,
          questions: {
            [QUESTION_ID]: {
              type: 'choice',
              instructions: 'Which label is selected in this experiment? Return the conditional probability distribution over all offered labels given exactly the stated facts. For an unobserved draw, preserve the stated randomness; do not guess its hidden outcome. The answer options are mutually exclusive and exhaustive.',
              criteria: Object.fromEntries(ordered.map(id => [id, `The selected label is ${id}.`])),
            },
          },
          reference_distribution: Object.fromEntries(ids.map((id, i) => [id, spec.probs[i]])),
          reference_kind: 'analytically_defined_conditional_distribution_not_observed_outcome',
        };
        row.input_sha256 = inputHash(row);
        rows.push(row);
      }
    }
  }
  return rows;
}

export function requestReserve(row) {
  // 当前请求极小：至少预留 $0.02/请求；另以 UTF-8 字节数代 token 数、
  // 加 8192 余量并乘四倍已观察单价。不是供应商强制费用上限。
  const bytes = Buffer.byteLength(JSON.stringify(inputOf(row)));
  return Math.max(CONFIG.minimum_request_reserve_usd, (bytes + 8192) * 0.042 * 4 / 1e6);
}

export function nearestRoundingDiagnostic(probs, reference, rounding) {
  const decimals = rounding?.probabilityDecimals;
  if (!Number.isInteger(decimals) || decimals < 0 || decimals > 15) {
    return { available: false, reason: 'missing_or_unsupported_probability_decimals' };
  }
  const radius = 0.5 * 10 ** -decimals;
  const ids = Object.keys(reference);
  const bounds = ids.map(id => [Math.max(0, probs[id] - radius), Math.min(1, probs[id] + radius)]);
  const lower_sum = sum(bounds.map(([l]) => l));
  const upper_sum = sum(bounds.map(([, u]) => u));
  const outside = ids.filter((id, i) => reference[id] < bounds[i][0] - TOL || reference[id] > bounds[i][1] + TOL);
  return {
    available: true,
    assumption: 'nearest_rounding_closed_intervals_tie_rule_unspecified',
    provider_rounding_mode_known: false,
    probability_decimals: decimals,
    half_step: radius,
    lower_sum,
    upper_sum,
    simplex_feasible: lower_sum <= 1 + TOL && upper_sum >= 1 - TOL,
    reference_inside_all_intervals: outside.length === 0,
    reference_outside_count: outside.length,
    reference_outside_candidate_ids: outside,
  };
}

export function analyzeCase(row, teacher) {
  const probs = teacher.native_probs?.[QUESTION_ID];
  const ids = row.canonical_candidate_ids;
  if (!probs || Object.keys(probs).length !== ids.length
      || ids.some(id => !Number.isFinite(probs[id]) || probs[id] < 0 || probs[id] > 1)) {
    throw new Error('INVALID_NATIVE_PROBABILITIES');
  }
  const values = ids.map(id => probs[id]);
  const raw_sum = sum(values);
  const nonzero = raw_sum > 0;
  const unit = Math.abs(raw_sum - 1) <= TOL;
  const max = nonzero ? Math.max(...values) : null;
  const entropy = ps => -sum(ps.filter(p => p > 0).map(p => p * Math.log(p)));
  const proxy = nonzero ? values.map(p => p / raw_sum) : null;
  const ref = ids.map(id => row.reference_distribution[id]);
  return {
    id: row.id, case_family: row.case_family, K: row.K, permutation: row.permutation,
    input_sha256: row.input_sha256,
    raw_sum,
    zero_count: values.filter(p => p === 0).length,
    nonzero_count: values.filter(p => p > 0).length,
    native_sum_is_one: unit,
    all_zero: !nonzero,
    native_pmax: max,
    native_argmax_candidate_ids: nonzero ? ids.filter(id => Math.abs(probs[id] - max) <= TOL) : [],
    // 非单位和时不把 -sum(r log r) 称为分布熵；全零不捏造 argmax 或均匀分布。
    native_entropy_nats: nonzero && unit ? entropy(values) : null,
    native_entropy_reason: !nonzero ? 'all_zero' : unit ? null : 'native_sum_not_one',
    native_max_abs_component_difference_from_reference: Math.max(...values.map((p, i) => Math.abs(p - ref[i]))),
    proxy_normalized: proxy === null ? null : {
      label: 'diagnostic_only_native_values_divided_by_raw_sum',
      pmax: Math.max(...proxy),
      entropy_nats: entropy(proxy),
      total_variation_from_reference: 0.5 * sum(proxy.map((p, i) => Math.abs(p - ref[i]))),
      max_abs_component_difference_from_reference: Math.max(...proxy.map((p, i) => Math.abs(p - ref[i]))),
    },
    rounding: teacher.rounding ?? null,
    nearest_rounding: nearestRoundingDiagnostic(probs, row.reference_distribution, teacher.rounding),
    cost_usd: providerCost(teacher),
  };
}

function providerCost(teacher) {
  const value = teacher?.provider_metadata?.gateway?.cost;
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

export async function readLedger(file) {
  let text;
  try { text = await fs.readFile(file, 'utf8'); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  // 文件截断时拒绝付费续跑，避免把已发出的请求误判为未执行。
  return text.split('\n').filter(line => line.trim()).map(line => JSON.parse(line));
}

export function inspectLedger(events, cases) {
  const planned = new Map(cases.map(row => [row.input_sha256, row]));
  const started = new Map();
  const finished = new Map();
  for (const event of events) {
    const row = planned.get(event.input_sha256);
    if (!row || row.id !== event.case_id || event.model !== CONFIG.model) throw new Error('LEDGER_INPUT_MISMATCH');
    if (event.event === 'started') {
      if (started.has(event.input_sha256)) throw new Error('DUPLICATE_DISPATCH');
      started.set(event.input_sha256, event);
    } else if (['succeeded', 'failed'].includes(event.event)) {
      if (!started.has(event.input_sha256) || finished.has(event.input_sha256)) throw new Error('INVALID_LEDGER_SEQUENCE');
      finished.set(event.input_sha256, event);
    } else throw new Error('INVALID_LEDGER_EVENT');
  }
  if (started.size > CONFIG.max_requests) throw new Error('LEDGER_EXCEEDS_REQUEST_LIMIT');
  const successes = [...finished.values()].filter(event => event.event === 'succeeded');
  const failures = [...finished.values()].filter(event => event.event === 'failed');
  const unresolved = [...started.values()].filter(event => !finished.has(event.input_sha256));
  const paidEvents = [...finished.values()].filter(event => event.actual_cost_usd !== null);
  if (paidEvents.some(event => !Number.isFinite(event.actual_cost_usd) || event.actual_cost_usd < 0)) throw new Error('INVALID_LEDGER_COST');
  const actual_cost_usd = sum(paidEvents.map(event => event.actual_cost_usd));
  const unknown = [...failures.filter(event => event.actual_cost_usd === null), ...unresolved];
  const reserved_unknown_cost_usd = sum(unknown.map(event => started.get(event.input_sha256).reserved_cost_usd));
  return { started, finished, successes, failures, unresolved, actual_cost_usd, reserved_unknown_cost_usd };
}

export function createSummary(cases, events, mode = 'saved_results') {
  const status = inspectLedger(events, cases);
  const byHash = new Map(cases.map(row => [row.input_sha256, row]));
  const diagnostics = status.successes.map(event => analyzeCase(byHash.get(event.input_sha256), event.teacher));
  const pairs = [];
  for (const K of CONFIG.ks) {
    for (const family of [...new Set(cases.map(row => row.case_family))]) {
      const a = cases.find(row => row.K === K && row.case_family === family && row.permutation === 'original');
      const b = cases.find(row => row.K === K && row.case_family === family && row.permutation === 'reverse');
      const ea = status.finished.get(a.input_sha256), eb = status.finished.get(b.input_sha256);
      if (ea?.event !== 'succeeded' || eb?.event !== 'succeeded') continue;
      const pa = ea.teacher.native_probs[QUESTION_ID], pb = eb.teacher.native_probs[QUESTION_ID];
      const ids = a.canonical_candidate_ids;
      const sa = sum(ids.map(id => pa[id])), sb = sum(ids.map(id => pb[id]));
      pairs.push({
        K, case_family: family,
        restored_candidate_id_comparison: true,
        native_max_abs_probability_difference: Math.max(...ids.map(id => Math.abs(pa[id] - pb[id]))),
        native_pmax_difference: sa > 0 && sb > 0 ? Math.abs(Math.max(...Object.values(pa)) - Math.max(...Object.values(pb))) : null,
        original_raw_sum: sa, reverse_raw_sum: sb,
        proxy_normalized_max_abs_probability_difference: sa > 0 && sb > 0
          ? Math.max(...ids.map(id => Math.abs(pa[id] / sa - pb[id] / sb))) : null,
      });
    }
  }
  const group = CONFIG.ks.map(K => {
    const records = diagnostics.filter(row => row.K === K);
    const nums = key => records.map(row => row[key]).filter(Number.isFinite);
    const range = key => nums(key).length ? { min: Math.min(...nums(key)), max: Math.max(...nums(key)) } : null;
    return {
      K, planned_cases: 8, completed_cases: records.length,
      all_zero_cases: records.filter(row => row.all_zero).length,
      nonunit_sum_cases: records.filter(row => !row.native_sum_is_one).length,
      raw_sum_range: range('raw_sum'), zero_count_range: range('zero_count'),
      native_pmax_range: range('native_pmax'), native_entropy_nats_range: range('native_entropy_nats'),
      nearest_rounding_feasible_cases: records.filter(row => row.nearest_rounding.simplex_feasible).length,
      reference_inside_nearest_intervals_cases: records.filter(row => row.nearest_rounding.reference_inside_all_intervals).length,
    };
  });
  return {
    schema_version: CONFIG.schema_version, generated_at: new Date().toISOString(), mode,
    purpose: 'finite_diagnostic_probe_not_training_dataset_expansion_not_observed_outcome_calibration_not_jev_rl_recipe',
    settings: CONFIG,
    planned_evaluations: cases.length, dispatched_evaluations: status.started.size,
    successful_evaluations: status.successes.length, failed_evaluations: status.failures.length,
    unresolved_evaluations: status.unresolved.length,
    complete: status.successes.length === cases.length,
    actual_known_cost_usd: status.actual_cost_usd,
    reserved_unknown_cost_usd: status.reserved_unknown_cost_usd,
    cost_known_for_every_dispatched_evaluation: status.reserved_unknown_cost_usd === 0,
    failure_codes: status.failures.map(event => ({ case_id: event.case_id, code: event.error_code })),
    by_k: group, cases: diagnostics, permutation_pairs: pairs,
    limitations_zh: [
      'reference_distribution 是题目定义的条件分布；本次没有抽样观测标签，分布差异不称为实际校准误差。',
      '每种情形每个顺序只有一次请求，顺序差异可能混合服务随机性；不能据此单独认定候选顺序导致差异。',
      '原生概率未经归一化；另列 proxy-normalized 仅用于诊断，全零不补均匀分布。',
      '只有 probabilityDecimals 时，最近邻舍入及闭区间是诊断假设；没有确认供应商舍入模式或边界取舍。',
      '40 个合成条件概率探针不能证明广泛能力或实证校准，也不能还原 Jev 内部 RLCD 算法。',
      '预算是客户端估算与并发预留守卫，不是供应商单请求强制上限；未知失败费用保留 reserve。',
    ],
  };
}

const fmt = value => value === null || value === undefined ? '—' : typeof value === 'number' ? Number(value.toPrecision(7)).toString() : String(value);
export function summaryMarkdown(summary) {
  const lines = [
    '# Jev 条件概率分布探针', '',
    `已发出 ${summary.dispatched_evaluations}/${summary.planned_evaluations} 次独立评估，成功 ${summary.successful_evaluations} 次，失败 ${summary.failed_evaluations} 次，未决 ${summary.unresolved_evaluations} 次。已知供应商费用 $${fmt(summary.actual_known_cost_usd)}；未知费用预留 $${fmt(summary.reserved_unknown_cost_usd)}。`, '',
    '这是自有合成问题的有限诊断，不是扩充训练集。参考值来自题目明示的条件概率规则，没有抽取实际 outcome；因此这里报告分布对齐差异，不把它叫作实际校准误差。', '',
    '每个 K 包含明确唯一答案、未揭示均匀抽签、两个标签各半、明示非均匀权重四类，每类各用原序与逆序。每次请求仅一个 state 与一道 Choice。', '',
    '| K | 情形 | 顺序 | 原生和 | 零项数 | 原生最大项 | 原生熵(nats) | 最近邻区间可行 | 参考落区间 |',
    '|---|---|---|---:|---:|---:|---:|---|---|',
  ];
  for (const row of summary.cases) {
    lines.push(`| ${row.K} | ${row.case_family} | ${row.permutation} | ${fmt(row.raw_sum)} | ${row.zero_count} | ${fmt(row.native_pmax)} | ${fmt(row.native_entropy_nats)} | ${row.nearest_rounding.simplex_feasible ?? '未知'} | ${row.nearest_rounding.reference_inside_all_intervals ?? '未知'} |`);
  }
  lines.push('', '全零时不定义 argmax 或概率最大值，非单位和时不定义原生分布熵。完整 argmax（含并列）、每 K 汇总、参考逐项差异、另标的 proxy-normalized 熵与差异，见同名 JSON；原始值和费用保存在私有 JSONL。', '',
    '| K | 情形 | 按候选 ID 还原后的原生最大逐项差 | 两个最大值之差 | proxy-normalized 最大逐项差 |',
    '|---|---|---:|---:|---:|');
  for (const row of summary.permutation_pairs) lines.push(`| ${row.K} | ${row.case_family} | ${fmt(row.native_max_abs_probability_difference)} | ${fmt(row.native_pmax_difference)} | ${fmt(row.proxy_normalized_max_abs_probability_difference)} |`);
  lines.push('', ...summary.limitations_zh.map(text => `- ${text}`), '');
  if (summary.failure_codes.length) lines.push('失败记录：', '', ...summary.failure_codes.map(row => `- ${row.case_id}: ${row.code}；不会自动重试。`), '');
  return lines.join('\n');
}

export async function writeSummary(outputDir, cases, events, mode) {
  const summary = createSummary(cases, events, mode);
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'distribution_probe_summary.json'), JSON.stringify(summary, null, 2) + '\n');
  await fs.writeFile(path.join(outputDir, 'distribution_probe_summary_zh.md'), summaryMarkdown(summary));
  return summary;
}

/** evaluate 注入用于完全离线的预算、失败、恢复测试；生产唯一入口是 --live。 */
export async function runProbe({ outputDir = 'research', evaluate, cases = buildCases(), budget = CONFIG.budget_usd } = {}) {
  if (typeof evaluate !== 'function') throw new Error('EVALUATOR_REQUIRED');
  if (!(budget > 0 && budget <= CONFIG.budget_usd)) throw new Error('INVALID_BUDGET');
  if (cases.length > CONFIG.max_requests) throw new Error('TOO_MANY_CASES');
  await fs.mkdir(outputDir, { recursive: true });
  const file = path.join(outputDir, 'private_distribution_probe.jsonl');
  const events = await readLedger(file);
  const previous = inspectLedger(events, cases);
  // 失败/中断不是可自动重试项；保留历史记录，避免崩溃后重复收费。
  if (previous.failures.length || previous.unresolved.length) {
    const summary = await writeSummary(outputDir, cases, events, 'blocked_by_prior_failure_or_unresolved_request');
    return { ...summary, stopped_reason: 'PRIOR_FAILURE_OR_UNRESOLVED_REQUEST' };
  }
  const pending = cases.filter(row => !previous.started.has(row.input_sha256));
  let spent = previous.actual_cost_usd;
  let reserved = 0, next = 0, dispatched = previous.started.size;
  let stopped = false, stoppedReason = null;
  let writing = Promise.resolve();
  const append = event => {
    writing = writing.then(async () => {
      await fs.appendFile(file, JSON.stringify(event) + '\n');
      events.push(event);
    });
    return writing;
  };
  const stop = reason => { stopped = true; stoppedReason ??= reason; };
  async function worker() {
    while (!stopped && next < pending.length) {
      const row = pending[next];
      const reserve = requestReserve(row);
      if (dispatched >= CONFIG.max_requests || spent + reserved + reserve > budget + 1e-12) {
        stop(dispatched >= CONFIG.max_requests ? 'REQUEST_LIMIT' : 'BUDGET_GUARD');
        break;
      }
      // 无 await 的同步预留把另一 worker 的 in-flight 费用计入守卫。
      next++; dispatched++; reserved += reserve;
      const base = { schema_version: CONFIG.schema_version, case_id: row.id, input_sha256: row.input_sha256, model: CONFIG.model };
      let teacher = null, actual = null, startedPersisted = false;
      try {
        await append({ ...base, event: 'started', at: new Date().toISOString(), reserved_cost_usd: reserve, case: row });
        startedPersisted = true;
        // 调用之前先记录 dispatch；若进程中断，续跑会停止而不是重试这次请求。
        teacher = await evaluate({ teacher: 'jev', model: CONFIG.model, state: row.state, questions: row.questions, signal: AbortSignal.timeout(CONFIG.timeout_ms) });
        actual = providerCost(teacher);
        if (actual === null) throw Object.assign(new Error('MISSING_COST'), { code: 'MISSING_COST' });
        spent += actual;
        analyzeCase(row, teacher);
        await append({ ...base, event: 'succeeded', at: new Date().toISOString(), actual_cost_usd: actual, case: row, teacher });
        if (actual > reserve + TOL) stop('ACTUAL_COST_EXCEEDED_RESERVE');
        if (spent + reserved - reserve > budget + TOL) stop('ACTUAL_COST_EXCEEDED_BUDGET');
      } catch (error) {
        stop('REQUEST_OR_PERSIST_FAILED');
        // 只保存固定/本地错误码，不保存供应商异常文本或可能含凭据的原始请求头。
        const safeCodes = new Set(['MISSING_COST', 'INVALID_NATIVE_PROBABILITIES', 'INVALID_TEACHER_OUTPUT', 'TEACHER_ABORTED', 'TEACHER_REQUEST_FAILED']);
        const error_code = safeCodes.has(error.code) ? error.code
          : safeCodes.has(error.message) ? error.message : 'REQUEST_OR_PERSIST_FAILED';
        if (startedPersisted) await append({ ...base, event: 'failed', at: new Date().toISOString(), actual_cost_usd: actual, reserved_cost_usd: reserve, error_code, teacher });
      } finally {
        reserved -= reserve;
      }
    }
  }
  // allSettled 确保一条落盘异常不会提前结束另一条仍在途的请求。
  const outcomes = await Promise.allSettled(Array.from({ length: CONFIG.concurrency }, worker));
  const rejected = outcomes.find(result => result.status === 'rejected');
  if (rejected) throw new Error('LEDGER_PERSISTENCE_FAILED_NO_AUTOMATIC_RETRY');
  await writing;
  const summary = await writeSummary(outputDir, cases, events, 'live');
  return { ...summary, stopped_reason: stoppedReason };
}

async function main(argv) {
  const allowed = new Set(['--live', '--summarize', '--help', '--output-dir']);
  let outputDir = 'research';
  for (let i = 0; i < argv.length; i++) {
    if (!allowed.has(argv[i])) throw new Error('UNKNOWN_ARGUMENT');
    if (argv[i] === '--output-dir') {
      if (!argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error('OUTPUT_DIR_REQUIRED');
      outputDir = argv[++i];
    }
  }
  if (argv.includes('--help')) {
    console.log('离线预览：node scripts/probe_jev_distributions.mjs\n付费执行：node --env-file=.env scripts/probe_jev_distributions.mjs --live\n仅重算本地摘要：node scripts/probe_jev_distributions.mjs --summarize\n可选 --output-dir DIR；并发 2，最多 40 次请求，预算 $1，超时 45 秒，不自动重试。');
    return;
  }
  if (argv.includes('--live') && argv.includes('--summarize')) throw new Error('SELECT_ONE_MODE');
  const cases = buildCases();
  // 仅含本地自写题目与解析参考分布，可供已冻结学生做同题额外诊断。
  // 不含教师响应，不得将该诊断集合用于重训或选择模型。
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'distribution_probe_inputs.json'), JSON.stringify({
    schema_version: CONFIG.schema_version,
    purpose: 'frozen_model_diagnostic_only_no_training_or_model_selection',
    reference_kind: 'analytically_defined_conditional_distribution_not_observed_outcome',
    cases,
  }, null, 2) + '\n');
  if (!argv.includes('--live')) {
    const events = await readLedger(path.join(outputDir, 'private_distribution_probe.jsonl'));
    if (argv.includes('--summarize')) {
      const summary = await writeSummary(outputDir, cases, events, 'offline_summary');
      console.log(JSON.stringify({ mode: summary.mode, successful_evaluations: summary.successful_evaluations, complete: summary.complete }));
    } else {
      const existing = inspectLedger(events, cases);
      console.log(JSON.stringify({
        mode: 'offline_preview_no_api_calls_no_env_reads', settings: CONFIG,
        total_cases: cases.length, total_reserve_if_all_requests_in_flight_usd: sum(cases.map(requestReserve)),
        existing_attempts: existing.started.size, existing_successes: existing.successes.length,
        blocked_by_previous_failure_or_unresolved: existing.failures.length + existing.unresolved.length > 0,
        planned_cases: cases.map(({ id, K, case_family, permutation, input_sha256 }) => ({ id, K, case_family, permutation, input_sha256 })),
        example: cases[0],
      }, null, 2));
    }
    return;
  }
  const { evaluateTeacher } = await import('./teachers.mjs');
  const summary = await runProbe({ outputDir, cases, evaluate: evaluateTeacher });
  console.log(JSON.stringify({ mode: summary.mode, successful_evaluations: summary.successful_evaluations, failed_evaluations: summary.failed_evaluations,
    dispatched_evaluations: summary.dispatched_evaluations, actual_known_cost_usd: summary.actual_known_cost_usd, complete: summary.complete, stopped_reason: summary.stopped_reason }));
  if (!summary.complete) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main(process.argv.slice(2)).catch(() => {
    console.error(JSON.stringify({ error: 'PROBE_STOPPED_CHECK_LOCAL_LEDGER', automatic_retries: 0 }));
    process.exitCode = 1;
  });
}
