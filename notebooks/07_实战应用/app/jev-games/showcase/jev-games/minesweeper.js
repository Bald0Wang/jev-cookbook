const baseline = window.RECORDED_MINESWEEPER_BASELINE_TRACE || [];
const shaped = window.RECORDED_MINESWEEPER_TRACE || [];
const size = 14;
let frame = 0;
let playing = false;
let timer = null;
const oldCanvas = document.getElementById('oldBoard');
const newCanvas = document.getElementById('newBoard');
const oldCtx = oldCanvas.getContext('2d');
const newCtx = newCanvas.getContext('2d');

function draw(ctx, state, action) {
  const cell = ctx.canvas.width / size;
  ctx.fillStyle = '#0d1719';
  ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  ctx.strokeStyle = 'rgba(106,242,210,.07)';
  for (let i = 1; i < size; i++) {
    ctx.beginPath(); ctx.moveTo(i * cell, 0); ctx.lineTo(i * cell, ctx.canvas.height); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i * cell); ctx.lineTo(ctx.canvas.width, i * cell); ctx.stroke();
  }
  const values = state?.visible || Array(size * size).fill('#');
  values.forEach((value, index) => {
    const row = Math.floor(index / size), col = index % size;
    let fill = '#1b3036', color = '#91a6aa';
    if (value === 'F') { fill = '#3a3320'; color = '#f7d774'; }
    else if (value === 'M') { fill = '#45241c'; color = '#ff9b64'; }
    else if (value !== '#') { fill = '#0e1b1f'; color = value === '1' ? '#70d6ff' : value === '2' ? '#72e0a0' : value === '3' ? '#f5c36f' : '#db9cff'; }
    ctx.fillStyle = fill; ctx.fillRect(col * cell + 3, row * cell + 3, cell - 6, cell - 6);
    if (value !== '#') { ctx.fillStyle = color; ctx.font = `700 ${Math.floor(cell * .42)}px ui-monospace`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(value, col * cell + cell / 2, row * cell + cell / 2); }
  });
  if (action) {
    const parts = action.split('_'); const row = Number(parts[parts.length - 2]), col = Number(parts[parts.length - 1]);
    ctx.strokeStyle = '#b7ff4a'; ctx.lineWidth = 3; ctx.strokeRect(col * cell + 2, row * cell + 2, cell - 4, cell - 4);
  }
}

