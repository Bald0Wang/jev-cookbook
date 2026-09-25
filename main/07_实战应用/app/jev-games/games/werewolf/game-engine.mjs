import { randomUUID } from 'node:crypto';

export const PLAYER_IDS = ['human', 'jev_1', 'jev_2', 'jev_3', 'jev_4', 'jev_5'];
export const PLAYER_NAMES = {
  human: '你',
  jev_1: 'Jev-1',
  jev_2: 'Jev-2',
  jev_3: 'Jev-3',
  jev_4: 'Jev-4',
  jev_5: 'Jev-5'
};
export const ROLES = ['werewolf', 'werewolf', 'seer', 'witch', 'villager', 'villager'];
export const GOOD_ROLES = new Set(['seer', 'witch', 'villager']);
export const ROLE_LABELS = {
  werewolf: '狼人',
  seer: '预言家',
  witch: '女巫',
  villager: '村民'
};
export const POLICY_PROFILES = {
  jev_1: '谨慎：优先引用已经公开的投票证据，低置信度时保留意见。',
  jev_2: '证据导向：关注身份声明冲突和查验结果，避免无依据跳跃。',
  jev_3: '主动：快速形成候选嫌疑人，但会在新信息出现后调整判断。',
  jev_4: '社交：重视发言顺序、过度辩护和跟票行为。',
  jev_5: '共识：比较多数意见，同时保留对高风险跟票的怀疑。'
};

function hashString(value) {
  let hash = 2166136261;
  for (const char of String(value)) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function normalizeSeed(value) {
  if (value === undefined || value === null || value === '') {
    const bytes = new Uint32Array(1);
    try {
      globalThis.crypto?.getRandomValues(bytes);
    } catch {
      bytes[0] = Date.now() >>> 0;
    }
    return bytes[0] >>> 0;
  }
  if (typeof value === 'number' && Number.isFinite(value)) return (value >>> 0);
  const asNumber = Number(value);
  return Number.isFinite(asNumber) ? (asNumber >>> 0) : hashString(value);
}

export function stableRandom(seed) {
  let state = normalizeSeed(seed) || 0x6d2b79f5;
  return {
    get state() { return state >>> 0; },
    set state(value) { state = value >>> 0; },
    next() {
      state = (state + 0x6d2b79f5) >>> 0;
      let t = state;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    },
    pick(items) { return items.length ? items[Math.floor(this.next() * items.length)] : undefined; }
  };
}

function nextRandom(game) {
  const rng = stableRandom(game.rngState);
  const value = rng.next();
  game.rngState = rng.state;
  return value;
}

export function seededPick(game, items) {
  if (!items.length) return undefined;
  return items[Math.floor(nextRandom(game) * items.length)];
}

function shuffle(game, values) {
  const result = [...values];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const other = Math.floor(nextRandom(game) * (index + 1));
    [result[index], result[other]] = [result[other], result[index]];
  }
  return result;
}

function validateFixedRoles(fixedRoles) {
  const roleByPlayer = Array.isArray(fixedRoles)
    ? Object.fromEntries(PLAYER_IDS.map((id, index) => [id, fixedRoles[index]]))
    : { ...fixedRoles };
  if (PLAYER_IDS.some(id => !ROLES.includes(roleByPlayer[id]))) throw new Error('fixedRoles must assign a valid role to every player');
  const counts = Object.fromEntries(Object.keys(ROLE_LABELS).map(role => [role, 0]));
  for (const role of Object.values(roleByPlayer)) counts[role] += 1;
  for (const role of Object.keys(counts)) {
    const expected = ROLES.filter(item => item === role).length;
    if (counts[role] !== expected) throw new Error(`fixedRoles has invalid count for ${role}`);
  }
  return roleByPlayer;
}

