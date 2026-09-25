// Explicit live check: node --env-file=.env verify-live-speech.mjs
import assert from 'node:assert/strict';
import { createGame, appendTranscript, buildPublicState } from './game-engine.mjs';
import { decideForAgent, speechFromDecision } from './jev-agent.mjs';

const game = createGame({ seed: 20260921, mode: 'auto', fixedRoles: {
  human: 'villager', jev_1: 'werewolf', jev_2: 'werewolf', jev_3: 'seer', jev_4: 'witch', jev_5: 'villager'
} });
game.phase = 'day_discussion';
game.nightKnowledge.jev_3.push({ round: 1, target: 'human', result: 'not_werewolf' });
appendTranscript(game, { speaker: 'system', type: 'night_result', text: '天亮了，昨夜平安无事。' });
appendTranscript(game, { speaker: 'human', type: 'human_message', text: '我是好人啊，先关注公开投票和查验信息。' });
const speeches = [];
for (const id of ['jev_1', 'jev_2', 'jev_3', 'jev_4', 'jev_5']) {
  const decision = await decideForAgent(game, id, 'day_speech');
  const speech = speechFromDecision(game, id, decision);
  assert.equal(speech?.source, 'deepseek', decision.fallbackReason);
  assert.equal(game.trace.decisions.at(-1).rawResponse, null, 'No Jev request during day');
  appendTranscript(game, { speaker: id, type: 'jev_message', ...speech });
  speeches.push(speech.text);
  console.log(JSON.stringify({ speaker: id, source: speech.source, text: speech.text }));
}
assert.equal(new Set(speeches).size, 5);
game.phase = 'voting';
game.pending.voters = [...game.alive];
game.pending.votes = {};
const vote = await decideForAgent(game, 'jev_5', 'vote');
assert.equal(vote.mode, 'jev');
assert.equal(game.trace.decisions.at(-1).cognitionMode, 'deepseek');
assert.equal(buildPublicState(game).cognitionMemory, undefined);
console.log('PASS: five DS public speeches, zero daytime Jev calls, DS analysis → Jev vote.');
