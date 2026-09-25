import test from 'node:test';
import assert from 'node:assert/strict';
import {
  PLAYER_IDS,
  buildPrivateState,
  buildPublicState,
  checkWin,
  createGame,
  resolveNight,
  resolveVotes,
  roleOf
} from './game-engine.mjs';
import { decideForAgent, parseResponse, speechFromDecision } from './jev-agent.mjs';

const fixedRoles = {
  human: 'villager',
  jev_1: 'werewolf',
  jev_2: 'werewolf',
  jev_3: 'seer',
  jev_4: 'witch',
  jev_5: 'villager'
};

test('same seed produces the same valid role assignment', () => {
  const first = createGame({ seed: 20260921 });
  const second = createGame({ seed: 20260921 });
  assert.deepEqual(first.roleByPlayer, second.roleByPlayer);
  assert.deepEqual(Object.values(first.roleByPlayer).sort(), ['seer', 'villager', 'villager', 'werewolf', 'werewolf', 'witch'].sort());
});

test('public state hides roles while private state only exposes the viewer role', () => {
  const game = createGame({ seed: 1, fixedRoles });
  const publicState = buildPublicState(game);
  const privateState = buildPrivateState(game, 'jev_3');
  assert.equal(publicState.roles, undefined);
  assert.equal(publicState.roleByPlayer, undefined);
  assert.equal(privateState.role, 'seer');
  assert.deepEqual(privateState.teammates, []);
  assert.equal(/"role(?:ByPlayer)?"\s*:/.test(JSON.stringify(publicState)), false);
});

test('night rules apply consensus, witch save, seer faction result, and poison legally', () => {
  const game = createGame({ seed: 2, fixedRoles });
  const result = resolveNight(game, {
    wolfVotes: { jev_1: 'human', jev_2: 'human' },
    consensusTarget: 'human',
    seerChoice: { seer: 'jev_3', target: 'jev_1' },
    witchSave: true,
    witchPoison: 'jev_2'
  });
  assert.deepEqual(result.dead, ['jev_2']);
  assert.equal(game.alive.includes('human'), true);
  assert.deepEqual(game.nightKnowledge.jev_3.at(-1), { round: 1, target: 'jev_1', result: 'werewolf' });
  assert.equal(game.usedAbilities.jev_4.save, true);
  assert.equal(game.usedAbilities.jev_4.poison, true);
});

test('tied vote exiles nobody and keeps all surviving targets alive', () => {
  const game = createGame({ seed: 3, fixedRoles });
  game.phase = 'voting';
  const votes = { human: 'jev_1', jev_1: 'human', jev_2: 'jev_3', jev_3: 'jev_1', jev_4: 'jev_3', jev_5: 'human' };
  const result = resolveVotes(game, votes);
  assert.equal(result.exiled, null);
  assert.deepEqual(result.tied.sort(), ['human', 'jev_1', 'jev_3'].sort());
  assert.deepEqual(game.alive, PLAYER_IDS);
  assert.equal(roleOf(game, 'jev_1'), 'werewolf');
});

test('seer private result is surfaced as a grounded public claim', () => {
  const game = createGame({ seed: 4, fixedRoles });
  game.nightKnowledge.jev_3.push({ round: 1, target: 'jev_1', result: 'werewolf' });
  const rendered = speechFromDecision(game, 'jev_3', { intent: 'remain_silent', shouldSpeak: false, target: 'jev_1', evidence: 'low_information' });
  assert.match(rendered.text, /预言家/);
  assert.match(rendered.text, /Jev-1/);
  assert.equal(rendered.claim, 'seer');
  assert.equal(game.publicClaims.jev_3, 'seer');
});

test('Jev answers are parsed by question name without mixing score and choice answers', () => {
  const game = createGame({ seed: 5, fixedRoles });
  const parsed = parseResponse('day_speech', {
    answers: {
      speechIntent: { type: 'choice', choice: 'remain_silent', confidence: 0.81 },
      speechTarget: { type: 'choice', choice: 'jev_1', confidence: 0.72 },
      claim: { type: 'choice', choice: 'none', confidence: 0.9 },
      evidence: { type: 'choice', choice: 'low_information', confidence: 0.8 },
      should_speak: { type: 'noul', noul: 0.2 },
      confidence: { type: 'score', score: 0.4, confidence: 0.77 }
    }
  }, game, 'jev_3');
  assert.equal(parsed.intent, 'remain_silent');
  assert.equal(parsed.target, 'jev_1');
  assert.equal(parsed.shouldSpeak, false);
  assert.equal(parsed.confidence, 0.77);
});

test('demo ruleset does not end at wolf-good parity', () => {
  const game = createGame({ seed: 6, fixedRoles });
  game.alive = ['human', 'jev_1', 'jev_2', 'jev_3'];
  assert.equal(checkWin(game), null);
  game.alive = ['human', 'jev_1', 'jev_2'];
  assert.equal(checkWin(game), 'werewolf');
});

test('night result is announced and a dead human enters spectator mode', () => {
  const game = createGame({ seed: 7, fixedRoles });
  const result = resolveNight(game, { wolfVotes: { jev_1: 'human', jev_2: 'human' }, consensusTarget: 'human' });
  assert.deepEqual(result.dead, ['human']);
  assert.equal(game.awaitingHuman, 'spectate');
  assert.match(game.publicTranscript.find(item => item.type === 'night_result').text, /你在昨夜被袭击，已出局/);
});

test('each living day gets a visible round separator in public chat', () => {
  const game = createGame({ seed: 8, fixedRoles });
  resolveNight(game, { wolfVotes: { jev_1: 'jev_5', jev_2: 'jev_5' }, consensusTarget: 'jev_5' });
  const marker = game.publicTranscript.find(item => item.type === 'round_start');
  assert.equal(marker.round, 1);
  assert.match(marker.text, /第 1 天开始/);
});

test('day speech uses cognition directly instead of a Jev action request', async () => {
  const game = createGame({ seed: 9, fixedRoles, mode: 'offline' });
  game.phase = 'day_discussion';
  const decision = await decideForAgent(game, 'jev_3', 'day_speech');
  assert.equal(decision.mode, 'heuristic');
  assert.equal(game.trace.decisions.at(-1).question.source, 'deepseek_cognition');
  assert.equal(game.trace.decisions.at(-1).cognitionFallbackReason, 'offline_mode');
});