export function createGame(options = {}) {
  const seed = normalizeSeed(options.seed);
  const humanId = options.humanSeat || 'human';
  if (!PLAYER_IDS.includes(humanId)) throw new Error(`Unknown humanSeat: ${humanId}`);
  const game = {
    id: options.id || `werewolf-${randomUUID()}`,
    seed,
    rngState: seed || 0x6d2b79f5,
    humanId,
    phase: 'night',
    round: 1,
    alive: [...PLAYER_IDS],
    roleByPlayer: {},
    publicClaims: {},
    publicTranscript: [],
    voteHistory: [],
    nightResults: [],
    memory: Object.fromEntries(PLAYER_IDS.map(id => [id, []])),
    nightKnowledge: Object.fromEntries(PLAYER_IDS.map(id => [id, []])),
    usedAbilities: Object.fromEntries(PLAYER_IDS.map(id => [id, { save: false, poison: false }])),
    pending: { speakerIndex: 0, voters: [], voterIndex: 0 },
    awaitingHuman: null,
    winner: null,
    lastOutcome: null,
    mode: options.mode || 'scripted',
    ruleset: options.ruleset || 'demo',
    replayDecisions: options.replayTrace?.decisions || null,
    replayCursor: 0,
    replayEvents: options.replayTrace?.events || null,
    replayEventCursor: 0,
    debugRevealed: false,
    trace: {
      version: 1,
      gameId: options.id || null,
      seed,
      createdAt: new Date().toISOString(),
      mode: options.mode || 'scripted',
      decisions: [],
      events: []
    }
  };
  game.trace.gameId = game.id;
  if (options.fixedRoles) {
    game.roleByPlayer = validateFixedRoles(options.fixedRoles);
  } else {
    const rng = stableRandom(seed);
    const permutation = [...ROLES];
    for (let index = permutation.length - 1; index > 0; index -= 1) {
      const other = Math.floor(rng.next() * (index + 1));
      [permutation[index], permutation[other]] = [permutation[other], permutation[index]];
    }
    game.roleByPlayer = Object.fromEntries(PLAYER_IDS.map((id, index) => [id, permutation[index]]));
    game.rngState = rng.state;
  }
  game.trace.roles = { ...game.roleByPlayer };
  recordEvent(game, { type: 'game_created', seed, humanId, rolesAssigned: true });
  return game;
}

export function recordEvent(game, event) {
  game.trace.events.push({ seq: game.trace.events.length + 1, ...event });
}

export function recordDecision(game, decision) {
  game.trace.decisions.push({ seq: game.trace.decisions.length + 1, ...decision });
}

export function roleOf(game, playerId) {
  return game.roleByPlayer[playerId];
}

export function isAlive(game, playerId) {
  return game.alive.includes(playerId);
}

export function factionOf(role) {
  return role === 'werewolf' ? 'werewolf' : 'good';
}

export function legalTargets(game, actorId, action) {
  if (!isAlive(game, actorId)) return [];
  if (action === 'kill') return game.alive.filter(id => id !== actorId && roleOf(game, id) !== 'werewolf');
  if (action === 'inspect') return game.alive.filter(id => id !== actorId);
  if (action === 'poison') return game.alive.filter(id => id !== actorId);
  if (action === 'vote') return game.alive.filter(id => id !== actorId);
  return [];
}

export function buildPublicState(game) {
  const publicDecisions = game.trace.decisions.filter(item => {
    if (item.phase === 'day_speech') return true;
    if (item.phase === 'vote') return game.voteHistory.some(vote => vote.round === item.round);
    return false;
  }).map(item => {
    const choice = item.choice || {};
    const publicChoice = item.phase === 'day_speech'
      ? { intent: choice.intent || null, target: choice.target || null, claim: choice.claim || null, evidence: choice.evidence || 'low_information', shouldSpeak: choice.shouldSpeak !== false }
      : { target: choice.target || null };
    const probabilities = Object.entries(item.probabilities || {}).sort(([, a], [, b]) => b - a).slice(0, 3).map(([target, probability]) => ({ target, probability }));
    return { seq: item.seq, round: item.round, phase: item.phase, agentId: item.agentId, mode: item.mode, confidence: item.confidence ?? 0, choice: publicChoice, probabilities };
  });
  const latestDecision = new Map();
  for (const decision of publicDecisions) latestDecision.set(decision.agentId, decision);
  return {
    gameId: game.id,
    seed: game.seed,
    mode: game.mode,
    ruleset: game.ruleset,
    phase: game.phase,
    round: game.round,
    alive: [...game.alive],
    players: PLAYER_IDS.map(id => ({ id, name: PLAYER_NAMES[id], alive: isAlive(game, id), claim: game.publicClaims[id] || null, lastDecision: latestDecision.get(id) || null })),
    publicClaims: { ...game.publicClaims },
    publicTranscript: game.publicTranscript.map(item => ({ ...item })),
    voteHistory: game.voteHistory.map(item => ({ ...item, votes: { ...item.votes }, tally: { ...item.tally } })),
    nightResults: game.nightResults.map(item => ({ ...item, dead: [...item.dead] })),
    awaitingHuman: game.awaitingHuman,
    humanId: game.humanId,
    winner: game.winner,
    lastOutcome: game.lastOutcome,
    publicDecisions
  };
}

