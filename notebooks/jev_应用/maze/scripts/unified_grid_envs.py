"""Finite-horizon Maze and Snake environments with JSON decision observations.

Maze actions attempt untried directions, including blocked directions. Automatic
repositioning uses only edges physically traversed earlier and consumes the same
physical-step budget. The full attempted/open-edge memory is visible as compact
row-wise masks; hidden geometry and route oracles never enter observations.

Snake offers every non-reverse direction. Its objective is to collect target_food
additional food items after reset. Rewards are 1 on task success, otherwise 0.
The formal deadline is task termination, never an external truncation.

An optional initial_state supplies a complete simulator snapshot instead of seed
generation. Its stored Snake RNG is retained exactly; the seed argument controls
generation only when no snapshot is supplied. All returned objects are detached.
"""

from collections import deque
import copy
import json

from evaluate_composed_maze import render_local_request
import scaled_maze
import snake_game


DIRECTIONS = dict(scaled_maze.DIRECTIONS)
REVERSE = dict(snake_game.REVERSE)
BITS = {action: 1 << index for index, action in enumerate(DIRECTIONS)}


def _positive(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _json(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _destination(position, action):
    dr, dc = DIRECTIONS[action]
    return position[0] + dr, position[1] + dc


class _Base:
    def __init__(self, spec, task):
        if not isinstance(spec, dict) or spec.get("task") != task:
            raise ValueError(f"Expected a {task} specification")
        self.spec = copy.deepcopy(spec)
        self.task = task
        self.size = _positive(spec.get("size", 8), "size", 2)
        self.max_steps = _positive(spec.get("max_steps", 4 * self.size * self.size), "max_steps")
        self.history_limit = _positive(spec.get("history_limit", 8), "history_limit", 0)
        self._closed = False
        self._initialized = False

    def _reset_counters(self, seed):
        if self._closed:
            raise RuntimeError("The environment is closed")
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        self._steps = self._decisions = self._collisions = 0
        self._success = self._terminated = False
        self._outcome = "in_progress"
        self._history = deque(maxlen=self.history_limit)
        self._initialized = True

    def _check_action(self, action):
        if self._closed or not self._initialized:
            raise RuntimeError("Reset an open environment before stepping")
        if self._terminated:
            raise RuntimeError("Cannot step a terminal episode")
        if not isinstance(action, str) or action not in self._candidates():
            raise ValueError("Action must be one of the currently offered candidate IDs")

    def _finish(self, outcome, success=False):
        self._terminated, self._success, self._outcome = True, bool(success), outcome

    def _observation(self, text):
        return {"task": self.task, "state": text, "candidates": self._candidates(),
                "remaining_steps": self.max_steps - self._steps, "step": self._steps}

    def _metrics(self):
        return {"physical_steps": self._steps, "decision_steps": self._decisions,
                "remaining_steps": self.max_steps - self._steps, "collisions": self._collisions,
                "success": self._success, "outcome": self._outcome}

    def _info(self, events):
        return {"success": self._success, "terminated": self._terminated, "truncated": False,
                "outcome": self._outcome, "episode_metrics": self._metrics(),
                "physical_steps_this_action": len(events),
                "macro_physical_steps": sum(event["actor"] == "verified_edge_reposition" for event in events),
                "physical_events": copy.deepcopy(events),
                "reward_semantics": "one on task success; zero otherwise"}

    def close(self):
        self._closed = True


class UnifiedMazeEnv(_Base):
    """Local observations, risky untried candidates, and verified-edge macros."""

    def __init__(self, spec):
        super().__init__(spec, "maze")
        if "initial_state" not in self.spec and self.size < 5:
            raise ValueError("Generated mazes require size >= 5")
        self.topology = self.spec.get("topology", "corridor")
        if self.topology not in scaled_maze.TOPOLOGIES:
            raise ValueError("Unknown maze topology")

    def reset(self, seed):
        self._reset_counters(seed)
        source = (copy.deepcopy(self.spec["initial_state"]) if "initial_state" in self.spec
                  else scaled_maze.make_maze(self.size, seed, self.topology))
        scaled_maze.validate_state(source)
        if source["size"] != self.size:
            raise ValueError("Snapshot size differs from specification")
        self._world = {key: copy.deepcopy(source[key]) for key in ("game", "size", "walls", "position", "goal")}
        self._walls = set(map(tuple, self._world["walls"]))
        self._position, self._goal = tuple(source["position"]), tuple(source["goal"])
        self._edges = {}
        self._graph = {self._position: set()}
        self._visits = {self._position: 1}
        self._macro_steps = 0
        if self._position == self._goal:
            self._finish("goal_reached", True)
        return self._observe(), self._info([])

    def _untried(self, position):
        return [action for action in DIRECTIONS if (position, action) not in self._edges]

    def _candidates(self):
        if self._terminated:
            return {}
        return {action: f"Attempt one cell {action} to {_json(_destination(self._position, action))}; this direction has not been tried here."
                for action in self._untried(self._position)}

    def _memory_rows(self):
        rows = []
        for row in range(self.size):
            codes = []
            for col in range(self.size):
                tried = sum(BITS[action] for action in DIRECTIONS if ((row, col), action) in self._edges)
                opened = sum(BITS[action] for action in DIRECTIONS if self._edges.get(((row, col), action)) == "open")
                codes.append(f"{tried:x}{opened:x}")
            runs = []
            index = 0
            while index < len(codes):
                end = index + 1
                while end < len(codes) and codes[end] == codes[index]:
                    end += 1
                runs.append(codes[index] + (f"x{end-index}" if end-index > 1 else ""))
                index = end
            rows.append(f"{row}:" + ",".join(runs))
        return "\n".join(rows)

    def _observe(self):
        current = {action: self._edges.get((self._position, action), "untried") for action in DIRECTIONS}
        local = render_local_request(self._world, window_size=5)["state"]
        text = (f"Maze task: reach goal {_json(self._goal)} within {self.max_steps} physical attempts. "
                f"Used: {self._steps}. Remaining: {self.max_steps-self._steps}. Outcome: {self._outcome}.\n"
                f"{local}\nCurrent direction memory: {_json(current)}.\n"
                "Only untried directions are offered, including possible collisions. When none remain, code repositions "
                "to the nearest known frontier using only previously traversed edges; every such move consumes one attempt.\n"
                "Complete observed edge memory, rows indexed from zero: each two-hex-digit code is tried-mask then open-mask. "
                "Bits: north=1, east=2, south=4, west=8. A code followed by xN repeats N columns. "
                "00 means no edge evidence, not a wall. Reverse edges of successful moves are also confirmed.\n"
                f"{self._memory_rows()}\nRecent physical events: {_json(list(self._history))}.")
        return self._observation(text)

    def _route_to_frontier(self):
        # This method intentionally accesses no simulator geometry or goal.
        previous, queue = {self._position: None}, deque([self._position])
        while queue:
            node = queue.popleft()
            if node != self._position and self._untried(node):
                route = []
                while previous[node] is not None:
                    node, action = previous[node]
                    route.append(action)
                return list(reversed(route))
            for action in DIRECTIONS:
                neighbor = _destination(node, action)
                if neighbor in self._graph.get(node, set()) and neighbor not in previous:
                    previous[neighbor] = node, action
                    queue.append(neighbor)
        return None

    def _attempt(self, action, actor):
        before, destination = self._position, _destination(self._position, action)
        reason = ("boundary" if not all(0 <= value < self.size for value in destination)
                  else "wall" if destination in self._walls else None)
        if actor == "verified_edge_reposition" and (reason or destination not in self._graph.get(before, set())):
            raise RuntimeError("A reposition macro must use a previously traversed open edge")
        self._steps += 1
        self._macro_steps += actor == "verified_edge_reposition"
        self._edges[(before, action)] = "blocked" if reason else "open"
        if reason:
            self._collisions += 1
        else:
            self._edges[(destination, REVERSE[action])] = "open"
            self._graph.setdefault(before, set()).add(destination)
            self._graph.setdefault(destination, set()).add(before)
            self._position = destination
            self._world["position"] = list(destination)
            self._visits[destination] = self._visits.get(destination, 0) + 1
        if self._position == self._goal:
            self._finish("goal_reached", True)
        elif self._steps == self.max_steps:
            self._finish("deadline")
        event = {"step": self._steps, "actor": actor, "action": action, "position": list(before),
                 "next_position": list(self._position), "collision": bool(reason), "collision_reason": reason,
                 "terminated": self._terminated, "success": self._success}
        self._history.append(copy.deepcopy(event))
        return event

    def _metrics(self):
        return {**super()._metrics(), "visited_cells": len(self._visits),
                "reposition_steps": self._macro_steps, "goal_reached": self._success}

    def step(self, action_id):
        self._check_action(action_id)
        self._decisions += 1
        events = [self._attempt(action_id, "model")]
        if not self._terminated and not self._untried(self._position):
            route = self._route_to_frontier()
            if route is None:
                self._finish("frontier_exhausted")
            else:
                for action in route:
                    if self._terminated:
                        break
                    events.append(self._attempt(action, "verified_edge_reposition"))
        return self._observe(), float(self._success), self._terminated, False, self._info(events)


class UnifiedSnakeEnv(_Base):
    """All non-reverse actions remain available, including fatal proposals."""

    def __init__(self, spec):
        super().__init__(spec, "snake")
        self.target_food = _positive(spec.get("target_food", max(1, self.size // 4)), "target_food")

    def reset(self, seed):
        self._reset_counters(seed)
        source = (copy.deepcopy(self.spec["initial_state"]) if "initial_state" in self.spec
                  else snake_game.make_snake(self.size, seed))
        snake_game.validate_state(source)
        if source["size"] != self.size:
            raise ValueError("Snapshot size differs from specification")
        self._world = {key: copy.deepcopy(source[key]) for key in
                       ("game", "size", "seed", "body", "direction", "food", "rng_state", "done", "outcome", "score", "steps")}
        self._initial_score = self._world["score"]
        self._survival_steps = 0
        if self._world["done"]:
            self._finish("initial_terminal")
        return self._observe(), self._info([])

    def _candidates(self):
        if self._terminated:
            return {}
        return {action: f"Move {action} to {_json(_destination(self._world['body'][0], action))}."
                for action in snake_game.valid_actions(self._world)}

    def _observe(self):
        state = self._world
        text = (f"Snake on a {self.size}x{self.size} board. Coordinates are zero-based (row,column); north decreases row, "
                f"east increases column. Body head first: {_json(state['body'])}. Direction: {state['direction']}. "
                f"Current food: {_json(state['food'])}. Food collected this episode: {state['score']-self._initial_score}. "
                f"Target: collect {self.target_food} additional food items after reset before {self.max_steps} attempts expire. "
                f"Used: {self._steps}. Remaining: {self.max_steps-self._steps}. Outcome: {self._outcome}. "
                "Reaching the target ends the task successfully immediately. Reverse moves are disallowed; all other directions "
                "are offered even if they collide. Eating retains the tail; otherwise the tail vacates and entering that cell is allowed. "
                "A wall or non-vacating body collision ends the task unsuccessfully. "
                f"Recent physical events: {_json(list(self._history))}.")
        return self._observation(text)

    def _metrics(self):
        return {**super()._metrics(), "food_collected": self._world["score"] - self._initial_score,
                "score": self._world["score"], "initial_score": self._initial_score,
                "target_food": self.target_food, "survival_steps": self._survival_steps,
                "body_length": len(self._world["body"]), "full_board_win": self._world["outcome"] == "win"}

    def step(self, action_id):
        self._check_action(action_id)
        before = copy.deepcopy(self._world)
        self._world = snake_game.step(self._world, action_id)
        self._steps += 1
        self._decisions += 1
        collision = self._world["outcome"] in {"wall_collision", "self_collision"}
        self._collisions += collision
        self._survival_steps += not collision
        if collision:
            self._finish(self._world["outcome"])
        elif self._world["score"] - self._initial_score >= self.target_food:
            self._finish("target_food_reached", True)
        elif self._world["done"]:
            self._finish("board_filled_before_target")
        elif self._steps == self.max_steps:
            self._finish("deadline")
        event = {"step": self._steps, "actor": "model", "action": action_id,
                 "head": copy.deepcopy(before["body"][0]), "next_head": copy.deepcopy(self._world["body"][0]),
                 "ate_food": self._world["score"] > before["score"], "collision": collision,
                 "terminated": self._terminated, "success": self._success}
        self._history.append(copy.deepcopy(event))
        return self._observe(), float(self._success), self._terminated, False, self._info([event])
