const pair = window.MINESWEEPER_PAIR || {baseline:{events:[]}, shaped:{events:[]}};
const toReplay = run => (run.events || []).map(event => ({
  state: {visible: event.after?.status === 'lost' ? event.after.visible : (event.before?.visible || Array(196).fill('#')), actions: (event.request?.state?.board || []).flat().flatMap((value, index) => value === '#' ? [`reveal_${Math.floor(index / 14)}_${index % 14}`] : []), safeReveals: [], suspectedMines: [], riskCandidates: []},
  selected: event.action ? `${event.action.kind}_${Math.floor(event.action.cell / 14)}_${event.action.cell % 14}` : null,
  request: event.request,
  rawAnswer: event.answer,
  answer: {answers: {action: {type: 'choice', choice: event.action ? `${event.action.kind}_${Math.floor(event.action.cell / 14)}_${event.action.cell % 14}` : null, confidence: event.answer?.answers?.kind?.confidence || 0}}},
  action: event.action,
  after: event.after,
  openCount: (event.before?.visible || []).filter(value => /^\d$/.test(value)).length,
  flags: (event.before?.visible || []).filter(value => value === 'F').length,
  status: event.before?.status || 'playing'
}));
window.RECORDED_MINESWEEPER_BASELINE_TRACE = toReplay(pair.baseline);
window.RECORDED_MINESWEEPER_TRACE = toReplay(pair.shaped);
