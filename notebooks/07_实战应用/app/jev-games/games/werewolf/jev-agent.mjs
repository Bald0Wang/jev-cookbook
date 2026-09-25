import { buildAgentState, buildPublicState, buildPrivateState, legalTargets, PLAYER_IDS, POLICY_PROFILES, recordDecision, recordEvent, roleOf, isAlive, seededPick, ROLE_LABELS } from './game-engine.mjs';
import { renderSpeech } from './dialogue.mjs';
import { summarizeForAgent, writePublicSpeech } from './cognition.mjs';

const API_URL = 'https://api.typesafe.ai/v1/systemone';
const REQUEST_TIMEOUT_MS = 4500;

export function hasApiKey() {
  const value = process.env.TYPESAFE_API_KEY?.trim();
  return Boolean(value && !/(your|replace|api key|placeholder)/i.test(value));
}

function suspicionMap(game, agentId) {
  const scores = Object.fromEntries(PLAYER_IDS.map(id => [id, 1]));
  const role = roleOf(game, agentId);
  for (const id of PLAYER_IDS) {
    if (!isAlive(game, id) || id === agentId) scores[id] = -Infinity;
    if (role === 'werewolf' && roleOf(game, id) === 'werewolf') scores[id] = -Infinity;
  }
  for (const result of game.nightKnowledge[agentId]) if (result.result === 'werewolf') scores[result.target] = 99;
  for (const claim of Object.entries(game.publicClaims)) {
    if (claim[1] === 'seer' && role !== 'seer') scores[claim[0]] += 2;
  }
  for (const transcript of game.publicTranscript) {
    if (transcript.intent === 'accuse' && transcript.target && scores[transcript.target] !== -Infinity) scores[transcript.target] += 1;
    if (transcript.type === 'exile' && transcript.target && scores[transcript.target] !== -Infinity) scores[transcript.target] -= 1;
  }
  return scores;
}

function sortedTargets(game, agentId, action) {
  const targets = legalTargets(game, agentId, action);
  const scores = suspicionMap(game, agentId);
  return [...targets].sort((a, b) => (scores[b] - scores[a]) || PLAYER_IDS.indexOf(a) - PLAYER_IDS.indexOf(b));
}

function suspicionProbabilities(game, agentId) {
  const scores = suspicionMap(game, agentId);
  const targets = legalTargets(game, agentId, 'vote');
  if (!targets.length) return {};
  const highest = Math.max(...targets.map(target => scores[target]));
  const weights = targets.map(target => Math.exp(scores[target] - highest));
  const total = weights.reduce((sum, value) => sum + value, 0) || 1;
  return Object.fromEntries(targets.map((target, index) => [target, Number((weights[index] / total).toFixed(4))]));
}

export function offlineDecision(game, agentId, phase) {
  const role = roleOf(game, agentId);
  const targets = sortedTargets(game, agentId, phase === 'night_wolf' ? 'kill' : phase === 'night_seer' ? 'inspect' : phase === 'night_witch' ? 'poison' : 'vote');
  if (phase === 'night_wolf') return { target: targets[0] || null, confidence: 0.55, mode: 'scripted' };
  if (phase === 'night_seer') {
    const unknown = legalTargets(game, agentId, 'inspect').filter(target => !game.nightKnowledge[agentId].some(item => item.target === target));
    return { target: unknown[0] || targets[0] || null, confidence: 0.72, mode: 'scripted' };
  }
  if (phase === 'night_witch') {
    const candidate = game.night?.consensusTarget || null;
    const shouldSave = !game.usedAbilities[agentId].save && Boolean(candidate) && game.round === 1;
    const poison = !shouldSave && !game.usedAbilities[agentId].poison && targets.find(target => suspicionMap(game, agentId)[target] >= 5);
    return { save: shouldSave, poisonTarget: poison || null, confidence: shouldSave || poison ? 0.61 : 0.74, mode: 'scripted' };
  }
  if (phase === 'day_speech') {
    const target = targets[0] || null;
    const knownWolf = game.nightKnowledge[agentId].find(item => item.result === 'werewolf');
    if (role === 'seer' && knownWolf) return { intent: 'share_result', target: knownWolf.target, result: knownWolf.result, claim: 'seer', claimRole: 'seer', evidence: 'role_result', shouldSpeak: true, confidence: 0.92, mode: 'scripted' };
    if (role === 'seer' && game.nightKnowledge[agentId].length && !game.publicClaims[agentId]) return { intent: 'claim_role', target, claim: 'seer', claimRole: 'seer', evidence: 'role_result', shouldSpeak: true, confidence: 0.66, mode: 'scripted' };
    if (role === 'werewolf') return { intent: 'defend_self', target: agentId, evidence: 'defensive_behavior', shouldSpeak: true, confidence: 0.54, mode: 'scripted' };
    return { intent: target ? 'accuse_player' : 'remain_silent', target, evidence: game.voteHistory.length ? 'vote_inconsistency' : 'low_information', shouldSpeak: Boolean(target), confidence: 0.48, mode: 'scripted' };
  }
  if (phase === 'vote') return { target: targets[0] || null, confidence: targets[0] ? 0.57 : 0.2, mode: 'scripted' };
  return {};
}

