import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { makeBoard, initialGame, applyAction, makeRequest, parseCell, cellName } from './mines-comparison-core.mjs';

const root = new URL('../', import.meta.url);
const seed = Number(process.argv[2] || 20260922);
const maxSteps = Number(process.argv[3] || 100);
const mode = process.argv[4] || 'pair';
const targetOutput = process.argv[5];
const resume = mode === 'shaped' ? JSON.parse(await readFile(pathToFileURL(targetOutput), 'utf8')) : null;
const board = resume?.board || makeBoard(seed);
const initial = initialGame(board);
let apiKey = process.env.TYPESAFE_API_KEY;
if (!apiKey) {
  const env = await readFile(new URL('games/minesweeper/.env', root), 'utf8');
  apiKey = env.match(/^\s*TYPESAFE_API_KEY\s*=\s*(.*?)\s*$/m)?.[1].replace(/^['"]|['"]$/g, '');
}
if (!apiKey) throw Error('Missing TYPESAFE_API_KEY');
const result = resume || {schemaVersion: 2, capturedAt: new Date().toISOString(), board, opening: {kind: 'reveal', cell: 0, actor: 'program', initial}, maxSteps, baseline: {events: []}, shaped: {events: []}};
const destination = targetOutput ? pathToFileURL(targetOutput) : new URL('showcase/jev-games/traces/minesweeper-pair.json', root);
async function save() { await writeFile(destination, JSON.stringify(result, null, 2)); }
async function run(variant) {
  const game = structuredClone(initial), events = result[variant].events;
  for (let step = 1; step <= maxSteps && game.status === 'playing'; step++) {
    const before = structuredClone(game), request = makeRequest(game, variant), started = Date.now();
    try {
      const response = await fetch('https://api.typesafe.ai/v1/systemone', {method: 'POST', headers: {'Content-Type':'application/json', Authorization: `Bearer ${apiKey}`}, body: JSON.stringify(request.payload), signal: AbortSignal.timeout(30000)});
      if (!response.ok) throw Error(`TypeSafe HTTP ${response.status}`);
      const answer = await response.json();
      const kind = answer.answers?.kind?.choice;
      const target = answer.answers?.[kind]?.choice;
      const criteria = request.payload.questions[kind]?.criteria || {};
      if (!request.kinds.includes(kind) || !Object.hasOwn(criteria, target)) throw Error(`Invalid model action ${kind} ${target}`);
      const action = {kind, cell: parseCell(target)};
      applyAction(game, board, action);
      events.push({step, timestamp: new Date().toISOString(), latencyMs: Date.now()-started, phase: request.phase, request: request.payload, answer, action, before, after: structuredClone(game)});
      if (step % 10 === 0 || game.status !== 'playing') console.log(variant, step, game.status, game.visible.filter(v => /^\d$/.test(v)).length);
    } catch (error) { result[variant].error = error.message; break; }
  }
  result[variant].endReason = result[variant].error ? 'api_error' : game.status === 'playing' ? 'step_limit' : game.status;
  result[variant].final = structuredClone(game);
}
// Independent runs share immutable board and opening; neither can see the other run.
function baselineRequest(game) {
  const covered = game.visible.flatMap((v,i) => v === '#' ? [i] : []);
  const state = {size:14, totalMines:20, board:Array.from({length:14},(_,r)=>game.visible.slice(r*14,(r+1)*14)), covered, actions:covered.map(i=>`reveal_${Math.floor(i/14)}_${i%14}`), moves:game.moves};
  const criteria = Object.fromEntries(covered.map(cell => [cellName(cell), 'Reveal this covered cell using only the visible board.']));
  return {payload:{model:'jev-latest',state,questions:{action:{type:'choice',instructions:'Choose one covered cell to reveal using only the currently visible board. Do not assume hidden history or hidden mine locations.',criteria}}},phase:'baseline',kinds:['reveal'],targets:covered};
}
if (mode === 'baseline') await run('baseline'); else if (mode === 'shaped') await run('shaped'); else await Promise.all([run('baseline'),run('shaped')]);
await save();
if (!targetOutput) await writeFile(new URL('showcase/jev-games/traces/minesweeper-pair.js', root), 'window.MINESWEEPER_PAIR = ' + JSON.stringify(result) + ';\n');
console.log(JSON.stringify({board:board.id, baseline:result.baseline.events.length, shaped:result.shaped.events.length, ends:[result.baseline.endReason,result.shaped.endReason], output:fileURLToPath(destination)}));
