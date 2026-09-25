import { useRef, useState } from 'react';

type Answer = { model?: string; answers?: Record<string, { choice?: string; confidence?: number; probabilities?: Record<string, number>; noul?: number }> };
type Sample = { input: Record<string, unknown>; output?: Answer; ms?: number; selected?: string; error?: string };
export function useDecisionLab() {
  const [sample, setSample] = useState<Sample | null>(null);
  const [stats, setStats] = useState({ calls: 0, successes: 0, totalMs: 0, errors: 0, overrides: 0 });
  const generation = useRef(0);
  const reset = () => { generation.current++; setSample(null); setStats({ calls: 0, successes: 0, totalMs: 0, errors: 0, overrides: 0 }); };
  const request = async (url: string, input: Record<string, unknown>) => {
    const version = generation.current;
    const start = performance.now();
    setSample({ input: structuredClone(input) });
    setStats(s => ({ ...s, calls: s.calls + 1 }));
    try {
      const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) });
      if (!response.ok) throw new Error(`Jev 请求失败（HTTP ${response.status}）`);
      const output: Answer = await response.json();
      if (!output.answers) throw new Error('Jev 响应缺少决策结果');
      if (version !== generation.current) throw new Error('本次请求已取消');
      const ms = Math.round(performance.now() - start);
      setSample({ input: structuredClone(input), output, ms });
      setStats(s => ({ ...s, successes: s.successes + 1, totalMs: s.totalMs + ms }));
      return output;
    } catch (error) {
      if (version === generation.current) { setSample({ input, error: error instanceof Error ? error.message : '请求失败' }); setStats(s => ({ ...s, errors: s.errors + 1 })); }
      throw error;
    }
  };
  const executed = (selected: string, original?: string) => {
    setSample(s => s ? { ...s, selected } : s);
    if (original && selected !== original) setStats(s => ({ ...s, overrides: s.overrides + 1 }));
  };
  return { sample, stats, request, executed, reset };
}

const names: Record<string, string> = { up: '↑ 向上', down: '↓ 向下', left: '← 向左', right: '→ 向右' };
function label(value?: string) {
  if (!value) return '—';
  const match = value.match(/^(reveal|flag)_(\d+)_(\d+)$/);
  return match ? `${match[1] === 'flag' ? '插旗' : '翻开'} · ${Number(match[2]) + 1} 行 ${Number(match[3]) + 1} 列` : names[value] ?? value;
}
export function DecisionLab({ lab, game, paused }: { lab: ReturnType<typeof useDecisionLab>; game: 'snake' | 'mines'; paused: boolean }) {
  const { sample, stats } = lab;
  const decision = sample?.output?.answers?.[game === 'snake' ? 'move' : 'action'];
  const candidates = (sample?.input[game === 'snake' ? 'legalMoves' : 'actions'] ?? []) as string[];
  const waiting = !!sample && !sample.output && !sample.error;
  return <div className="decision-lab">
    <section className="lab-panel"><div className="lab-heading"><span>LIVE TELEMETRY</span><span className={waiting ? 'lab-pulse' : ''}>{paused ? '已暂停' : waiting ? '等待 Jev' : sample?.error ? '请求失败' : sample ? '已收到结果' : '尚未调用'}</span></div><h2>每一步，都有据可查</h2><dl className="lab-stats"><div><dt>调用次数</dt><dd>{stats.calls}</dd></div><div><dt>平均响应</dt><dd>{stats.successes ? `${Math.round(stats.totalMs / stats.successes)} ms` : '—'}</dd></div><div><dt>系统调整动作</dt><dd>{stats.overrides}</dd></div><div><dt>API 错误</dt><dd>{stats.errors}</dd></div><div><dt>实际模型</dt><dd>{sample?.output?.model ?? '—'}</dd></div></dl>{sample?.error && <p role="alert" className="lab-error">{sample.error}</p>}</section>
    <section className="lab-panel"><div className="lab-heading"><span>CURRENT DECISION</span><span>{candidates.length} 个候选</span></div><h2>{waiting ? '这一刻，Jev 正在选择' : '模型选择 → 实际执行'}</h2><div className="lab-result"><span>Jev 返回<b>{label(decision?.choice)}</b></span><span>执行动作<b>{label(sample?.selected)}</b></span></div>{sample?.selected && sample.selected !== decision?.choice && <p className="lab-note">系统调整了模型选择。下方保留原始响应，可核对两者区别。</p>}<p className="lab-note">条形表示模型返回的候选分布，不代表获胜概率。未返回数值时显示“—”。</p><div className="lab-candidates">{candidates.map(action => {
      const probability = decision?.probabilities?.[action];
      const mine = sample?.output?.answers?.[`mine_${action.split('_').slice(1).join('_')}`]?.noul;
      return <div className={`lab-candidate ${decision?.choice === action ? 'chosen' : ''}`} key={action}><div><strong>{label(action)}</strong><span>{probability === undefined ? '—' : `${Math.round(probability * 100)}%`}</span></div><div className="lab-bar"><i style={{ width: `${Math.max(0, Math.min(1, probability ?? 0)) * 100}%` }} /></div><small>{game === 'snake' ? action === sample?.input.plannedDirection ? '路径搜索给出的参考方向' : '当前棋盘允许的方向' : mine !== undefined ? `Jev 估计有雷：${Math.round(mine * 100)}%` : '候选列表中的动作'}{decision?.choice === action ? ' · 模型选中' : ''}</small></div>;
    })}{!candidates.length && <p className="lab-empty">启动 Jev 后，这里会展示本轮真正发送的候选动作及返回结果。</p>}</div></section>
    <section className="lab-panel"><div className="lab-heading"><span>REQUEST / RESPONSE</span><span>{sample?.ms !== undefined ? `${sample.ms} ms` : '—'}</span></div><details><summary>查看发送给服务端的状态</summary><pre>{sample ? JSON.stringify(sample.input, null, 2) : '尚无请求'}</pre></details><details><summary>查看 Jev 原始响应</summary><pre>{sample?.output ? JSON.stringify(sample.output, null, 2) : '尚无响应'}</pre></details></section>
  </div>;
}