export function humanFallbackDecision(game, agentId, phase) {
  const started = Date.now();
  const result = offlineDecision(game, agentId, phase);
  recordDecision(game, {
    round: game.round,
    phase,
    agentId,
    role: roleOf(game, agentId),
    choice: result,
    confidence: result.confidence ?? 0,
    latencyMs: Date.now() - started,
    mode: 'human_auto_fallback',
    fallbackReason: 'human_night_action_is_automatic_in_mvp'
  });
  return { ...result, mode: 'human_auto_fallback', fallbackReason: 'human_night_action_is_automatic_in_mvp' };
}

function questionFor(phase, game, agentId) {
  const legal = phase === 'night_wolf' ? legalTargets(game, agentId, 'kill') : phase === 'night_seer' ? legalTargets(game, agentId, 'inspect') : phase === 'vote' ? legalTargets(game, agentId, 'vote') : legalTargets(game, agentId, 'poison');
  const criteria = (choices, description) => Object.fromEntries(choices.map(choice => [String(choice), `${description} Option: ${String(choice)}.`]));
  const confidence = { type: 'score', instructions: 'How confident is this decision?', criteria: ['Very low confidence.', 'Low confidence.', 'Moderate confidence.', 'High confidence.', 'Very high confidence.'] };
  if (phase === 'night_wolf') return { target: { type: 'choice', instructions: 'Choose one legal non-wolf target to kill.', criteria: criteria(legal, 'This target is a legal night action') }, confidence };
  if (phase === 'night_seer') return { target: { type: 'choice', instructions: 'Choose one living player to inspect.', criteria: criteria(legal, 'This target is a legal inspection') }, confidence };
  if (phase === 'night_witch') return { save: { type: 'noul', instructions: 'Should the witch use the save potion on the night death candidate?', criteria: { true: 'Saving prevents the current legal night death.', false: 'Keep the save potion for a later night.' } }, poisonTarget: { type: 'choice', instructions: 'Choose a legal poison target or null.', criteria: criteria([null, ...legal], 'This is a legal poison choice') }, confidence };
  if (phase === 'day_speech') {
    const questions = { speechIntent: { type: 'choice', instructions: 'Choose one speech intent.', criteria: criteria(['accuse_player', 'defend_self', 'support_player', 'claim_role', 'question_claim', 'share_result', 'change_vote', 'remain_silent'], 'This is a supported speech intent') }, speechTarget: { type: 'choice', instructions: 'Choose a legal speech target.', criteria: criteria(legalTargets(game, agentId, 'vote'), 'This is a legal speech target') }, claim: { type: 'choice', instructions: 'Choose a public role claim or none.', criteria: criteria(['none', 'villager', 'seer', 'witch', 'werewolf'], 'This is a supported claim') }, evidence: { type: 'choice', instructions: 'Choose one evidence code grounded in the visible state.', criteria: criteria(['vote_inconsistency', 'claim_conflict', 'night_pattern', 'defensive_behavior', 'low_information', 'role_result'], 'This is a supported evidence code') }, should_speak: { type: 'noul', instructions: 'Should this agent speak now?', criteria: { true: 'A concise template statement is useful now.', false: 'There is not enough useful information to speak.' } }, confidence };
    const suspicionCriteria = ['No suspicion.', 'Very low suspicion.', 'Low suspicion.', 'Somewhat low suspicion.', 'Neutral suspicion.', 'Somewhat high suspicion.', 'High suspicion.', 'Very high suspicion.', 'Near-certain suspicion.', 'Certain suspicion.'];
    for (const target of legalTargets(game, agentId, 'vote')) questions[`suspicion_${target}`] = { type: 'score', instructions: `Score the suspicion that ${target} is a werewolf from 0 to 10.`, criteria: suspicionCriteria };
    return questions;
  }
  return { voteTarget: { type: 'choice', instructions: 'Choose exactly one living player to vote for.', criteria: criteria(legalTargets(game, agentId, 'vote'), 'This is a legal vote target') }, confidence };
}

