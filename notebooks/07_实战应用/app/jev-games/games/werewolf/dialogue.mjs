import { PLAYER_NAMES, ROLE_LABELS } from './game-engine.mjs';

const templates = {
  accuse_player: {
    vote_inconsistency: target => `我怀疑 ${PLAYER_NAMES[target] || target}，因为它的投票和之前的发言不一致。`,
    claim_conflict: target => `我认为 ${PLAYER_NAMES[target] || target} 的身份声明和已知信息冲突。`,
    defensive_behavior: target => `我注意到 ${PLAYER_NAMES[target] || target} 的辩护反应过强，暂时把它列为嫌疑对象。`,
    low_information: target => `我暂时怀疑 ${PLAYER_NAMES[target] || target}，但目前置信度不高。`,
    night_pattern: target => `我认为 ${PLAYER_NAMES[target] || target} 的行为和夜间结果放在一起看并不自然。`
  },
  defend_self: {
    low_information: () => '我目前没有足够信息支持放逐自己，请结合公开投票和发言判断。',
    defensive_behavior: () => '我愿意解释自己的选择，但希望大家把注意力放在可核验的投票事实上。'
  },
  support_player: {
    vote_inconsistency: target => `我暂时支持 ${PLAYER_NAMES[target] || target}，因为它的投票和发言能够相互对应。`,
    role_result: target => `我支持 ${PLAYER_NAMES[target] || target}，这和我掌握的查验结果一致。`,
    low_information: target => `我暂时支持 ${PLAYER_NAMES[target] || target}，但保留意见。`
  },
  claim_role: {
    role_result: role => `我声明自己是${ROLE_LABELS[role] || role}，可以提供与身份相关的公开信息。`,
    low_information: role => `我声明自己是${ROLE_LABELS[role] || role}，但现在不公开更多细节。`
  },
  question_claim: {
    low_information: target => `我想请 ${PLAYER_NAMES[target] || target} 进一步解释自己的判断，目前的信息还不足以下结论。`,
    claim_conflict: target => `我想质疑 ${PLAYER_NAMES[target] || target} 的身份声明，因为它和目前的公开信息冲突。`
  },
  share_result: {
    low_information: () => '我目前没有可以公开的查验结果，先听其他人的判断。',
    role_result: (target, result, role) => `${role === 'seer' ? '我声明自己是预言家。' : ''}我分享查验结果：${PLAYER_NAMES[target] || target} 被判断为${result === 'werewolf' ? '狼人阵营' : '非狼人阵营'}。`
  },
  change_vote: {
    low_information: () => '我还没有形成明确的投票倾向，继续听大家的理由。',
    vote_inconsistency: target => `我改投 ${PLAYER_NAMES[target] || target}，因为新的投票信息改变了我的判断。`
  },
  remain_silent: {
    low_information: () => '我暂时保留意见，继续观察公开信息。'
  }
};

export function renderSpeech(decision, context = {}) {
  const type = templates[decision?.intent] ? decision.intent : 'remain_silent';
  if (type === 'remain_silent' || decision?.shouldSpeak === false) return null;
  const evidence = decision?.evidence && templates[type]?.[decision.evidence] ? decision.evidence : Object.keys(templates[type] || {})[0];
  const target = decision?.target;
  let text;
  if (type === 'claim_role') text = templates[type][evidence](decision.claimRole || context.role || 'villager');
  else if (type === 'share_result') text = templates[type][evidence](target, decision.result || context.result || 'not_werewolf', context.role);
  else if (templates[type]?.[evidence]) text = templates[type][evidence](target);
  if (!text) text = '我暂时保留意见，继续观察公开信息。';
  return { text, intent: type, target: target || null, evidence: evidence || 'low_information', claim: decision.claim || null };
}
