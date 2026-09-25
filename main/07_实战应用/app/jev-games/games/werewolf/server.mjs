import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { basename, extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  PLAYER_IDS,
  PLAYER_NAMES,
  buildPrivateState,
  buildPublicState,
  createGame,
  debugSnapshot,
  applyHumanMessage,
  applyHumanVote,
  isAlive,
  legalTargets,
  recordEvent,
  resolveNight,
  resolveVotes,
  roleOf,
  seededPick,
  appendTranscript
} from './game-engine.mjs';
import { decideForAgent, hasApiKey, humanFallbackDecision, speechFromDecision } from './jev-agent.mjs';
import { hasDeepSeekKey } from './cognition.mjs';
import { renderSpeech } from './dialogue.mjs';

const root = fileURLToPath(new URL('.', import.meta.url));
const traceRoot = join(root, 'trace');
const preferredPort = Number(process.env.PORT || 4175);
const mime = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml'
};
const games = new Map();

try {
  const envText = await readFile(join(root, '.env'), 'utf8');
  for (const line of envText.split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (match && !process.env[match[1]]) process.env[match[1]] = match[2].replace(/^['"]|['"]$/g, '');
  }
} catch {}

function send(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(data));
}

async function readBody(req) {
  let body = '';
  for await (const chunk of req) body += chunk;
  if (body.length > 100_000) throw new Error('Request body too large');
  return JSON.parse(body || '{}');
}

function publicResponse(game) {
  return { game: buildPublicState(game), privateState: buildPrivateState(game, game.humanId) };
}

function ensureGame(id) {
  const game = games.get(id);
  if (!game) throw new Error('Game not found');
  return game;
}

function nextReplayEvent(game, type) {
  if (game.mode !== 'replay' || !game.replayEvents) return null;
  for (let index = game.replayEventCursor; index < game.replayEvents.length; index += 1) {
    const event = game.replayEvents[index];
    if (event.type === type) {
      game.replayEventCursor = index + 1;
      return event;
    }
  }
  return null;
}

async function saveTrace(game) {
  await mkdir(traceRoot, { recursive: true });
  const filename = join(traceRoot, `${game.id}.json`);
  await writeFile(filename, JSON.stringify(game.trace, null, 2));
  return filename;
}

async function decide(game, agentId, phase) {
  if (agentId === game.humanId && game.mode !== 'replay') return humanFallbackDecision(game, agentId, phase);
  return decideForAgent(game, agentId, phase);
}

async function runNight(game) {
  const wolfVotes = {};
  const wolves = PLAYER_IDS.filter(id => isAlive(game, id) && roleOf(game, id) === 'werewolf');
  const seer = PLAYER_IDS.find(id => isAlive(game, id) && roleOf(game, id) === 'seer');
  const [wolfDecisions, seerDecision] = await Promise.all([
    Promise.all(wolves.map(async wolf => [wolf, await decide(game, wolf, 'night_wolf')])),
    seer ? decide(game, seer, 'night_seer') : Promise.resolve(null)
  ]);
  for (const [wolf, decision] of wolfDecisions) wolfVotes[wolf] = decision.target;
  const seerChoice = seerDecision ? { seer, target: seerDecision.target } : null;
  const witch = PLAYER_IDS.find(id => isAlive(game, id) && roleOf(game, id) === 'witch');
  let witchSave = false;
  let witchPoison = null;
  if (witch) {
    game.night = { wolfVotes, consensusTarget: null };
    // The consensus preview is needed so the witch receives the legal death candidate.
    const choices = [...new Set(Object.values(wolfVotes).filter(Boolean))];
    game.night.consensusTarget = choices.length === 1 ? choices[0] : seededPick(game, choices) || null;
    const decision = await decide(game, witch, 'night_witch');
    witchSave = decision.save === true;
    witchPoison = decision.poisonTarget || null;
  }
  const consensusTarget = game.night?.consensusTarget || null;
  resolveNight(game, { wolfVotes, consensusTarget, seerChoice, witchSave, witchPoison });
}

async function advanceGameUnlocked(game) {
  game.awaitingHuman = null;
  while (true) {
    if (game.phase === 'finished') return publicResponse(game);
    if (game.phase === 'night') {
      await runNight(game);
      if (game.phase === 'finished') return publicResponse(game);
      if (game.awaitingHuman === 'spectate') return publicResponse(game);
      continue;
    }
    if (game.phase === 'day_discussion') {
      for (let index = game.pending.speakerIndex || 0; index < PLAYER_IDS.length; index += 1) {
        game.pending.speakerIndex = index + 1;
        const speaker = PLAYER_IDS[index];
        if (!isAlive(game, speaker)) continue;
        if (speaker === game.humanId) {
          const replayEvent = nextReplayEvent(game, 'human_message');
          if (replayEvent) {
            applyHumanMessage(game, replayEvent.text);
            continue;
          }
          game.pending.speaker = speaker;
          game.awaitingHuman = 'message';
          return publicResponse(game);
        }
        const decision = await decide(game, speaker, 'day_speech');
        const rendered = speechFromDecision(game, speaker, decision);
        if (rendered) {
          appendTranscript(game, { speaker, type: 'jev_message', text: rendered.text, intent: rendered.intent, target: rendered.target, evidence: rendered.evidence, source: rendered.source || 'template_fallback', decisionSeq: game.trace.decisions.at(-1)?.seq || null });
          recordEvent(game, { type: 'jev_message', speaker, decision, rendered });
        } else {
          const silent = renderSpeech({ intent: 'remain_silent', evidence: 'low_information' });
          appendTranscript(game, { speaker, type: 'jev_message', text: silent?.text || '我暂时保留意见。', intent: 'remain_silent', target: null, evidence: 'low_information', decisionSeq: game.trace.decisions.at(-1)?.seq || null });
          recordEvent(game, { type: 'jev_message', speaker, decision, rendered: null });
        }
      }
      game.phase = 'voting';
      game.pending.voters = [...game.alive];
      game.pending.voterIndex = 0;
      game.pending.votes = {};
      continue;
    }
    if (game.phase === 'voting') {
      const voters = game.pending.voters || [...game.alive];
      for (let index = game.pending.voterIndex || 0; index < voters.length; index += 1) {
        game.pending.voterIndex = index + 1;
        const voter = voters[index];
        if (!isAlive(game, voter)) continue;
        if (voter === game.humanId) {
          const replayEvent = nextReplayEvent(game, 'human_vote');
          if (replayEvent) {
            applyHumanVote(game, replayEvent.target);
            continue;
          }
          game.pending.voter = voter;
          game.awaitingHuman = 'vote';
          return publicResponse(game);
        }
        const decision = await decide(game, voter, 'vote');
        const legal = legalTargets(game, voter, 'vote');
        const target = legal.includes(decision.target) ? decision.target : legal[0];
        game.pending.votes[voter] = target;
        recordEvent(game, { type: 'jev_vote', voter, target, decision });
      }
      resolveVotes(game, game.pending.votes || {});
      continue;
    }
    throw new Error(`Unknown phase ${game.phase}`);
  }
}

function advanceGame(game) {
  if (game.advancePromise) return game.advancePromise;
  if (game.awaitingHuman && game.awaitingHuman !== 'spectate') return Promise.resolve(publicResponse(game));
  const promise = (async () => {
    try {
      return await advanceGameUnlocked(game);
    } finally {
      if (game.advancePromise === promise) game.advancePromise = null;
    }
  })();
  game.advancePromise = promise;
  return promise;
}

async function newGame(req, res) {
  const body = await readBody(req);
  let replayTrace = null;
  if (body.replay && body.traceId) {
    const traceName = basename(String(body.traceId)).replace(/\.json$/i, '');
    replayTrace = JSON.parse(await readFile(join(traceRoot, `${traceName}.json`), 'utf8'));
  }
  const mode = replayTrace ? 'replay' : (body.mode === 'offline' || !hasApiKey() ? 'offline' : 'auto');
  const options = { seed: body.seed ?? replayTrace?.seed, humanSeat: body.humanSeat, mode, ruleset: body.ruleset || 'demo', replayTrace };
  if (replayTrace?.roles) options.fixedRoles = replayTrace.roles;
  if (body.debug && body.fixedRoles) options.fixedRoles = body.fixedRoles;
  const game = createGame(options);
  games.set(game.id, game);
  recordEvent(game, { type: 'mode_selected', mode: game.mode, ruleset: game.ruleset, apiConfigured: hasApiKey(), deepseekConfigured: hasDeepSeekKey() });
  return send(res, 200, publicResponse(game));
}

async function gameState(req, res, id) {
  return send(res, 200, publicResponse(ensureGame(id)));
}

async function advance(req, res, id) {
  return send(res, 200, await advanceGame(ensureGame(id)));
}

async function humanMessage(req, res, id) {
  const game = ensureGame(id);
  const body = await readBody(req);
  applyHumanMessage(game, body.text);
  return send(res, 200, await advanceGame(game));
}

async function humanVote(req, res, id) {
  const game = ensureGame(id);
  const body = await readBody(req);
  applyHumanVote(game, body.target);
  return send(res, 200, await advanceGame(game));
}

async function revealDebug(req, res, id) {
  const game = ensureGame(id);
  game.debugRevealed = true;
  return send(res, 200, debugSnapshot(game));
}

async function saveTraceEndpoint(req, res) {
  const body = await readBody(req);
  const game = ensureGame(body.gameId);
  const filename = await saveTrace(game);
  return send(res, 200, { saved: true, gameId: game.id, filename: filename.replace(`${root}`, '').replaceAll('\\', '/') });
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    const parts = url.pathname.split('/').filter(Boolean);
    if (req.method === 'POST' && url.pathname === '/api/game/new') return await newGame(req, res);
    if (parts[0] === 'api' && parts[1] === 'game' && parts[2]) {
      const id = parts[2];
      if (req.method === 'GET' && parts.length === 3) return await gameState(req, res, id);
      if (req.method === 'POST' && parts[3] === 'advance') return await advance(req, res, id);
      if (req.method === 'POST' && parts[3] === 'human-message') return await humanMessage(req, res, id);
      if (req.method === 'POST' && parts[3] === 'vote') return await humanVote(req, res, id);
      if (req.method === 'POST' && parts[3] === 'reveal-debug') return await revealDebug(req, res, id);
    }
    if (req.method === 'POST' && url.pathname === '/api/trace') return await saveTraceEndpoint(req, res);
    if (req.method === 'GET' && url.pathname === '/api/status') return send(res, 200, { configured: hasApiKey(), defaultPort: 4175 });
    if (req.method !== 'GET') return send(res, 405, { error: 'Method not allowed' });
    const pathname = url.pathname === '/' ? '/index.html' : url.pathname;
    if (pathname.startsWith('/trace/') || pathname === '/.env' || pathname.includes('/.env')) return send(res, 403, { error: 'Forbidden' });
    const file = normalize(join(root, pathname));
    if (!file.startsWith(root)) return send(res, 403, { error: 'Forbidden' });
    const content = await readFile(file);
    res.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' });
    res.end(content);
  } catch (error) {
    const status = /not found/i.test(error?.message || '') ? 404 : 400;
    send(res, status, { error: error instanceof Error ? error.message : String(error) });
  }
});

function listenOn(port) {
  server.once('error', error => {
    if (error.code === 'EADDRINUSE') {
      const nextPort = port + 1;
      console.warn(`Port ${port} is already in use. Trying ${nextPort}...`);
      return listenOn(nextPort);
    }
    throw error;
  });
  server.listen(port, () => console.log(`Werewolf running at http://localhost:${port}`));
}

listenOn(preferredPort);