function privateRoleInfo(game, agentId) {
  const role = roleOf(game, agentId);
  const teammates = role === 'werewolf' ? game.alive.filter(id => id !== agentId && roleOf(game, id) === 'werewolf') : [];
  const abilities = [];
  if (role === 'seer') abilities.push('inspect');
  if (role === 'witch') abilities.push(...(!game.usedAbilities[agentId].save ? ['save'] : []), ...(!game.usedAbilities[agentId].poison ? ['poison'] : []));
  if (role === 'werewolf') abilities.push('kill');
  return { role, teammates, availableAbilities: abilities };
}

export function buildPrivateState(game, agentId) {
  const info = privateRoleInfo(game, agentId);
  const state = {
    agentId,
    role: info.role,
    teammates: info.teammates,
    nightKnowledge: game.nightKnowledge[agentId].map(item => ({ ...item })),
    availableAbilities: info.availableAbilities,
    memorySummary: [...game.memory[agentId]],
    policy: POLICY_PROFILES[agentId] || '遵守角色规则，依据公开信息行动。'
  };
  if (info.role === 'witch' && game.phase === 'night') {
    state.nightDeathCandidate = game.night?.consensusTarget || null;
    state.potions = { save: !game.usedAbilities[agentId].save, poison: !game.usedAbilities[agentId].poison };
  }
  return state;
}

export function buildAgentState(game, agentId) {
  return { publicState: buildPublicState(game), privateState: buildPrivateState(game, agentId), memory: [...game.memory[agentId]], policy: POLICY_PROFILES[agentId] || '' };
}

export function appendTranscript(game, item) {
  game.publicTranscript.push({ seq: game.publicTranscript.length + 1, ...item });
  for (const id of PLAYER_IDS) {
    if (id !== game.humanId && game.memory[id].length < 12) game.memory[id].push(item.text || `${item.type || 'event'}: ${item.target || ''}`);
  }
}

export function applyHumanMessage(game, text) {
  if (game.phase !== 'day_discussion' || game.awaitingHuman !== 'message' || game.pending.speaker !== game.humanId) throw new Error('Not waiting for the human message');
  const value = String(text ?? '').trim();
  if (!value) throw new Error('Message cannot be empty');
  if ([...value].length > 280) throw new Error('Message must be 280 characters or fewer');
  appendTranscript(game, { speaker: game.humanId, type: 'human_message', text: value });
  recordEvent(game, { type: 'human_message', speaker: game.humanId, text: value });
  game.awaitingHuman = null;
  game.pending.speaker = null;
}

export function applyHumanVote(game, target) {
  if (game.phase !== 'voting' || game.awaitingHuman !== 'vote' || game.pending.voter !== game.humanId) throw new Error('Not waiting for the human vote');
  if (!legalTargets(game, game.humanId, 'vote').includes(target)) throw new Error('Illegal vote target');
  game.pending.votes ||= {};
  game.pending.votes[game.humanId] = target;
  game.awaitingHuman = null;
  game.pending.voter = null;
  recordEvent(game, { type: 'human_vote', voter: game.humanId, target });
}

export function renderRoleClaim(role) {
  return ROLE_LABELS[role] || role;
}

export function checkWin(game) {
  const wolves = game.alive.filter(id => roleOf(game, id) === 'werewolf').length;
  const good = game.alive.length - wolves;
  if (wolves === 0) game.winner = 'good';
  else if (game.ruleset === 'standard' ? wolves >= good : wolves > good) game.winner = 'werewolf';
  else game.winner = null;
  if (game.winner) game.phase = 'finished';
  return game.winner;
}