function answerFor(payload, key) {
  const answers = payload?.answers && typeof payload.answers === 'object' ? payload.answers : payload;
  return answers?.[key] ?? payload?.[key];
}

function answerValue(answer, fields = ['choice', 'value', 'score', 'confidence', 'noul']) {
  if (answer === null || answer === undefined || typeof answer !== 'object') return answer;
  for (const field of fields) if (answer[field] !== undefined) return answer[field];
  return undefined;
}

export function parseResponse(phase, payload, game, agentId) {
  const legalVote = legalTargets(game, agentId, 'vote');
  const legalKill = legalTargets(game, agentId, 'kill');
  const legalInspect = legalTargets(game, agentId, 'inspect');
  const legalPoison = legalTargets(game, agentId, 'poison');
  const targetKey = phase === 'vote' ? 'voteTarget' : phase === 'day_speech' ? 'speechTarget' : 'target';
  const rawTarget = answerValue(answerFor(payload, targetKey), ['choice', 'value']);
  const confidence = Number(answerValue(answerFor(payload, 'confidence'), ['confidence', 'score'])) || 0;
  if (phase === 'night_wolf') return legalKill.includes(rawTarget) ? { target: rawTarget, confidence, mode: 'jev' } : null;
  if (phase === 'night_seer') return legalInspect.includes(rawTarget) ? { target: rawTarget, confidence, mode: 'jev' } : null;
  if (phase === 'night_witch') {
    const rawSave = answerValue(answerFor(payload, 'save'), ['noul', 'value']);
    const save = typeof rawSave === 'number' ? rawSave >= 0.5 : Boolean(rawSave);
    const poisonTarget = rawTarget === null || rawTarget === 'null' || legalPoison.includes(rawTarget) ? (rawTarget === 'null' ? null : rawTarget) : null;
    return { save, poisonTarget, confidence, mode: 'jev' };
  }
  if (phase === 'vote') return legalVote.includes(rawTarget) ? { target: rawTarget, confidence, mode: 'jev' } : null;
  const intent = answerValue(answerFor(payload, 'speechIntent'), ['choice', 'value']) || 'remain_silent';
  const evidence = answerValue(answerFor(payload, 'evidence'), ['choice', 'value']) || 'low_information';
  const claim = answerValue(answerFor(payload, 'claim'), ['choice', 'value']) || 'none';
  const rawNoul = answerValue(answerFor(payload, 'should_speak'), ['noul', 'value']);
  const shouldSpeak = typeof rawNoul === 'number' ? rawNoul >= 0.5 : rawNoul !== false;
  return { intent, target: legalVote.includes(rawTarget) ? rawTarget : legalVote[0], evidence, claim, claimRole: claim, shouldSpeak, confidence, mode: 'jev' };
}

