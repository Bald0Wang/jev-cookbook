"""Deterministic Sudoku dynamics and per-cell decision questions (standard library).

Modeled on NanoJev's ``snake_game.py``: a complete, JSON-round-trippable state;
``make`` / ``validate_state`` / ``step`` / ``render_request`` / ``make_record``; a
deterministic SplitMix64 stream so identical seeds reproduce identical puzzles; and
rendered requests that omit solution and seed, exactly as the snake omits RNG state.

Episode shape: the harness picks the next empty cell (most-constrained-first, computed
from published facts), and the judge answers one ``choice`` question — which digit to
write — plus one ``boolean`` question per digit ("is d consistent with the unique
solution?").  A wrong digit counts as a mistake; three mistakes end the episode.  Gold
labels are computable because the puzzle has a unique solution.

The state carries ``solution`` (physical fact, like the snake's RNG state) but
``render_request`` never publishes it.
"""
import copy
import hashlib
import json

DIGITS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
SPLITS = {'train', 'dev', 'calibration', 'test', 'ood'}
MASK64 = (1 << 64) - 1
MAX_MISTAKES = 3


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
    return items, rng_state


def _box_of(row, col):
    return (row // 3) * 3 + col // 3


def _peers(grid, row, col):
    """Digits present in the same row, column, or 3x3 box."""
    seen = set()
    for index in range(9):
        seen.add(grid[row][index])
        seen.add(grid[index][col])
    box_row, box_col = 3 * (row // 3), 3 * (col // 3)
    for r in range(box_row, box_row + 3):
        for c in range(box_col, box_col + 3):
            seen.add(grid[r][c])
    seen.discard(0)
    return seen


def _candidates(grid, row, col):
    return [d for d in DIGITS if d not in _peers(grid, row, col)]


def _count_solutions(grid, limit=2):
    """Backtracking solution counter; stops as soon as ``limit`` is reached."""
    def backtrack():
        best = None
        for r in range(9):
            for c in range(9):
                if grid[r][c] == 0:
                    cands = _candidates(grid, r, c)
                    if best is None or len(cands) < len(best[2]):
                        best = (r, c, cands)
                        if len(cands) <= 1:
                            break
            if best is not None and len(best[2]) <= 1:
                break
        if best is None:
            return 1
        r, c, cands = best
        total = 0
        for digit in cands:
            grid[r][c] = digit
            total += backtrack()
            grid[r][c] = 0
            if total >= limit:
                return total
        return total
    return backtrack()


def _fill_complete(rng_state):
    """A random complete grid via constrained backtracking with deterministic order."""
    grid = [[0] * 9 for _ in range(9)]

    def backtrack():
        best = None
        for r in range(9):
            for c in range(9):
                if grid[r][c] == 0:
                    cands = _candidates(grid, r, c)
                    if best is None or len(cands) < len(best[2]):
                        best = (r, c, cands)
            if best is not None and len(best[2]) <= 1:
                break
        if best is None:
            return True
        r, c, cands = best
        cands, rng_state_local = _shuffle(cands, _fill_complete.rng)
        _fill_complete.rng = rng_state_local
        for digit in cands:
            grid[r][c] = digit
            if backtrack():
                return True
            grid[r][c] = 0
        return False

    _fill_complete.rng = rng_state
    backtrack()
    return grid, _fill_complete.rng


def make_sudoku(seed: int, holes: int = 40):
    """A puzzle with a unique solution, carved deterministically from a full grid."""
    if type(seed) is not int or type(holes) is not int or not 0 <= holes <= 64:
        raise ValueError('seed must be an integer and holes an integer in [0, 64]')
    solution, rng_state = _fill_complete(seed)
    grid = [row[:] for row in solution]
    cells = [(r, c) for r in range(9) for c in range(9)]
    cells, rng_state = _shuffle(cells, rng_state)
    removed = 0
    for r, c in cells:
        if removed >= holes:
            break
        saved = grid[r][c]
        grid[r][c] = 0
        probe = [row[:] for row in grid]
        if _count_solutions(probe, limit=2) == 1:
            removed += 1
        else:
            grid[r][c] = saved
    givens = [[cell != 0 for cell in row] for row in grid]
    return {
        'game': 'sudoku', 'seed': seed, 'holes': holes, 'rng_state': rng_state,
        'grid': grid, 'givens': givens, 'solution': solution,
        'done': False, 'outcome': None, 'score': 0, 'mistakes': 0, 'steps': 0,
    }


def validate_state(state):
    required = {'game', 'seed', 'holes', 'rng_state', 'grid', 'givens', 'solution',
                'done', 'outcome', 'score', 'mistakes', 'steps'}
    if not isinstance(state, dict) or not required <= state.keys() or state['game'] != 'sudoku':
        raise ValueError('Expected a complete Sudoku state')
    if type(state['seed']) is not int or type(state['holes']) is not int or not 0 <= state['holes'] <= 64:
        raise ValueError('Invalid seed or hole count')
    if type(state['rng_state']) is not int or not 0 <= state['rng_state'] <= MASK64:
        raise ValueError('Invalid 64-bit RNG state')
    for key in ('grid', 'givens', 'solution'):
        table = state[key]
        if not isinstance(table, list) or len(table) != 9 or any(len(row) != 9 for row in table):
            raise ValueError(f'{key} must be a 9x9 table')
    for key in ('grid', 'solution'):
        if any(type(v) is not int or not 0 <= v <= 9 for row in state[key] for v in row):
            raise ValueError(f'{key} cells must be integers in [0, 9]')
    if any(type(v) is not bool for row in state['givens'] for v in row):
        raise ValueError('givens must be booleans')
    for r in range(9):
        for c in range(9):
            if state['givens'][r][c]:
                if state['grid'][r][c] == 0:
                    raise ValueError('A given cell must hold its digit in a live grid')
            elif not state['done'] and state['grid'][r][c] != 0 and state['grid'][r][c] != state['solution'][r][c]:
                raise ValueError('A live non-given cell can only hold the solution digit')
    for units in ([state['grid'][r][:] for r in range(9)],
                  [[state['grid'][r][c] for r in range(9)] for c in range(9)],
                  [[state['grid'][3 * (r // 3) + dr][3 * (c // 3) + dc] for dr in range(3) for dc in range(3)]
                   for r in range(3) for c in range(3)]):
        for line in units:
            values = [v for v in line if v]
            if len(values) != len(set(values)):
                raise ValueError('A live grid never repeats a digit in a row, column, or box')
    if type(state['done']) is not bool or any(type(state[k]) is not int or state[k] < 0
                                              for k in ('score', 'mistakes', 'steps')):
        raise ValueError('Invalid terminal flag or counters')
    complete = state['grid'] == state['solution']
    if state['done']:
        expected = 'win' if complete else 'three_mistakes'
        if state['outcome'] != expected:
            raise ValueError('Terminal outcome does not match the grid and mistake count')
    elif state['outcome'] is not None or complete or state['mistakes'] >= MAX_MISTAKES:
        raise ValueError('A live state cannot be complete or over the mistake limit')


def next_cell(state):
    """Most-constrained empty cell, computed from published facts only (MRV)."""
    best = None
    for r in range(9):
        for c in range(9):
            if state['grid'][r][c] == 0:
                cands = _candidates(state['grid'], r, c)
                if best is None or len(cands) < len(best[2]):
                    best = (r, c, cands)
                    if len(cands) <= 1:
                        break
        if best is not None and len(best[2]) <= 1:
            break
    return None if best is None else (best[0], best[1], best[2])


def valid_digits(state):
    cell = next_cell(state)
    if cell is None:
        return []
    return cell[2]


def step(state, digit):
    """Write ``digit`` into the harness-chosen cell; a wrong digit is a mistake."""
    if state['done']:
        raise ValueError('Terminal states have no moves')
    cell = next_cell(state)
    if cell is None:
        raise ValueError('No empty cell remains')
    row, col, _ = cell
    truth = state['solution'][row][col]
    state = copy.deepcopy(state)
    state['steps'] += 1
    if digit == truth:
        state['grid'][row][col] = digit
        state['score'] += 1
    else:
        state['mistakes'] += 1
    if state['grid'] == state['solution']:
        state['done'], state['outcome'] = True, 'win'
    elif state['mistakes'] >= MAX_MISTAKES:
        state['done'], state['outcome'] = True, 'three_mistakes'
    return state


def _constraints_text(state, row, col):
    row_vals = sorted(v for v in state['grid'][row] if v)
    col_vals = sorted(state['grid'][r][col] for r in range(9) if state['grid'][r][col])
    box_vals = sorted({state['grid'][r][c]
                       for r in range(3 * (row // 3), 3 * (row // 3) + 3)
                       for c in range(3 * (col // 3), 3 * (col // 3) + 3)} - {0})
    return (f'row {row} already contains {row_vals}; column {col} already contains {col_vals}; '
            f'the 3x3 box already contains {box_vals}')


def render_request(state):
    """Physical observations only; no solution, seed or RNG."""
    cell = next_cell(state)
    if cell is None:
        raise ValueError('Terminal states have no question')
    row, col, cands = cell
    board = '\n'.join(
        ' '.join(str(v) if v else '.' for v in state['grid'][r]) +
        ('   <- next cell (row %d, column %d)' % (row, col) if r == row else '')
        for r in range(9)
    )
    text = (f"Sudoku 9x9, zero-based (row,column). Dots are empty cells.\n{board}\n"
            f"The next cell to fill is (row {row}, column {col}). "
            f"{_constraints_text(state, row, col)[0].upper() + _constraints_text(state, row, col)[1:]}. "
            "A digit already present in the row, column, or box is impossible. Among the digits "
            "that survive all three constraints, exactly one matches the puzzle's unique solution; "
            "the puzzle is solvable by constraint reasoning alone when a cell has a single candidate, "
            "and by elimination when a digit fits nowhere else in its row, column, or box.")
    questions = {'digit': {'type': 'choice', 'instructions':
        'Write exactly one digit into the named cell. Use the published row/column/box exclusions '
        'first: digits listed there are impossible. Among the survivors, prefer a digit that '
        'appears as a candidate for no other empty cell in its row, column, or box (a hidden '
        'single). Do not guess between two equally-reasoned survivors.',
        'criteria': {str(d): (
            f'Write {d} at (row {row}, column {col}). '
            + ('IMPOSSIBLE: it already appears in ' + _conflict_unit(state, row, col, d) + '.'
               if d in _peers(state['grid'], row, col) else
               'survives all three row/column/box checks.')) for d in DIGITS}}}
    for d in DIGITS:
        questions[f'fits_{d}'] = {'type': 'boolean', 'instructions':
            f'If the cell (row {row}, column {col}) is filled with {d}, is that the digit the '
            'puzzle\'s unique solution places there? Constraint survival is necessary but not '
            'sufficient.',
            'criteria': {'true': f'{d} is the solution digit for this cell.',
                         'false': f'The solution digit for this cell is not {d}.'}}
    return {'state': text, 'questions': questions, 'cell': [row, col], 'candidates': cands}


def _conflict_unit(state, row, col, digit):
    if digit in state['grid'][row]:
        return f'row {row}'
    if any(state['grid'][r][col] == digit for r in range(9)):
        return f'column {col}'
    return 'the 3x3 box'


def make_record(state, split):
    if not isinstance(split, str) or split not in SPLITS:
        raise ValueError('Unknown split')
    public = render_request(state)
    row, col = public['cell']
    truth = state['solution'][row][col]
    identity = 'sudoku:' + _hash({'grid': state['grid'], 'cell': [row, col]})[:24]
    fits = {d: (d == truth) for d in DIGITS}
    gold = {'digit': str(truth)}
    probabilities = {'digit': {str(d): float(d == truth) for d in DIGITS}}
    for d in DIGITS:
        gold[f'fits_{d}'] = fits[d]
        probabilities[f'fits_{d}'] = {'true': float(fits[d]), 'false': float(not fits[d])}
    return {'id': identity, 'state_id': identity,
            'family_id': 'sudoku_next_cell_v1', 'split': split, **public,
            'gold': gold, 'gold_probs': probabilities,
            'metadata': {'source': 'self_authored_programmatic', 'license': 'CC0-1.0',
                         'environment_state': copy.deepcopy(state),
                         'target_semantics': ('Fill the published cell with the unique-solution '
                                              'digit; constraint survival is necessary but not '
                                              'sufficient for correctness.')}}
