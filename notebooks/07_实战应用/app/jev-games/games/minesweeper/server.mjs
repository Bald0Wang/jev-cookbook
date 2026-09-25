import { createServer } from 'node:http';
import { readFile, writeFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const preferredPort = Number(process.env.PORT || 4174);
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8' };

try {
  const envText = await readFile(join(root, '.env'), 'utf8');
  for (const line of envText.split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (match && !process.env[match[1]]) process.env[match[1]] = match[2].replace(/^['"]|['"]$/g, '');
  }
} catch {}

async function readBody(req) { let body = ''; for await (const chunk of req) body += chunk; return JSON.parse(body || '{}'); }
function send(res, status, data) { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(data)); }
async function callJev(payload, res) {
  if (!process.env.TYPESAFE_API_KEY) return send(res, 503, { error: 'TYPESAFE_API_KEY is not configured.' });
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const upstream = await fetch('https://api.typesafe.ai/v1/systemone', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.TYPESAFE_API_KEY}` }, body: JSON.stringify(payload) });
      const text = await upstream.text(); res.writeHead(upstream.status, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(text); return;
    } catch { if (attempt === 1) return send(res, 502, { error: 'TypeSafe request failed.' }); await new Promise(resolve => setTimeout(resolve, 250)); }
  }
}
async function move(req, res) {
  const state = await readBody(req);
  const actions = (Array.isArray(state.actions) && state.actions.length ? state.actions : ['reveal_0_0']).slice(0, 24);
  const criteria = Object.fromEntries(actions.map(action => {
    const [kind, row, col] = action.split('_');
    const label = `${kind === 'flag' ? 'flag' : 'reveal'} row ${row}, column ${col}`;
    const risk = state.riskCandidates?.find(item => item.key === `${row},${col}`)?.risk;
    const hint = state.safeReveals?.includes(`${row},${col}`) && kind === 'reveal' ? ' This is a logically certain safe reveal.' : state.suspectedMines?.includes(`${row},${col}`) && kind === 'flag' ? ' This cell is logically suspected to contain a mine.' : risk != null ? ` Estimated local mine risk is ${Math.round(risk * 100)}%.` : '';
    return [action, `${label}.${hint}`];
  }));
  const revealActions = actions.filter(action => action.startsWith('reveal_'));
  const riskQuestions = Object.fromEntries(revealActions.map(action => { const [, row, col] = action.split('_'); return [`mine_${row}_${col}`, { type: 'noul', instructions: `Is the Minesweeper cell at row ${row}, column ${col} a mine based only on the visible board and nearby numbered clues?`, criteria: { true: 'The visible clues support that this cell is a mine.', false: 'The visible clues support that this cell is safe to reveal.' } }]; }));
  const payload = { state, model: 'jev-latest', questions: { action: { type: 'choice', instructions: 'Play Minesweeper. Choose exactly one action from the actions list. Prefer logically certain safe reveals. Flag only cells supported by nearby numbers. If no certain move exists, choose the reveal with the strongest evidence of being safe and avoid repeating recent actions.', criteria }, ...riskQuestions } };
  return callJev(payload, res);
}
const server = createServer(async (req, res) => {
  try {
    if (req.method === 'POST' && req.url === '/api/move') return move(req, res);
    if (req.method === 'POST' && req.url === '/api/trace') { const body = await readBody(req); await writeFile(join(root, 'trace-live.json'), JSON.stringify(body)); return send(res, 200, { saved: true }); }
    if (req.method === 'GET' && req.url === '/api/status') return process.env.TYPESAFE_API_KEY ? send(res, 200, { configured: true }) : send(res, 503, { configured: false });
    if (req.method !== 'GET') return send(res, 405, { error: 'Method not allowed' });
    const pathname = req.url === '/' ? '/index.html' : req.url.split('?')[0];
    const file = normalize(join(root, pathname));
    if (!file.startsWith(root)) return send(res, 403, { error: 'Forbidden' });
    const content = await readFile(file); res.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' }); res.end(content);
  } catch { send(res, 404, { error: 'Not found' }); }
});
function listenOn(port) { server.once('error', error => { if (error.code === 'EADDRINUSE') return listenOn(port + 1); throw error; }); server.listen(port, () => console.log(`Minesweeper running at http://localhost:${port}`)); }
listenOn(preferredPort);
