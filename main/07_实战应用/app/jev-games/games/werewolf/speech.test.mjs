import test from 'node:test';
import assert from 'node:assert/strict';
import { createGame, appendTranscript, buildPublicState } from './game-engine.mjs';
import { decideForAgent, speechFromDecision } from './jev-agent.mjs';
import { renderSpeech } from './dialogue.mjs';

test('DS writes actual public dialogue; voting receives its private analysis; no Jev call for speech', async t => {
  const env = { ...process.env };
  t.after(() => { process.env = env; });
  process.env.DEEPSEEK_API_KEY = 'test-ds';
  process.env.TYPESAFE_API_KEY = 'test-jev';
  const game = createGame({ seed: 2, mode: 'auto' });
  const calls = [];
  const prose = '真人玩家说要看投票变化，但目前还没投过票。我想先听大家各自怀疑谁，以及依据是什么，再决定站哪边。';
  t.mock.method(globalThis, 'fetch', async (url, request) => {
    const body = JSON.parse(request.body);
    calls.push({ url, body });
    if (String(url).includes('typesafe')) return Response.json({ answers: { voteTarget: { choice: 'human' }, confidence: { confidence: 0.7 } } });
    if (body.temperature === 0.8) return Response.json({ choices: [{ message: { content: JSON.stringify({ text: prose }) } }] });
    return Response.json({ choices: [{ message: { content: JSON.stringify({ summary: 'PRIVATE_ANALYSIS', hypotheses: [], actionAdvice: 'Compare claims', memorySummary: [], speechPlan: { intent: 'question_claim', target: 'human', claim: 'none', evidence: 'claim_conflict', shouldSpeak: true } }) } }] });
  });
  appendTranscript(game, { speaker: 'human', text: '我想看投票变化。' });
  const decision = await decideForAgent(game, 'jev_2', 'day_speech');
  const speech = speechFromDecision(game, 'jev_2', decision);
  assert.equal(speech.text, prose);
  assert.equal(speech.source, 'deepseek');
  assert.equal(calls.length, 2);
  const writer = JSON.parse(calls[1].body.messages[1].content);
  assert.equal(writer.privateState, undefined);
  assert.equal(JSON.stringify(writer).includes('PRIVATE_ANALYSIS'), false);
  assert.equal(writer.publicPlan.evidence, 'low_information');
  appendTranscript(game, { speaker: 'jev_2', ...speech });
  assert.equal(JSON.stringify(buildPublicState(game)).includes('PRIVATE_ANALYSIS'), false);
  await decideForAgent(game, 'jev_2', 'vote');
  assert.equal(calls.length, 4);
  assert.equal(calls[3].body.state.cognition.summary, 'PRIVATE_ANALYSIS');
  assert.equal(JSON.parse(calls[2].body.messages[1].content.split('Current player state:\n')[1]).previousAnalysis.summary, 'PRIVATE_ANALYSIS');
});

test('template fallback cannot turn missing evidence back into a false conflict', () => {
  const speech = renderSpeech({ intent: 'question_claim', target: 'human', evidence: 'low_information' });
  assert.doesNotMatch(speech.text, /冲突/);
});

test('public speech timeout or malformed text uses explicitly labelled fallback', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ choices: [{ message: { content: '{}' } }] }));
  const { writePublicSpeech } = await import('./cognition.mjs');
  const speech = await writePublicSpeech(createGame({ seed: 2 }), 'jev_1', { intent: 'question_claim', target: 'human', evidence: 'claim_conflict', claim: 'none' });
  assert.equal(speech.source, 'template_fallback');
  assert.equal(speech.fallbackReason, 'Invalid public speech');
  assert.doesNotMatch(speech.text, /冲突/);
});
