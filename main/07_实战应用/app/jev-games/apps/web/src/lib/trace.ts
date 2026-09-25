export type TraceEvent = {
  step: number;
  state?: Record<string, unknown>;
  answer?: Record<string, unknown>;
  selected?: string | null;
  status?: string;
  scoreAfter?: number;
  openCount?: number;
  flags?: number;
  timestamp?: string;
};

export type TraceRun = { events: TraceEvent[]; endReason?: string; capturedAt?: string };

export function traceLength(trace: TraceRun | null | undefined) { return trace?.events.length ?? 0; }
export function clampTraceStep(step: number, ...traces: Array<TraceRun | null | undefined>) {
  const max = Math.max(0, ...traces.map(traceLength).map(length => length - 1));
  return Math.min(Math.max(0, step), max);
}