function render() {
  const total = Math.max(baseline.length, shaped.length, 1);
  const baseIndex = Math.min(frame, Math.max(0, baseline.length - 1));
  const shapedIndex = Math.min(frame, Math.max(0, shaped.length - 1));
  const base = baseline[baseIndex] || { state: { visible: Array(size * size).fill('#') }, answer: { answers: {} } };
  const improved = shaped[shapedIndex] || { state: { visible: Array(size * size).fill('#') }, answer: { answers: {} } };
  const oldAnswer = base.answer?.answers?.action || {};
  const newAnswer = improved.answer?.answers?.action || {};
  draw(oldCtx, base.state, base.selected); draw(newCtx, improved.state, improved.selected);
  document.getElementById('counter').textContent = `STEP ${String(frame + 1).padStart(2, '0')} / ${String(total).padStart(2, '0')}`;
  const openCount = state => (state?.visible || []).filter(value => value !== '#' && value !== 'F' && value !== 'M').length;
  const flagCount = state => (state?.visible || []).filter(value => value === 'F').length;
  document.getElementById('oldOpen').textContent = String(openCount(base.state)).padStart(2, '0');
  document.getElementById('oldFlags').textContent = String(flagCount(base.state)).padStart(2, '0');
  document.getElementById('oldMoves').textContent = String(baseIndex).padStart(2, '0');
  document.getElementById('newOpen').textContent = String(openCount(improved.state)).padStart(2, '0');
  document.getElementById('newFlags').textContent = String(flagCount(improved.state)).padStart(2, '0');
  document.getElementById('newMoves').textContent = String(shapedIndex).padStart(2, '0');
  document.getElementById('oldConf').textContent = `confidence ${Math.round((oldAnswer.confidence || 0) * 100)}%`;
  document.getElementById('newConf').textContent = `confidence ${Math.round((newAnswer.confidence || 0) * 100)}%`;
  document.getElementById('oldAction').textContent = base.selected ? `Jev → ${base.selected.split('_').slice(1).join(',')}` : '等待动作';
  document.getElementById('newAction').textContent = improved.selected ? `Jev → ${improved.selected.split('_').slice(0, 2).join(',')}` : '等待动作';
  document.getElementById('oldText').textContent = base.status === 'game_over' ? 'Jev 翻开的格子是雷，标准规则结束本局。' : '只根据当前可见棋盘选择下一格。';
  document.getElementById('newText').textContent = improved.selected?.startsWith('flag') ? '确定雷优先插旗，再继续推理。' : '先处理确定安全格，再比较风险。';
  document.getElementById('oldChips').innerHTML = ['visible board only', `reveal candidates: ${base.state?.actions?.length || 0}`].map(value => `<span class="chip">${value}</span>`).join('');
  document.getElementById('newChips').innerHTML = [`safe: ${improved.state?.safeReveals?.length || 0}`, `suspected: ${improved.state?.suspectedMines?.length || 0}`, `risk candidates: ${improved.state?.riskCandidates?.length || 0}`].map(value => `<span class="chip">${value}</span>`).join('');
  document.getElementById('stepStateTitle').textContent = `左右同一张雷盘 · 起手后可见格 ${openCount(base.state)}`;
  document.getElementById('stepStateText').textContent = '程序先翻开同一个安全起始格，后续状态来自各自的真实 Jev 运行。';
  document.getElementById('stepActionTitle').textContent = `原始 ${base.state?.actions?.length || 0} · 约束 ${improved.state?.actions?.length || 0}`;
  document.getElementById('stepActionText').textContent = '左边把未知格都交给 Jev；右边按确定雷、确定安全格和风险候选缩小范围。';
  document.getElementById('stepAnswerTitle').textContent = `原始 ${base.selected || '等待'} · 约束 ${improved.selected || '等待'}`;
  document.getElementById('stepAnswerText').textContent = `confidence：${Math.round((oldAnswer.confidence || 0) * 100)}% → ${Math.round((newAnswer.confidence || 0) * 100)}%。`;
  document.getElementById('stepFeedbackTitle').textContent = `原始 ${base.status || 'playing'} · 约束 ${improved.after?.status || 'playing'}`;
  document.getElementById('stepFeedbackText').textContent = '动作执行后的棋盘状态会成为下一步输入。';
  document.getElementById('baselineJson').textContent = JSON.stringify({board: base.request?.state, answer: base.answer, action: base.action}, null, 2);
  document.getElementById('shapedJson').textContent = JSON.stringify({board: improved.request?.state, answer: improved.answer, action: improved.action}, null, 2);
}

document.getElementById('play').addEventListener('click', () => { playing = !playing; document.getElementById('play').textContent = playing ? '暂停' : '播放'; if (playing) timer = setInterval(() => { if (frame >= Math.max(baseline.length, shaped.length) - 1) { playing = false; clearInterval(timer); document.getElementById('play').textContent = '播放'; return; } frame++; render(); }, 900); else clearInterval(timer); });
document.getElementById('next').addEventListener('click', () => { frame = Math.min(Math.max(baseline.length, shaped.length) - 1, frame + 1); render(); });
document.getElementById('prev').addEventListener('click', () => { frame = Math.max(0, frame - 1); render(); });
document.getElementById('reset').addEventListener('click', () => { frame = 0; playing = false; clearInterval(timer); document.getElementById('play').textContent = '播放'; render(); });
render();
