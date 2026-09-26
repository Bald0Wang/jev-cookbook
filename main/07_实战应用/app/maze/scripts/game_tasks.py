#!/usr/bin/env python3
"""可程序求解的自写小游戏；纯标准库，无模型或外部数据。

Public API: valid_actions(state), step(state, action), solve(state).
States are JSON dictionaries; actions are strings; step never mutates its input.
"""

from collections import deque
from functools import lru_cache
import copy
import unittest


LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
DIRECTIONS = {'north': (-1, 0), 'east': (0, 1), 'south': (1, 0), 'west': (0, -1)}


def transform_cell(cell, size, symmetry):
    """Eight D4 symmetries: optional left/right reflection, then rotations."""
    if symmetry not in range(8):
        raise ValueError('symmetry must be 0..7')
    row, col = cell
    if symmetry >= 4:
        col = size - 1 - col
    for _ in range(symmetry % 4):
        row, col = col, size - 1 - row
    return row, col


def ttt_winner(board):
    winners = {board[a] for a, b, c in LINES if board[a] != '.' and board[a] == board[b] == board[c]}
    if len(winners) > 1:
        raise ValueError('Both players cannot win in a legal game')
    return next(iter(winners), None)


def validate_state(state):
    game = state.get('game')
    if game == 'tic_tac_toe':
        board, player = state['board'], state['player']
        if not isinstance(board, str) or len(board) != 9 or set(board) - {'.', 'X', 'O'}:
            raise ValueError('Board must contain nine ., X or O characters')
        nx, no = board.count('X'), board.count('O')
        if nx not in {no, no + 1} or player != ('X' if nx == no else 'O'):
            raise ValueError('Invalid move counts or side to move')
        winner = ttt_winner(board)
        if (winner == 'X' and nx != no + 1) or (winner == 'O' and nx != no):
            raise ValueError('Move counts contradict the terminal winner')
    elif game == 'grid_navigation':
        size = state['size']
        if type(size) is not int or size < 2:
            raise ValueError('Grid size must be at least 2')
        walls = {tuple(cell) for cell in state['walls']}
        if len(walls) != len(state['walls']):
            raise ValueError('Duplicate walls')
        for cell in list(walls) + [tuple(state['position']), tuple(state['goal'])]:
            if len(cell) != 2 or any(type(x) is not int or not 0 <= x < size for x in cell):
                raise ValueError('Cell outside grid')
        if tuple(state['position']) in walls or tuple(state['goal']) in walls:
            raise ValueError('Position and goal must be walkable')
    else:
        raise ValueError(f'Unknown game: {game}')


def valid_actions(state):
    validate_state(state)
    if state['game'] == 'tic_tac_toe':
        if ttt_winner(state['board']):
            return []
        return [f'cell_{i + 1}' for i, value in enumerate(state['board']) if value == '.']
    if state['position'] == state['goal']:
        return []
    row, col = state['position']
    size, walls = state['size'], {tuple(cell) for cell in state['walls']}
    return [name for name, (dr, dc) in DIRECTIONS.items()
            if 0 <= row + dr < size and 0 <= col + dc < size and (row + dr, col + dc) not in walls]


def step(state, action):
    if action not in valid_actions(state):
        raise ValueError(f'Illegal action: {action}')
    result = copy.deepcopy(state)
    if state['game'] == 'tic_tac_toe':
        index = int(action.removeprefix('cell_')) - 1
        board = list(state['board'])
        board[index] = state['player']
        result['board'] = ''.join(board)
        result['player'] = 'O' if state['player'] == 'X' else 'X'
    else:
        dr, dc = DIRECTIONS[action]
        result['position'] = [state['position'][0] + dr, state['position'][1] + dc]
    return result


@lru_cache(maxsize=None)
def _ttt_value(board, player):
    winner = ttt_winner(board)
    if winner:
        return 1 if winner == player else -1
    if '.' not in board:
        return 0
    opponent = 'O' if player == 'X' else 'X'
    return max(-_ttt_value(board[:i] + player + board[i+1:], opponent)
               for i, value in enumerate(board) if value == '.')


def grid_distances(state):
    size, walls, goal = state['size'], {tuple(cell) for cell in state['walls']}, tuple(state['goal'])
    distances, queue = {goal: 0}, deque([goal])
    while queue:
        row, col = queue.popleft()
        for dr, dc in DIRECTIONS.values():
            nxt = (row + dr, col + dc)
            if 0 <= nxt[0] < size and 0 <= nxt[1] < size and nxt not in walls and nxt not in distances:
                distances[nxt] = distances[(row, col)] + 1
                queue.append(nxt)
    return distances


