"""Deterministic Blackjack (21点) dynamics and per-action decision questions (stdlib).

NanoJev-style engine: complete JSON state, SplitMix64 shoe, rendered requests that omit
hidden information (the shoe order and the dealer's hole card) while publishing derived
facts the judge may use (hand values, bust probability from the shoe composition).

Rules: single deck reshuffled below 15 cards, blackjack pays 3:2, dealer stands on all
17s, double allowed on the first action only, no splits.  Per-action gold is the
table's basic strategy (hard/soft totals, double vs dealer upcard) — a fixed, published
policy reference, labelled as a policy.
"""
import copy
import hashlib
import json

RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
SUITS = ['♠', '♥', '♣', '♦']
ACTIONS = ('hit', 'stand', 'double')
MASK64 = (1 << 64) - 1
START_BANK = 100
BET = 10
RESHUFFLE_BELOW = 15


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _random64(rng_state):
    rng_state = (rng_state + 0x9E3779B97F4A7C15) & MASK64
    value = rng_state
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return rng_state, value ^ (value >> 31)


def _shuffle(items, rng_state):
    items = list(items)
    for index in range(len(items) - 1, 0, -1):
        rng_state, value = _random64(rng_state)
        pick = value % (index + 1)
        items[index], items[pick] = items[pick], items[index]
    return items


