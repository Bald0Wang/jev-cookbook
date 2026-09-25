import { createHash } from 'node:crypto';

export const SIZE = 14, MINES = 20, OPENING = 0;
export function neighbors(index) {
  const r = Math.floor(index / SIZE), c = index % SIZE, out = [];
  for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
    if ((dr || dc) && r + dr >= 0 && r + dr < SIZE && c + dc >= 0 && c + dc < SIZE) out.push((r + dr) * SIZE + c + dc);
  }
  return out;
}
export function makeBoard(seed) {
  let x = seed >>> 0;
  const random = () => { x += 0x6D2B79F5; let t = Math.imul(x ^ x >>> 15, 1 | x); t ^= t + Math.imul(t ^ t >>> 7, 61 | t); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const banned = new Set([OPENING, ...neighbors(OPENING)]);
  const choices = Array.from({length: SIZE * SIZE}, (_, i) => i).filter(i => !banned.has(i));
  for (let i = choices.length - 1; i > 0; i--) { const j = Math.floor(random() * (i + 1)); [choices[i], choices[j]] = [choices[j], choices[i]]; }
  const mines = choices.slice(0, MINES).sort((a, b) => a - b);
  return { seed, size: SIZE, mineCount: MINES, mines, id: createHash('sha256').update(JSON.stringify(mines)).digest('hex') };
}
export function initialGame(board) {
  const game = {visible: Array(SIZE * SIZE).fill('#'), status: 'playing', moves: 0};
  applyAction(game, board, {kind: 'reveal', cell: OPENING});
  game.moves = 0;
  return game;
}
export function applyAction(game, board, action) {
  if (game.status !== 'playing') throw Error('Game already ended');
  const {kind, cell} = action, value = game.visible[cell];
  if (!Number.isInteger(cell) || cell < 0 || cell >= SIZE * SIZE) throw Error('Invalid cell');
  if (kind === 'flag' && value === '#') game.visible[cell] = 'F';
  else if (kind === 'unflag' && value === 'F') game.visible[cell] = '#';
  else if (kind === 'reveal' && value === '#') {
    const mines = new Set(board.mines);
    if (mines.has(cell)) { game.visible[cell] = 'M'; game.status = 'lost'; }
    else {
      const queue = [cell];
      while (queue.length) {
        const i = queue.pop();
        if (game.visible[i] !== '#') continue;
        const count = neighbors(i).filter(j => mines.has(j)).length;
        game.visible[i] = String(count);
        if (count === 0) neighbors(i).filter(j => !mines.has(j) && game.visible[j] === '#').forEach(j => queue.push(j));
      }
    }
  } else throw Error('Illegal action');
  game.moves++;
  if (game.visible.filter(v => /^\d$/.test(v)).length === SIZE * SIZE - MINES) game.status = 'won';
}
export const cellName = i => `r${Math.floor(i / SIZE) + 1}c${i % SIZE + 1}`;
export function parseCell(name) {
  const m = /^r(\d+)c(\d+)$/.exec(name || '');
  return m ? (Number(m[1]) - 1) * SIZE + Number(m[2]) - 1 : -1;
}
// This function receives only visible cells. Hidden mine positions are never consulted.
export function deduce(visible) {
  const safe = new Set(), mines = new Set(), constraints = [], known = new Set();
  const add = (cells, count) => {
    if (!cells.length || count < 0 || count > cells.length) return;
    cells.sort((a,b) => a-b);
    const k = cells.join(',') + ':' + count;
    if (!known.has(k)) { known.add(k); constraints.push({cells, count}); }
  };
  visible.forEach((v,i) => {
    if (!/^\d$/.test(v)) return;
    const around = neighbors(i);
    add(around.filter(j => visible[j] === '#'), Number(v) - around.filter(j => visible[j] === 'F').length);
  });
  // Bounded subset closure over visible-number equations.
  for (let pass = 0; pass < 8 && constraints.length < 600; pass++) {
    const previous = constraints.length;
    for (const a of constraints.slice()) {
      if (a.count === 0) a.cells.forEach(i => safe.add(i));
      if (a.count === a.cells.length) a.cells.forEach(i => mines.add(i));
      for (const b of constraints.slice(0, previous)) {
        if (a.cells.length < b.cells.length && a.cells.every(i => b.cells.includes(i))) add(b.cells.filter(i => !a.cells.includes(i)), b.count - a.count);
      }
    }
    if (constraints.length === previous) break;
  }
  for (const a of constraints) { if (a.count === 0) a.cells.forEach(i => safe.add(i)); if (a.count === a.cells.length) a.cells.forEach(i => mines.add(i)); }
  if ([...safe].some(i => mines.has(i))) return {safe: [], mines: [], inconsistent: true};
  return {safe: [...safe], mines: [...mines], inconsistent: false};
}
export function makeRequest(game, variant) {
  const covered = game.visible.flatMap((v,i) => v === '#' ? [i] : []), flagged = game.visible.flatMap((v,i) => v === 'F' ? [i] : []);
  const state = {size: SIZE, totalMines: MINES, coordinates: 'Rows and columns start at 1; # is covered, F is a player flag (not guaranteed correct), 0-8 count adjacent mines.', board: Array.from({length: SIZE}, (_,r) => game.visible.slice(r*SIZE,(r+1)*SIZE))};
  const deduction = variant === 'shaped' ? deduce(game.visible) : null;
  let phase = 'model_choice', kinds = ['reveal', 'flag'], targets = covered;
  if (flagged.length) kinds.push('unflag');
  if (deduction) {
    state.deductions = {safe: deduction.safe.map(cellName), mines: deduction.mines.map(cellName), assumption: 'Existing flags are correct; deductions use visible clues and subset subtraction only.'};
    if (deduction.mines.length) { phase = 'certain_mines'; kinds = ['flag']; targets = deduction.mines; }
    else if (deduction.safe.length) { phase = 'certain_safe'; kinds = ['reveal']; targets = deduction.safe; }
    else { phase = 'guess'; kinds = ['reveal']; }
  }
  const choices = list => Object.fromEntries(list.map(i => [cellName(i), null]));
  const questions = {kind: {type: 'choice', instructions: 'Play Minesweeper. Choose the next action type: reveal a safe cell, flag a cell supported as a mine, or remove an incorrect flag. Avoid unnecessary guesses.', criteria: Object.fromEntries(kinds.map(k => [k, k]))}};
  for (const kind of kinds) questions[kind] = {type: 'choice', instructions: `If performing ${kind}, which cell should be targeted? Use visible numbered clues. Reveal the safest cell; flag only when clues support a mine.`, criteria: choices(kind === 'unflag' ? flagged : targets)};
  // Parallel risk questions are bounded to the same candidate set on uncertain turns.
  if (phase === 'guess') {
    // Keep all covered cells available to Choice. Noul evaluates up to 12 frontier cells.
    const frontier = covered.filter(i => neighbors(i).some(j => /^\d$/.test(game.visible[j]))).slice(0,12);
    for (const i of frontier) questions[`risk_${cellName(i)}`] = {type: 'noul', instructions: `Given visible clues, is ${cellName(i)} a mine?`};
  }
  return {payload: {model: 'jev-latest', state, questions}, phase, kinds, targets};
}