def solve(state):
    validate_state(state)
    actions = valid_actions(state)
    if state['game'] == 'tic_tac_toe':
        value = _ttt_value(state['board'], state['player'])
        values = {}
        for action in actions:
            child = step(state, action)
            values[action] = -_ttt_value(child['board'], child['player'])
        return {'terminal': not actions, 'value': value, 'winner': ttt_winner(state['board']),
                'action_values': values, 'optimal_actions': [a for a in actions if values[a] == value],
                'objective': 'maximize win/draw/loss under perfect adversarial play; no preference for win timing'}
    distances = grid_distances(state)
    distance = distances.get(tuple(state['position']))
    costs = {}
    for action in actions:
        destination = tuple(step(state, action)['position'])
        costs[action] = None if destination not in distances else 1 + distances[destination]
    finite = [cost for cost in costs.values() if cost is not None]
    best = min(finite) if finite else None
    return {'terminal': not actions, 'distance': distance,
            'reachable': distance is not None, 'action_costs': costs,
            'optimal_actions': [a for a in actions if costs[a] == best],
            'objective': 'minimize steps to the goal; if unreachable, all legal moves tie'}


def transform_state(state, symmetry):
    validate_state(state)
    transformed = copy.deepcopy(state)
    if state['game'] == 'tic_tac_toe':
        board = ['.'] * 9
        for index, token in enumerate(state['board']):
            row, col = transform_cell(divmod(index, 3), 3, symmetry)
            board[row * 3 + col] = token
        transformed['board'] = ''.join(board)
    else:
        size = state['size']
        transformed['walls'] = sorted([list(transform_cell(cell, size, symmetry)) for cell in state['walls']])
        transformed['position'] = list(transform_cell(state['position'], size, symmetry))
        transformed['goal'] = list(transform_cell(state['goal'], size, symmetry))
    return transformed


def source_group_id(state):
    """Group all board symmetries; grid groups also ignore the starting position."""
    if state['game'] == 'tic_tac_toe':
        key = min(transform_state(state, i)['board'] for i in range(8))
        return f'ttt:{key}:{state["player"]}'
    maps = []
    for i in range(8):
        transformed = transform_state(state, i)
        maps.append((tuple(transformed['goal']), tuple(map(tuple, transformed['walls']))))
    goal, walls = min(maps)
    return f'grid:{state["size"]}:goal={goal}:walls={walls}'


@lru_cache(maxsize=1)
def all_ttt_states():
    """Enumerate reachable positions, stopping each trajectory immediately at a win."""
    seen = {}

    def visit(state):
        key = state['board']
        if key in seen:
            return
        seen[key] = state
        for action in valid_actions(state):
            visit(step(state, action))

    visit({'game': 'tic_tac_toe', 'board': '.' * 9, 'player': 'X'})
    return tuple(seen.values())


def self_test():
    class GameTests(unittest.TestCase):
        def test_ttt_forced_win_and_block(self):
            win = {'game': 'tic_tac_toe', 'board': 'XX.OO....', 'player': 'X'}
            self.assertEqual(solve(win)['value'], 1)
            self.assertIn('cell_3', solve(win)['optimal_actions'])
            terminal = step(win, 'cell_3')
            self.assertEqual(valid_actions(terminal), [])
            self.assertEqual(solve(terminal)['value'], -1)
            self.assertEqual(win['board'], 'XX.OO....')
            with self.assertRaises(ValueError):
                step(win, 'cell_1')
            block = {'game': 'tic_tac_toe', 'board': 'XX..O....', 'player': 'O'}
            self.assertEqual(solve(block)['optimal_actions'], ['cell_3'])

        def test_enumeration_and_symmetry(self):
            states = all_ttt_states()
            self.assertEqual(len(states), 5478)
            self.assertEqual(solve({'game': 'tic_tac_toe', 'board': '.' * 9, 'player': 'X'})['value'], 0)
            for state in states[::73]:
                for symmetry in range(8):
                    transformed = transform_state(state, symmetry)
                    self.assertEqual(source_group_id(state), source_group_id(transformed))
                    self.assertEqual(solve(state)['value'], solve(transformed)['value'])

        def test_grid_tie_detour_and_unreachable(self):
            open_grid = {'game': 'grid_navigation', 'size': 3, 'walls': [], 'position': [2, 0], 'goal': [0, 2]}
            self.assertEqual(solve(open_grid)['distance'], 4)
            self.assertEqual(set(solve(open_grid)['optimal_actions']), {'north', 'east'})
            detour = {**open_grid, 'walls': [[0, 1], [1, 1]], 'position': [0, 0]}
            self.assertEqual(solve(detour)['distance'], 6)
            self.assertEqual(solve(detour)['optimal_actions'], ['south'])
            unreachable = {**open_grid, 'walls': [[0, 1], [1, 2]]}
            self.assertFalse(solve(unreachable)['reachable'])
            self.assertEqual(solve(unreachable)['optimal_actions'], valid_actions(unreachable))
            for symmetry in range(8):
                transformed = transform_state(detour, symmetry)
                self.assertEqual(solve(transformed)['distance'], 6)
                self.assertEqual(source_group_id(transformed), source_group_id(detour))
            other_start = {**detour, 'position': [2, 0]}
            self.assertEqual(source_group_id(detour), source_group_id(other_start))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GameTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    return {'tests': result.testsRun, 'passed': True}


if __name__ == '__main__':
    self_test()
