import { useEffect, useState, type CSSProperties } from 'react';
import type { TraceEvent } from '../lib/trace';

type MineEvent = TraceEvent & { before?: { visible: string[] }; after?: { visible: string[] }; action?: { kind?: string; cell?: number }; request?: { state?: { size?: number } }; answer?: { answers?: Record<string, { choice?: string; confidence?: number }> } };
type Pair = { board: { size: number; mineCount: number }; baseline: { events: MineEvent[] }; shaped: { events: MineEvent[] } };

export default function MinesweeperComparePage() {
  const [pair, setPair] = useState<Pair | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { fetch('/traces/minesweeper-pair.json').then(r => r.json()).then(setPair); }, []);
  const total = Math.min(pair?.baseline.events.length ?? 0, pair?.shaped.events.length ?? 0);
  const index = total ? Math.min(step, total - 1) : 0;
  const oldEvent = pair?.baseline.events[index];
  const newEvent = pair?.shaped.events[index];
  useEffect(() => { if (!playing || !total) return; const timer = window.setInterval(() => setStep(v => { if (v >= total - 1) { setPlaying(false); return v; } return v + 1; }), 900); return () => window.clearInterval(timer); }, [playing, total]);
  const status = !pair ? '正在加载记录' : playing ? '两边同步播放' : '可以逐步查看';
  return <section className="react-compare">
    <div className="compare-head"><div><p className="eyebrow">REACT TRACE VIEWER / MINESWEEPER</p><h1>同一张雷盘，两种输入方式</h1><p>左边只给当前盘面，右边把规则、候选格和历史反馈一起交给 Jev。</p></div><span className="compare-status">{status}</span></div>
    <div className="compare-toolbar"><button className="primary-button" onClick={() => setPlaying(v => !v)}>{playing ? '暂停' : '播放'}</button><button onClick={() => setStep(v => Math.max(0, v - 1))}>←</button><button onClick={() => setStep(v => Math.min(Math.max(0, total - 1), v + 1))}>→</button><button onClick={() => { setPlaying(false); setStep(0); }}>重置</button><span>STEP {String(index + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</span></div>
    <div className="react-boards"><MineCard title="原始 Jev" subtitle="只传当前可见盘面" accent="#ff7773" event={oldEvent} size={pair?.board.size ?? 14} /><MineCard title="约束后 Jev" subtitle="状态、规则、候选和反馈" accent="#b7ff4a" event={newEvent} size={pair?.board.size ?? 14} /></div>
  </section>;
}

function MineCard({ title, subtitle, accent, event, size }: { title: string; subtitle: string; accent: string; event?: MineEvent; size: number }) {
  const cells = event?.after?.visible ?? event?.before?.visible ?? [];
  const action = event?.action;
  const choice = event?.answer?.answers?.[action?.kind ?? 'reveal']?.choice;
  const opened = cells.filter(cell => cell !== '#').length;
  const flags = cells.filter(cell => cell === 'F').length;
  const style = { '--accent': accent, '--grid': size } as CSSProperties;
  return <article className="react-board-card" style={style}><div className="react-card-head"><div><h2>{title}</h2><p>{subtitle}</p></div><span>RECORDED</span></div><div className="mine-grid">{cells.map((cell, i) => <div key={i} className={`mine-cell ${cell === '#' ? 'covered' : ''} ${cell === 'F' ? 'flagged' : ''} ${action?.cell === i ? 'selected' : ''}`}>{cell === '#' ? '' : cell === 'F' ? '⚑' : cell}</div>)}</div><div className="react-metrics"><b>{String(opened).padStart(2, '0')}<small>已打开</small></b><b>{String(flags).padStart(2, '0')}<small>旗帜</small></b><b>{String(event?.step ?? 0).padStart(2, '0')}<small>动作</small></b></div><div className="react-decision"><strong>Jev → {choice ?? action?.kind ?? '等待'}</strong><p>这一回合先读输入，再选择一个格子；右侧还会保留上一步的反馈。</p></div>{event && <details className="trace-details"><summary>查看这一回合的输入和输出</summary><div className="trace-columns"><div><label>输入</label><pre>{JSON.stringify(event.request?.state ?? event.before, null, 2)}</pre></div><div><label>输出</label><pre>{JSON.stringify(event.answer ?? event.action, null, 2)}</pre></div></div></details>}</article>;
}