export function resolveNight(game, { wolfVotes = {}, consensusTarget: requestedTarget = null, seerChoice = null, witchSave = false, witchPoison = null } = {}) {
  const wolves = PLAYER_IDS.filter(id => isAlive(game, id) && roleOf(game, id) === 'werewolf');
  const legalWolfVotes = Object.fromEntries(wolves.map(id => [id, legalTargets(game, id, 'kill').includes(wolfVotes[id]) ? wolfVotes[id] : null]));
  const choices = Object.values(legalWolfVotes).filter(Boolean);
  let consensusTarget = requestedTarget && choices.includes(requestedTarget) ? requestedTarget : null;
  if (!consensusTarget && choices.length) {
    const unique = [...new Set(choices)];
    consensusTarget = unique.length === 1 ? unique[0] : seededPick(game, unique);
  }
  game.night = { ...(game.night || {}), wolfVotes: legalWolfVotes, consensusTarget, seerChoice };
  const seerResult = seerChoice && isAlive(game, seerChoice.seer) && legalTargets(game, seerChoice.seer, 'inspect').includes(seerChoice.target)
    ? { round: game.round, target: seerChoice.target, result: factionOf(roleOf(game, seerChoice.target)) === 'werewolf' ? 'werewolf' : 'not_werewolf' }
    : null;
  const witchId = PLAYER_IDS.find(id => isAlive(game, id) && roleOf(game, id) === 'witch');
  const canSave = witchId && !game.usedAbilities[witchId].save;
  const canPoison = witchId && !game.usedAbilities[witchId].poison;
  const saved = Boolean(witchSave && canSave && consensusTarget);
  const poisonTarget = canPoison && legalTargets(game, witchId, 'poison').includes(witchPoison) && witchPoison !== (saved ? consensusTarget : null) ? witchPoison : null;
  if (witchId && saved) game.usedAbilities[witchId].save = true;
  if (witchId && poisonTarget) game.usedAbilities[witchId].poison = true;
  const dead = [...new Set([...(consensusTarget && !saved ? [consensusTarget] : []), ...(poisonTarget ? [poisonTarget] : [])])];
  for (const id of dead) game.alive = game.alive.filter(playerId => playerId !== id);
  if (seerResult) game.nightKnowledge[seerChoice.seer].push(seerResult);
  const result = { round: game.round, dead: PLAYER_IDS.filter(id => dead.includes(id)) };
  game.nightResults.push(result);
  game.lastOutcome = { type: 'night', round: game.round, dead: result.dead };
  if (!result.dead.length) {
    appendTranscript(game, { speaker: 'system', type: 'night_result', text: '天亮了，昨夜平安无事。' });
  } else if (result.dead.includes(game.humanId)) {
    const others = result.dead.filter(id => id !== game.humanId).map(id => PLAYER_NAMES[id]).join('、');
    appendTranscript(game, { speaker: 'system', type: 'night_result', target: game.humanId, text: `天亮了，你在昨夜被袭击，已出局。${others ? ` ${others} 也在昨夜死亡。` : ''} 你将以观战身份继续查看本局。` });
  } else {
    appendTranscript(game, { speaker: 'system', type: 'night_result', target: result.dead[0], text: `天亮了，${result.dead.map(id => PLAYER_NAMES[id]).join('、')} 在昨夜死亡。` });
  }
  recordEvent(game, { type: 'night_resolved', round: game.round, wolfVotes: legalWolfVotes, consensusTarget, saved, poisonTarget, seerChoice, seerResult, dead: result.dead });
  game.night = null;
  if (!checkWin(game)) {
    game.phase = 'day_discussion';
    game.pending = { speakerIndex: 0, speaker: null, voterIndex: 0, voter: null };
    appendTranscript(game, { speaker: 'system', type: 'round_start', round: game.round, text: `第 ${game.round} 天开始 · 白天讨论` });
    if (result.dead.includes(game.humanId)) game.awaitingHuman = 'spectate';
  }
  return result;
}

export function resolveVotes(game, votes) {
  const legalVotes = {};
  for (const voter of game.alive) {
    if (legalTargets(game, voter, 'vote').includes(votes[voter])) legalVotes[voter] = votes[voter];
  }
  const tally = {};
  for (const target of Object.values(legalVotes)) tally[target] = (tally[target] || 0) + 1;
  const highest = Math.max(0, ...Object.values(tally));
  const leaders = Object.keys(tally).filter(target => tally[target] === highest);
  const exiled = leaders.length === 1 ? leaders[0] : null;
  if (exiled) game.alive = game.alive.filter(id => id !== exiled);
  const result = { round: game.round, votes: legalVotes, tally, exiled, tied: leaders.length > 1 ? leaders : [] };
  game.voteHistory.push(result);
  game.lastOutcome = { type: 'vote', round: game.round, exiled, tied: result.tied };
  if (exiled) {
    const role = roleOf(game, exiled);
    appendTranscript(game, { speaker: 'system', type: 'exile', target: exiled, role, text: `${PLAYER_NAMES[exiled]} 被放逐，身份公开为 ${ROLE_LABELS[role]}。` });
  } else {
    appendTranscript(game, { speaker: 'system', type: 'tie', text: '本轮投票平票，没有人被放逐。' });
  }
  recordEvent(game, { type: 'vote_resolved', ...result });
  if (!checkWin(game)) {
    game.round += 1;
    game.phase = 'night';
    game.pending = { speakerIndex: 0, speaker: null, voterIndex: 0, voter: null };
  }
  return result;
}

export function debugSnapshot(game) {
  return {
    publicState: buildPublicState(game),
    roles: Object.fromEntries(PLAYER_IDS.map(id => [id, roleOf(game, id)])),
    privateStates: Object.fromEntries(PLAYER_IDS.map(id => [id, buildPrivateState(game, id)])),
    trace: game.trace
  };
}
