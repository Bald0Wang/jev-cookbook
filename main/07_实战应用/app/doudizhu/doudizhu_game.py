"""Deterministic Dou Dizhu (斗地主) dynamics and per-turn decision questions (stdlib).

Same contract as ``sudoku_game.py`` / NanoJev's ``snake_game.py``: a complete
JSON-round-trippable state, ``make`` / ``validate_state`` / ``step`` /
``render_request`` / ``make_record``, SplitMix64 determinism, and rendered requests
that omit hidden information (the other players' hands) exactly as the snake omits RNG.

Supported card types: single, pair, trio, trio+single, trio+pair, straight (>=5),
pair straight (>=3 pairs), pure plane (>=2 consecutive trios), bomb, rocket.
Beats: same type & length & higher rank; bomb beats all non-rocket; rocket beats all.

Gold labels: per-move ``beats_trick`` is deterministic truth; the ``move`` gold is a
reference heuristic policy (smallest winning play, peasant cooperation, bomb timing),
labelled as such — it is a policy, not an optimum.
"""
import copy
import hashlib
import json

RANK_NAMES = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2', '小王', '大王']
SUITS = ['♠', '♥', '♣', '♦']
SPLITS = {'train', 'dev', 'calibration', 'test', 'ood'}
MASK64 = (1 << 64) - 1
SEATS = ('landlord', 'peasant_a', 'peasant_b')


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
    if card >= 52:
        return RANK_NAMES[13 + card - 52]
    return RANK_NAMES[card // 4] + SUITS[card % 4]


def rank_of(card: int) -> int:
    return card // 4 if card < 52 else 13 + (card - 52)


def _counts(hand):
    by_rank = {}
    for card in hand:
        by_rank.setdefault(rank_of(card), []).append(card)
    return by_rank


def _sequence_moves(by_rank, *, each, min_len, mtype, max_rank=11):
    """Straights (each=1), pair straights (each=2), pure planes (each=3)."""
    moves = []
    ranks = sorted(r for r, cards in by_rank.items() if r <= max_rank and len(cards) >= each)
    run = []
    for r in ranks:
        if run and r == run[-1] + 1:
            run.append(r)
        else:
            run = [r]
        for length in range(min_len, len(run) + 1):
            window = run[-length:]
            cards = []
            for rank in window:
                pool = sorted(by_rank[rank])[:each]
                cards.extend(pool)
            moves.append({'type': mtype, 'cards': sorted(cards), 'rank': window[-1], 'length': length})
    return moves


def gen_moves(hand, trick=None):
    """Every legal move from ``hand``; if ``trick`` is set, only moves that beat it plus pass."""
    by_rank = _counts(hand)
    moves = [{'type': 'pass', 'cards': [], 'rank': -1, 'length': 0}]
    for rank, cards in sorted(by_rank.items()):
        moves.append({'type': 'single', 'cards': [cards[0]], 'rank': rank, 'length': 1})
        if len(cards) >= 2 and rank <= 12:
            moves.append({'type': 'pair', 'cards': sorted(cards[:2]), 'rank': rank, 'length': 1})
        if len(cards) >= 3 and rank <= 12:
            moves.append({'type': 'trio', 'cards': sorted(cards[:3]), 'rank': rank, 'length': 1})
            others = [c for c in hand if rank_of(c) != rank]
            if others:
                kick = min(others, key=lambda c: (rank_of(c), c))
                moves.append({'type': 'trio_single', 'cards': sorted(cards[:3] + [kick]),
                              'rank': rank, 'length': 1})
            for other_rank, other_cards in by_rank.items():
                if other_rank != rank and other_rank <= 12 and len(other_cards) >= 2:
                    moves.append({'type': 'trio_pair', 'cards': sorted(cards[:3] + other_cards[:2]),
                                  'rank': rank, 'length': 1})
        if len(cards) == 4 and rank <= 12:
            moves.append({'type': 'bomb', 'cards': sorted(cards), 'rank': rank, 'length': 1})
    moves.extend(_sequence_moves(by_rank, each=1, min_len=5, mtype='straight'))
    moves.extend(_sequence_moves(by_rank, each=2, min_len=3, mtype='pair_straight'))
    moves.extend(_sequence_moves(by_rank, each=3, min_len=2, mtype='plane'))
    if 52 in hand and 53 in hand:
        moves.append({'type': 'rocket', 'cards': [52, 53], 'rank': 14, 'length': 1})
    # de-duplicate identical (type, cards) moves
    seen, unique = set(), []
    for move in moves:
        key = (move['type'], tuple(move['cards']))
        if key not in seen:
            seen.add(key)
            unique.append(move)
    if trick is None:
        return [m for m in unique if m['type'] != 'pass']
    return [m for m in unique if m['type'] == 'pass' or _beats(m, trick)]


def _beats(move, trick):
    if move['type'] == 'rocket':
        return True
    if trick['type'] == 'rocket':
        return False
    if move['type'] == 'bomb':
        return trick['type'] != 'bomb' or move['rank'] > trick['rank']
    if trick['type'] == 'bomb':
        return False
    return (move['type'] == trick['type'] and move['length'] == trick['length']
            and move['rank'] > trick['rank'])


def move_name(move) -> str:
    if move['type'] == 'pass':
        return 'pass'
    cards = ' '.join(card_name(c) for c in move['cards'])
    names = {'single': '单张', 'pair': '对子', 'trio': '三张', 'trio_single': '三带一',
             'trio_pair': '三带二', 'straight': '顺子', 'pair_straight': '连对',
             'plane': '飞机', 'bomb': '炸弹', 'rocket': '王炸'}
    tail = f" ({move['length']}连)" if move['type'] in ('straight', 'pair_straight', 'plane') else ''
    return f"{names[move['type']]} {cards}{tail}"


def _reference_move(state, moves, trick):
    """The reference policy: smallest winning play; peasant cooperation; bomb timing."""
    if not moves:
        return {'type': 'pass', 'cards': [], 'rank': -1, 'length': 0}
    non_pass = [m for m in moves if m['type'] != 'pass']
    if trick is None:
        unloading = [m for m in non_pass if m['type'] != 'bomb' and m['type'] != 'rocket']
        empties = [m for m in non_pass if len(m['cards']) == len(state['hands'][state['turn']])]
        if empties:
            return empties[0]
        pool = unloading or non_pass
        return min(pool, key=lambda m: (len(m['cards']) * 4 + m['rank']))
    owner = trick['owner']
    is_landlord = state['landlord']
    same_team = (state['turn'] != is_landlord and owner != is_landlord)
    if same_team and (trick['rank'] >= 10 or len(state['hands'][owner]) <= 4):
        return moves[0] if moves[0]['type'] == 'pass' else {'type': 'pass', 'cards': [], 'rank': -1, 'length': 0}
    plain = [m for m in non_pass if m['type'] not in ('bomb', 'rocket')]
    if plain:
        return min(plain, key=lambda m: m['rank'])
    danger = len(state['hands'][owner]) <= 2 or trick['rank'] >= 11
    explosives = [m for m in non_pass if m['type'] in ('bomb', 'rocket')]
    if explosives and danger:
        return min(explosives, key=lambda m: (m['type'] != 'bomb', m['rank']))
    return moves[0] if moves[0]['type'] == 'pass' else {'type': 'pass', 'cards': [], 'rank': -1, 'length': 0}


def make_doudizhu(seed: int):
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    deck = list(range(54))
    deck = _shuffle(deck, (seed * 2 + 1) & MASK64)
    hands = [sorted(deck[0:17]), sorted(deck[17:34]), sorted(deck[34:51])]
    bottom = sorted(deck[51:54])
    landlord = seed % 3
    hands[landlord] = sorted(hands[landlord] + bottom)
    return {
        'game': 'doudizhu', 'seed': seed, 'rng_state': 0,
        'hands': hands, 'bottom': bottom, 'landlord': landlord,
        'turn': landlord, 'trick': None, 'passes': 0,
        'done': False, 'outcome': None, 'multiplier': 1,
        'history': [], 'plays': 0,
    }


def validate_state(state):
    required = {'game', 'seed', 'rng_state', 'hands', 'bottom', 'landlord', 'turn',
                'trick', 'passes', 'done', 'outcome', 'multiplier', 'history', 'plays'}
    if not isinstance(state, dict) or not required <= state.keys() or state['game'] != 'doudizhu':
        raise ValueError('Expected a complete Dou Dizhu state')
    if not 0 <= state['landlord'] <= 2 or not 0 <= state['turn'] <= 2:
        raise ValueError('Seat out of range')
    # Bottom cards were folded into the landlord's hand, so the partition check covers
    # hands + history only; bottom must appear in the landlord's hand.
    in_play = sorted(sum(state['hands'], []) +
                     [c for entry in state['history'] for c in entry['cards']])
    if in_play != list(range(54)):
        raise ValueError('The 54 cards must be partitioned across hands and history')
    if state['plays'] == 0 and not set(state['bottom']) <= set(state['hands'][state['landlord']]):
        raise ValueError('Bottom cards must sit in the landlord hand at deal time')
    if state['done'] and state['outcome'] not in ('landlord_win', 'peasants_win'):
        raise ValueError('Invalid terminal outcome')


def step(state, move):
    if state['done']:
        raise ValueError('Terminal states have no moves')
    legal = gen_moves(state['hands'][state['turn']], state['trick'])
    key = (move.get('type'), tuple(move.get('cards', [])))
    if not any((m['type'], tuple(m['cards'])) == key for m in legal):
        raise ValueError('Illegal move for the current seat')
    state = copy.deepcopy(state)
    seat = state['turn']
    if move['type'] != 'pass':
        for card in move['cards']:
            state['hands'][seat].remove(card)
        state['trick'] = {'type': move['type'], 'cards': sorted(move['cards']),
                          'rank': move['rank'], 'length': move['length'], 'owner': seat}
        state['passes'] = 0
        if move['type'] in ('bomb', 'rocket'):
            state['multiplier'] *= 2
        state['history'].append({'seat': seat, **{k: move[k] for k in ('type', 'cards', 'rank', 'length')}})
    else:
        state['passes'] += 1
        if state['passes'] >= 2:
            state['trick'] = None
            state['passes'] = 0
    state['plays'] += 1
    if not state['hands'][seat]:
        state['done'] = True
        state['outcome'] = 'landlord_win' if seat == state['landlord'] else 'peasants_win'
        return state
    state['turn'] = (state['turn'] + 1) % 3
    return state


def render_request(state):
    """Physical observations for the seat on turn: own hand, counts, trick; no hidden hands."""
    seat = state['turn']
    moves = gen_moves(state['hands'][seat], state['trick'])
    hand = state['hands'][seat]
    hand_text = ' '.join(card_name(c) for c in sorted(hand, key=rank_of))
    trick = state['trick']
    trick_text = 'no active play — you lead' if trick is None else (
        f"{SEATS[trick['owner']]} played {move_name(trick)}")
    text = (f"Dou Dizhu, seat {seat} ({SEATS[seat]}), landlord is seat {state['landlord']}. "
            f"Your hand ({len(hand)} cards): {hand_text}. Other hands: "
            f"seat {(seat+1)%3} has {len(state['hands'][(seat+1)%3])} cards, "
            f"seat {(seat+2)%3} has {len(state['hands'][(seat+2)%3])} cards. "
            f"Table: {trick_text}. Multiplier x{state['multiplier']}. "
            "Rules: beat the table with the same type and a higher rank, or with a bomb/rocket; "
            "two passes return the lead. As a peasant, your partner peasant is an ally — do not "
            "outbid their strong plays. Empty your hand first to win.")
    criteria = {}
    for index, move in enumerate(moves):
        if move['type'] == 'pass':
            criteria[f'm{index}'] = 'Pass this turn.'
        else:
            beats_now = state['trick'] is None or _beats(move, state['trick'])
            left = len(hand) - len(move['cards'])
            criteria[f'm{index}'] = (f"Play {move_name(move)}; leaves {left} cards in hand."
                                     + ('' if beats_now or state['trick'] is None else ''))
    questions = {'move': {'type': 'choice', 'instructions':
        'Choose the single best play. Lead by unloading large combinations first and saving '
        'singles; follow by beating with the smallest sufficient play. As a peasant, never '
        'outbid your partner peasant when their play is already strong (rank >= J) or when they '
        'are within a few cards of winning. Save bombs and the rocket for when the landlord is '
        'within two cards of winning or the table rank is A or higher. Emptying your hand wins '
        'immediately — always take that play when it exists.',
        'criteria': criteria}}
    return {'state': text, 'questions': questions, 'moves': [
        {'id': f'm{i}', 'type': m['type'], 'cards': m['cards'], 'name': move_name(m)}
        for i, m in enumerate(moves)]}


def make_record(state, split):
    if not isinstance(split, str) or split not in SPLITS:
        raise ValueError('Unknown split')
    public = render_request(state)
    seat = state['turn']
    moves = gen_moves(state['hands'][seat], state['trick'])
    trick = state['trick']
    reference = _reference_move(state, moves, trick)
    key = (reference['type'], tuple(reference['cards']))
    gold_id = next(f'm{i}' for i, m in enumerate(moves)
                   if (m['type'], tuple(m['cards'])) == key)
    gold = {'move': gold_id}
    probabilities = {'move': {}}
    for i, m in enumerate(moves):
        beats_now = bool(trick is None or (m['type'] != 'pass' and _beats(m, trick)))
        gold[f'beats_m{i}'] = beats_now
        probabilities[f'beats_m{i}'] = {'true': float(beats_now), 'false': float(not beats_now)}
        probabilities['move'][f'm{i}'] = float((m['type'], tuple(m['cards'])) == key)
    total = sum(probabilities['move'].values())
    probabilities['move'] = {k: v / total for k, v in probabilities['move'].items()}
    identity = 'doudizhu:' + _hash({'hands': state['hands'], 'turn': seat,
                                    'trick': state['trick']})[:24]
    return {'id': identity, 'state_id': identity, 'family_id': 'doudizhu_turn_v1',
            'split': split, **public, 'gold': gold, 'gold_probs': probabilities,
            'metadata': {'source': 'self_authored_programmatic', 'license': 'CC0-1.0',
                         'target_semantics': ("'move' gold is a reference heuristic policy "
                                              "(smallest winning play, peasant cooperation, "
                                              "bomb timing), not a game-theoretic optimum."),
                         'beats_truth': 'deterministic_truth'}}