def card_name(card: int) -> str:
    return RANKS[card % 13] + SUITS[card // 13]


def _card_value(card: int) -> int:
    rank = card % 13
    return 11 if rank == 0 else min(rank, 9) + 1


def hand_value(cards):
    total = sum(_card_value(c) for c in cards)
    aces = sum(1 for c in cards if c % 13 == 0)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    soft = any(c % 13 == 0 for c in cards) and total <= 21 and any(
        total - v + 11 <= 21 for v in [sum(_card_value(c) for c in cards if not (c % 13 == 0))])
    return total, bool(soft and aces and sum(_card_value(c) for c in cards) != total)


def _new_shoe(rng_state):
    shoe = _shuffle(list(range(52)), rng_state)
    return shoe


def make_blackjack(seed: int):
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    shoe = _new_shoe((seed * 2 + 3) & MASK64)
    state = {
        'game': 'blackjack', 'seed': seed, 'shoe': shoe, 'shoe_index': 0,
        'player': [], 'dealer': [], 'phase': 'dealing', 'done': False,
        'outcome': None, 'bank': START_BANK, 'bet': BET, 'doubled': False,
        'round': 0, 'history': [], 'natural': False, 'dealer_natural': False,
        'last_delta': 0, 'reshuffled': False,
    }
    state = _deal_round(state)
    while state['phase'] == 'done_round' and not state['done']:
        state = _deal_round(state)
    return state


def _draw(state):
    if state['shoe_index'] >= len(state['shoe']) - RESHUFFLE_BELOW:
        state['shoe'] = _new_shoe((state['seed'] * 7919 + state['round'] * 31) & MASK64)
        state['shoe_index'] = 0
        state['reshuffled'] = True
    card = state['shoe'][state['shoe_index']]
    state['shoe_index'] += 1
    return card


def _deal_round(state):
    state = copy.deepcopy(state)
    state['round'] += 1
    state['player'], state['dealer'] = [], []
    state['doubled'] = False
    state['natural'] = False
    state['outcome'] = None
    state['phase'] = 'player'
    for _ in range(2):
        state['player'].append(_draw(state))
        state['dealer'].append(_draw(state))
    player_total, _ = hand_value(state['player'])
    dealer_total, _ = hand_value(state['dealer'])
    if player_total == 21:
        state['natural'] = True
        state['phase'] = 'settle'
        state = _settle(state)
    elif dealer_total == 21:
        state['phase'] = 'settle'
        state['dealer_natural'] = True
        state = _settle(state)
    else:
        state['dealer_natural'] = False
    return state


def _settle(state):
    state = copy.deepcopy(state)
    player_total, _ = hand_value(state['player'])
    dealer_total, _ = hand_value(state['dealer'])
    bet = state['bet'] * (2 if state['doubled'] else 1)
    if state['natural']:
        outcome, delta = 'player_blackjack', int(bet * 1.5)
    elif player_total > 21:
        outcome, delta = 'bust', -bet
    elif dealer_total > 21:
        outcome, delta = 'dealer_bust', bet
    elif player_total > dealer_total:
        outcome, delta = 'win', bet
    elif player_total < dealer_total:
        outcome, delta = 'lose', -bet
    else:
        outcome, delta = 'push', 0
    state['outcome'] = outcome
    state['bank'] += delta
    state['last_delta'] = delta
    state['history'].append({'round': state['round'], 'outcome': outcome,
                             'delta': delta, 'player': sorted(state['player']),
                             'dealer': sorted(state['dealer'])})
    state['phase'] = 'done_round'
    if state['bank'] < BET:
        state['done'] = True
        state['outcome'] = 'bankrupt'
    return state


def _dealer_play(state):
    state = copy.deepcopy(state)
    while True:
        total, _ = hand_value(state['dealer'])
        if total >= 17:
            break
        state['dealer'].append(_draw(state))
    return state


def legal_actions(state):
    if state['phase'] != 'player':
        return []
    actions = ['hit', 'stand']
    if len(state['player']) == 2 and state['bank'] >= state['bet'] * 2:
        actions.insert(1, 'double')
    return actions


def bust_probability(state):
    """P(next card busts the player), computed from the published shoe composition."""
    total, _ = hand_value(state['player'])
    remaining = state['shoe'][state['shoe_index']:len(state['shoe']) - 1]
    if not remaining:
        return 0.0
    bust = sum(1 for c in remaining if total + _card_value(c) > 21)
    return round(bust / len(remaining), 3)


def basic_strategy(state) -> str:
    """The published reference policy (hard/soft totals, double on first two cards)."""
    total, soft = hand_value(state['player'])
    upcard = min(_card_value(state['dealer'][1]), 11) if state['dealer'][1] % 13 == 0 else \
        _card_value(state['dealer'][1])
    if _card_value(state['dealer'][1]) == 11:
        upcard = 11
    can_double = len(state['player']) == 2 and state['bank'] >= state['bet'] * 2
    if soft:
        if total >= 19:
            return 'stand'
        if total == 18:
            if 3 <= upcard <= 6 and can_double:
                return 'double'
            return 'stand' if upcard >= 2 and upcard <= 8 else 'hit'
        if total == 17 and 3 <= upcard <= 6 and can_double:
            return 'double'
        if total in (15, 16) and 4 <= upcard <= 6 and can_double:
            return 'double'
        if total in (13, 14) and 5 <= upcard <= 6 and can_double:
            return 'double'
        return 'hit'
    if total >= 17:
        return 'stand'
    if total >= 13:
        return 'stand' if upcard <= 6 else 'hit'
    if total == 12:
        return 'stand' if 4 <= upcard <= 6 else 'hit'
    if total == 11:
        return 'double' if (upcard <= 10 and can_double) else 'hit'
    if total == 10:
        return 'double' if (upcard <= 9 and can_double) else 'hit'
    if total == 9:
        return 'double' if (3 <= upcard <= 6 and can_double) else 'hit'
    return 'hit'


def step(state, action):
    if state['done'] or state['phase'] != 'player':
        raise ValueError('No player action available now')
    if action not in legal_actions(state):
        raise ValueError(f'Illegal action {action!r}')
    state = copy.deepcopy(state)
    if action == 'hit':
        state['player'].append(_draw(state))
        total, _ = hand_value(state['player'])
        if total > 21:
            state['phase'] = 'settle'
            state = _settle(state)
    elif action == 'double':
        state['doubled'] = True
        state['player'].append(_draw(state))
        total, _ = hand_value(state['player'])
        state['phase'] = 'settle'
        if total > 21:
            state = _settle(state)
        else:
            state = _dealer_play(state)
            state = _settle(state)
    else:  # stand
        state['phase'] = 'settle'
        state = _dealer_play(state)
        state = _settle(state)
    # A freshly dealt round can itself end immediately (a natural), so keep dealing
    # until a round is actually waiting on a player action or the bank is gone.
    while state['phase'] == 'done_round' and not state['done']:
        state = _deal_round(state)
    return state


def render_request(state):
    """Player-visible observations: both player cards, dealer upcard, shoe composition.
    Omits the shoe order and the dealer's hole card."""
    total, soft = hand_value(state['player'])
    upcard = state['dealer'][1]
    up_val = 11 if upcard % 13 == 0 else _card_value(upcard)
    remaining = state['shoe'][state['shoe_index']:len(state['shoe']) - 1]
    bust_p = bust_probability(state)
    hand_text = ' '.join(card_name(c) for c in state['player'])
    composition = {}
    for c in remaining:
        composition[RANKS[c % 13]] = composition.get(RANKS[c % 13], 0) + 1
    text = (f"Blackjack round {state['round']}. Your hand: {hand_text} = {total}"
            f"{' (soft)' if soft else ''}. Dealer shows {card_name(upcard)} (value {up_val}). "
            f"Shoe composition remaining: {json.dumps(composition, sort_keys=True)}. "
            f"Probability the next card busts you: {bust_p:.1%}. "
            "House rules: dealer stands on all 17s, blackjack pays 3:2, double on the first "
            "action only. Follow basic strategy: stand on hard 17+, stand on 13-16 vs a "
            "dealer 2-6, hit soft 17 or below, double 11 vs any upcard 10 or less.")
    criteria = {
        'hit': f'Take one card. Bust probability {bust_p:.1%}; safe if the hand is soft.',
        'stand': f'Keep {total} and let the dealer play. Dealer must draw to all 17s.',
        'double': 'Double the bet, take exactly one more card, then stand.'
                  + ('' if 'double' in legal_actions(state) else ' (Not available now.)'),
    }
    questions = {'action': {'type': 'choice', 'instructions':
        'Choose the action with the best expected value against the dealer upcard, using the '
        'published bust probability and hand value. Basic strategy: stand on hard 17+; stand on '
        'hard 13-16 only vs dealer 2-6; always hit soft 17 or below; double hard 11 vs upcard '
        '2-10, hard 10 vs 2-9, hard 9 vs 3-6 when allowed.',
        'criteria': criteria}}
    return {'state': text, 'questions': questions,
            'legal': legal_actions(state), 'hand_value': total, 'soft': soft,
            'bust_probability': bust_p, 'upcard_value': up_val}


def make_record(state, split):
    if split not in ('train', 'dev', 'calibration', 'test', 'ood'):
        raise ValueError('Unknown split')
    public = render_request(state)
    gold_action = basic_strategy(state)
    gold = {'action': gold_action}
    probabilities = {'action': {a: float(a == gold_action) for a in ACTIONS}}
    identity = 'blackjack:' + _hash({'player': state['player'], 'up': state['dealer'][1],
                                     'round': state['round']})[:24]
    return {'id': identity, 'state_id': identity, 'family_id': 'blackjack_action_v1',
            'split': split, **public, 'gold': gold, 'gold_probs': probabilities,
            'metadata': {'source': 'self_authored_programmatic', 'license': 'CC0-1.0',
                         'target_semantics': ("'action' gold is the published basic-strategy "
                                              "policy, not a computed optimum.")}}
