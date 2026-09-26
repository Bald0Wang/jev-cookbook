"""Headless ViZDoom adapter with bounded, visible-only text observations.

Install requirements-vizdoom.txt separately; importing this module needs only
the Python standard library. ``max_steps`` counts decisions, ``frame_skip``
counts Doom tics per decision, and optional ``max_ticks`` is an additional
task deadline measured from reset. Native scenario timeouts remain enabled.
All these deadlines are task terminations, never collector truncations.

Only visible label bounding boxes and player health/ammo/pose enter ``state``.
Kill/damage counters are evaluation information, not policy observations.
The bundled basic and predict_position scenarios each have one target.
Success means a positive KILLCOUNT delta, independently of native reward.

Primary API references:
https://vizdoom.farama.org/api/python/doom_game/
https://vizdoom.farama.org/api/python/game_state/
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from collections import deque
from pathlib import Path
import tempfile
from typing import Any, Mapping


def _load_vizdoom():
    try:
        return importlib.import_module("vizdoom")
    except ImportError as exc:
        raise ImportError(
            "ViZDoom is optional. Install it in your environment with "
            "python -m pip install -r requirements-vizdoom.txt"
        ) from exc


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _finite(value: Any, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise RuntimeError(f"ViZDoom returned a nonfinite {name}")
    return value


class UnifiedDoomEnv:
    """Synchronous PLAYER environment implementing reset/step/close.

    Specs: task='shooting', scenario='basic'|'predict_position',
    max_steps=75, frame_skip=4, optional max_ticks, history_length=2 (1..4).
    Actions are the stable IDs left/right/shoot/noop, with no combinations.
    reset(seed) re-seeds immediately before new_episode, including the first
    reset; the episode implicitly created by init is never used as a rollout.
    """

    _VARIABLES = (
        "HEALTH", "SELECTED_WEAPON_AMMO", "POSITION_X", "POSITION_Y",
        "POSITION_Z", "ANGLE", "KILLCOUNT", "DAMAGECOUNT", "DAMAGE_TAKEN",
    )
    _ACTIONS = {
        "left": (True, False, False),
        "right": (False, True, False),
        "shoot": (False, False, True),
        "noop": (False, False, False),
    }

    def __init__(self, spec: Mapping[str, Any]):
        self.spec = dict(spec)
        if self.spec.get("task", "shooting") != "shooting":
            raise ValueError("UnifiedDoomEnv only supports task='shooting'")
        self.scenario = self.spec.get("scenario", "basic")
        if self.scenario not in ("basic", "predict_position"):
            raise ValueError("scenario must be 'basic' or 'predict_position'")
        self.max_steps = _positive_int(self.spec.get("max_steps", 75), "max_steps")
        self.frame_skip = _positive_int(self.spec.get("frame_skip", 4), "frame_skip")
        self.max_ticks = _positive_int(
            self.spec.get("max_ticks", self.max_steps * self.frame_skip), "max_ticks"
        )
        self.history_length = _positive_int(
            self.spec.get("history_length", 2), "history_length"
        )
        if self.history_length > 4:
            raise ValueError("history_length must be at most 4")
        self._game = None
        self._vzd = None
        self._temporary = None
        self._active = False
        self._done = True
        self._history = deque(maxlen=self.history_length)
        self._metadata: dict[str, Any] = {}

    def _initialize(self):
        self._vzd = vzd = _load_vizdoom()
        game = vzd.DoomGame()
        self._game = game
        scenarios = Path(getattr(vzd, "scenarios_path", Path(vzd.__file__).parent / "scenarios"))
        config = scenarios / f"{self.scenario}.cfg"
        wad = scenarios / f"{self.scenario}.wad"
        if not config.is_file() or not wad.is_file():
            self.close()
            raise RuntimeError(f"Bundled ViZDoom scenario files are missing: {config}")
        self._temporary = tempfile.TemporaryDirectory(prefix="nanojev_doom_")
        try:
            game.load_config(str(config))
            game.set_doom_scenario_path(str(wad))
            game.set_doom_config_path(str(Path(self._temporary.name) / "vizdoom.ini"))
            game.set_mode(vzd.Mode.PLAYER)
            game.set_window_visible(False)
            game.set_sound_enabled(False)
            game.set_console_enabled(False)
            game.set_screen_resolution(vzd.ScreenResolution.RES_320X240)
            game.set_screen_format(vzd.ScreenFormat.RGB24)
            game.set_labels_buffer_enabled(True)
            game.set_objects_info_enabled(False)
            game.set_sectors_info_enabled(False)
            game.set_automap_buffer_enabled(False)
            game.set_depth_buffer_enabled(False)
            names = ("MOVE_LEFT", "MOVE_RIGHT", "ATTACK") if self.scenario == "basic" else (
                "TURN_LEFT", "TURN_RIGHT", "ATTACK"
            )
            game.set_available_buttons([getattr(vzd.Button, name) for name in names])
            missing = [name for name in self._VARIABLES if not hasattr(vzd.GameVariable, name)]
            if missing:
                raise RuntimeError(f"ViZDoom GameVariable API is missing: {missing}")
            game.set_available_game_variables([
                getattr(vzd.GameVariable, name) for name in self._VARIABLES
            ])
            self._metadata = {
                "backend": "vizdoom", "vizdoom_version": str(getattr(vzd, "__version__", "unknown")),
                "scenario": self.scenario, "mode": "PLAYER", "buttons": list(names),
                "scenario_config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
                "scenario_wad_sha256": hashlib.sha256(wad.read_bytes()).hexdigest(),
                "observation_source": "visible_label_boxes_and_player_health_ammo_pose",
                "objects_info_enabled": False, "sectors_info_enabled": False,
                "timeout_detection": "native_flag_and_episode_clock" if hasattr(
                    game, "is_episode_timeout_reached"
                ) else "episode_clock",
                "counter_source": "get_game_variable_after_each_single_tick",
                "physical_tick_source": "synchronous_single_tick_calls",
                "action_repeat": "same_buttons_until_duration_or_first_goal_terminal_tick",
                "frame_skip": self.frame_skip, "max_steps": self.max_steps,
                "max_ticks": self.max_ticks, "history_length": self.history_length,
            }
            game.init()
        except Exception:
            self.close()
            raise

    def _variables(self) -> dict[str, float]:
        # Explicit enum checks above prevent an absent enum being mistaken for 0.
        # No fallback from unreadable terminal counters to reward is permitted.
        return {
            name: _finite(self._game.get_game_variable(getattr(self._vzd.GameVariable, name)), name)
            for name in self._VARIABLES
        }

    def _remaining_ticks(self) -> int:
        budget = max(0, self.max_ticks - self._physical_ticks)
        if self._native_timeout > 0:
            budget = min(budget, max(0, self._native_timeout - self._episode_tick))
        return budget

    def _visible_snapshot(self, state, variables) -> dict[str, Any]:
        labels = []
        if state is not None:
            buffer = state.labels_buffer
            if buffer is None:
                raise RuntimeError("ViZDoom labels buffer is missing despite being enabled")
            for label in state.labels:
                # A bounding box alone is insufficient: require rendered pixels.
                # This never accesses state.objects, sectors, hidden entities or RNG.
                value = int(label.value)
                if value == 0 or not bool((buffer == value).any()):
                    continue
                box = [int(label.x), int(label.y), int(label.width), int(label.height)]
                if box[2] <= 0 or box[3] <= 0:
                    continue
                labels.append({"id": int(label.object_id), "name": str(label.object_name), "bbox": box})
        labels.sort(key=lambda row: (row["id"], row["name"], row["bbox"]))
        return {
            "episode_tick": self._episode_tick,
            "health": variables["HEALTH"], "ammo": variables["SELECTED_WEAPON_AMMO"],
            "position": [round(variables[f"POSITION_{axis}"], 3) for axis in "XYZ"],
            "angle_degrees": round(variables["ANGLE"], 3),
            "visible_labels": labels, "visual_state_available": state is not None,
        }

    def _observation(self) -> dict[str, Any]:
        ticks = 0 if self._done else self._remaining_ticks()
        remaining = 0 if self._done else min(
            self.max_steps - self._step, (ticks + self.frame_skip - 1) // self.frame_skip
        )
        duration = min(self.frame_skip, ticks)
        movement = "Strafe" if self.scenario == "basic" else "Turn"
        candidates = {} if self._done else {
            "left": f"{movement} left for {duration} Doom ticks.",
            "right": f"{movement} right for {duration} Doom ticks.",
            "shoot": f"Hold attack for {duration} Doom ticks.",
            "noop": f"Wait without pressing buttons for {duration} Doom ticks.",
        }
        payload = {
            "scenario": self.scenario, "goal": "Eliminate the monster before the task deadline.",
            "screen_size": [320, 240], "bbox_format": "x,y,width,height; origin top left",
            "remaining_decisions": remaining, "remaining_ticks": ticks,
            "observed_history": list(self._history), "terminal": self._done,
        }
        return {
            "task": "shooting", "state": json.dumps(payload, separators=(",", ":"), allow_nan=False),
            "candidates": candidates, "remaining_steps": remaining, "step": self._step,
        }

    def _info(self, native_reward=0.0, action_id=None, requested_ticks=0, actual_ticks=0):
        current = self._current
        metrics = {
            "success": self._success, "outcome": self._outcome,
            "decisions": self._step, "physical_ticks": self._physical_ticks,
            "native_reward": self._native_reward,
            "killcount": current["KILLCOUNT"],
            "kills": current["KILLCOUNT"] - self._initial["KILLCOUNT"],
            "damage_dealt": current["DAMAGECOUNT"] - self._initial["DAMAGECOUNT"],
            "damage_taken": current["DAMAGE_TAKEN"] - self._initial["DAMAGE_TAKEN"],
            "health": current["HEALTH"], "ammo": current["SELECTED_WEAPON_AMMO"],
            "ammo_consumed": self._ammo_consumed,
        }
        return {
            **self._metadata, "seed": self._seed, "success": self._success,
            "episode_metrics": metrics, "native_reward": native_reward,
            "native_total_reward": _finite(self._game.get_total_reward(), "total_reward"),
            "action_id": action_id, "requested_ticks": requested_ticks, "actual_ticks": actual_ticks,
            "episode_tick": self._episode_tick, "episode_start_tick": self._start_tick,
            "native_episode_tick": self._native_episode_tick,
            "native_clock_resets": self._native_clock_resets,
            "native_timeout_tick": self._native_timeout,
            "terminated": self._done, "truncated": False,
            "terminal_reason": self._outcome if self._done else None,
            "bootstrap_allowed": not self._done,
        }

    def reset(self, seed: int = 0):
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
            raise ValueError("seed must be an integer in [0, 2**32)")
        if self._game is None:
            self._initialize()
        self._game.set_seed(seed)
        self._game.new_episode()
        if self._game.is_episode_finished():
            raise RuntimeError("ViZDoom scenario is already terminal at reset")
        self._seed = seed
        self._step = self._physical_ticks = 0
        self._native_reward = self._ammo_consumed = 0.0
        self._episode_tick = self._start_tick = int(self._game.get_episode_time())
        self._native_episode_tick = self._episode_tick
        self._native_clock_resets = 0
        self._native_timeout = int(self._game.get_episode_timeout())
        self._initial = self._current = self._variables()
        self._success = self._done = False
        self._outcome = "running"
        self._active = True
        self._history.clear()
        state = self._game.get_state()
        if state is None or self._remaining_ticks() <= 0:
            raise RuntimeError("ViZDoom reset has no usable state or remaining task ticks")
        self._history.append(self._visible_snapshot(state, self._current))
        return self._observation(), self._info()

    def step(self, action_id: str):
        if not self._active or self._done:
            raise RuntimeError("Call reset before step and after every terminal transition")
        if not isinstance(action_id, str) or action_id not in self._ACTIONS:
            raise ValueError(f"Unknown action ID: {action_id!r}")
        requested = min(self.frame_skip, self._remaining_ticks())
        if requested <= 0:
            raise RuntimeError("Live episode unexpectedly has no remaining physical ticks")
        reward, actual = 0.0, 0
        finished = dead = native_timeout = False
        # A multi-tic call can cross a scripted map exit and reset episode time
        # and counters. Advance one synchronous tic at a time, holding the same
        # chosen buttons, so the first observed kill is retained before that exit.
        for _ in range(requested):
            previous, before_tick = self._current, self._native_episode_tick
            reward += _finite(self._game.make_action(list(self._ACTIONS[action_id]), 1), "reward")
            self._native_episode_tick = int(self._game.get_episode_time())
            finished = bool(self._game.is_episode_finished())
            native_delta = self._native_episode_tick - before_tick
            if native_delta != 1:
                if finished and native_delta <= 0:
                    self._native_clock_resets += 1
                else:
                    raise RuntimeError(f"Unexpected clock change after one synchronous tick: {native_delta}")
            actual += 1
            self._physical_ticks += 1
            self._episode_tick = self._start_tick + self._physical_ticks
            self._current = self._variables()
            self._ammo_consumed += max(
                0.0, previous["SELECTED_WEAPON_AMMO"] - self._current["SELECTED_WEAPON_AMMO"]
            )
            self._success = self._current["KILLCOUNT"] > self._initial["KILLCOUNT"]
            dead = bool(self._game.is_player_dead())
            native_timeout = self._native_timeout > 0 and self._episode_tick >= self._native_timeout
            if hasattr(self._game, "is_episode_timeout_reached"):
                native_timeout = native_timeout or bool(self._game.is_episode_timeout_reached())
            if self._success or dead or finished or native_timeout:
                break
        self._step += 1
        self._native_reward += reward
        deadline = self._step >= self.max_steps or self._physical_ticks >= self.max_ticks
        self._done = bool(self._success or dead or native_timeout or deadline or finished)
        self._outcome = (
            "target_killed" if self._success else "player_dead" if dead else
            "native_timeout" if native_timeout else "task_deadline" if deadline else
            "native_terminal_without_kill" if finished else "running"
        )
        self._history.append(self._visible_snapshot(self._game.get_state(), self._current))
        return self._observation(), reward, self._done, False, self._info(reward, action_id, requested, actual)

    def close(self):
        if self._game is not None:
            try:
                self._game.close()
            finally:
                self._game = None
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
        self._active = False
        self._done = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