async function callJev(payload) {
  if (!hasApiKey()) throw new Error('TYPESAFE_API_KEY is not configured');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(API_URL, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.TYPESAFE_API_KEY}` }, body: JSON.stringify(payload), signal: controller.signal });
    const text = await response.text();
    if (!response.ok) throw new Error(`TypeSafe returned ${response.status}`);
    return { data: JSON.parse(text), raw: text.slice(0, 20000) };
  } finally {
    clearTimeout(timer);
  }
}

export async function decideForAgent(game, agentId, phase) {
  const inputState = buildAgentState(game, agentId);
  const cognition = await summarizeForAgent(game, agentId, phase);
  inputState.cognition = cognition.cognition;
  const fallback = offlineDecision(game, agentId, phase);
  const started = Date.now();
  let result = fallback;
  let rawResponse = null;
  let fallbackReason = null;
  let mode = 'scripted';
  if (game.mode === 'replay') {
    const recorded = (game.replayDecisions || []).slice(game.replayCursor).find(item => item.agentId === agentId && item.phase === phase && item.round === game.round);
    if (recorded) {
      game.replayCursor = (game.replayDecisions || []).indexOf(recorded) + 1;
      result = recorded.choice || fallback;
      mode = 'replay';
    } else {
      fallbackReason = 'replay_decision_missing';
    }
  } else if (phase === 'day_speech') {
    result = cognition.cognition.speechPlan || fallback;
    mode = cognition.mode;
    fallbackReason = cognition.fallbackReason;
    if (cognition.mode === 'deepseek') {
      const publicSpeech = await writePublicSpeech(game, agentId, result);
      result = { ...result, publicSpeech };
      fallbackReason = publicSpeech.fallbackReason;
    }
  } else if (game.mode !== 'offline' && hasApiKey()) {
    try {
      const response = await callJev({ model: 'jev-latest', state: inputState, questions: questionFor(phase, game, agentId) });
      const parsed = parseResponse(phase, response.data, game, agentId);
      if (!parsed) throw new Error('Jev response did not contain a legal choice');
      result = parsed;
      rawResponse = response.raw;
      mode = 'jev';
    } catch (error) {
      fallbackReason = error instanceof Error ? error.message : String(error);
    }
  } else if (game.mode !== 'offline') fallbackReason = 'no_api_key';
  recordDecision(game, {
    round: game.round,
    phase,
    agentId,
    role: roleOf(game, agentId),
    question: phase === 'day_speech' ? { source: 'deepseek_cognition', output: 'speechPlan' } : questionFor(phase, game, agentId),
    choice: result,
    score: result.score ?? result.confidence ?? 0,
    noul: result.noul ?? (result.shouldSpeak === undefined ? null : (result.shouldSpeak ? 1 : 0)),
    probabilities: suspicionProbabilities(game, agentId),
    cognition: cognition.cognition,
    cognitionMode: cognition.mode,
    cognitionLatencyMs: cognition.latencyMs,
    cognitionFallbackReason: cognition.fallbackReason,
    cognitionUsage: cognition.usage,
    confidence: result.confidence ?? 0,
    latencyMs: Date.now() - started,
    mode,
    fallbackReason,
    input: inputState,
    rawResponse,
    cognitionRawResponse: cognition.raw
  });
  return { ...result, mode, fallbackReason };
}

export function speechFromDecision(game, agentId, decision) {
  if (decision.publicSpeech) {
    const { text, intent, target, evidence, claim, source } = decision.publicSpeech;
    if (claim && claim !== 'none') game.publicClaims[agentId] = claim;
    return { text, intent, target, evidence, claim, source };
  }
  const state = buildPrivateState(game, agentId);
  const knownResult = state.nightKnowledge.find(item => item.target === decision.target);
  const safeDecision = { ...decision, shouldSpeak: decision.shouldSpeak !== false, claimRole: decision.claimRole || decision.claim };
  if (state.role === 'seer' && knownResult) {
    safeDecision.intent = 'share_result';
    safeDecision.target = knownResult.target;
    safeDecision.result = knownResult.result;
    safeDecision.claim = 'seer';
    safeDecision.claimRole = 'seer';
    safeDecision.evidence = 'role_result';
    safeDecision.shouldSpeak = true;
    if (decision.intent !== 'share_result' || decision.target !== knownResult.target || decision.claim !== 'seer') {
      recordEvent(game, { type: 'speech_safety_gate', agentId, reason: 'seer_result_must_be_grounded_and_visible', originalDecision: decision, appliedDecision: safeDecision });
    }
  }
  if (safeDecision.evidence === 'vote_inconsistency' && !game.voteHistory.length) safeDecision.evidence = 'low_information';
  if (safeDecision.evidence === 'claim_conflict' && !game.publicClaims[safeDecision.target]) safeDecision.evidence = 'low_information';
  if (safeDecision.evidence === 'role_result' && !knownResult) safeDecision.evidence = 'low_information';
  if (safeDecision.intent === 'share_result') {
    if (!knownResult) safeDecision.intent = 'remain_silent';
    else safeDecision.result = knownResult.result;
  }
  const rendered = renderSpeech(safeDecision, { role: state.role, result: knownResult?.result });
  if (rendered?.claim && rendered.claim !== 'none') game.publicClaims[agentId] = rendered.claim;
  return rendered;
}
