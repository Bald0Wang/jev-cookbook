from __future__ import annotations

from enum import StrEnum


class Action(StrEnum):
    NOOP = "noop"
    RIGHT = "right"
    RIGHT_JUMP = "right_jump"
    RIGHT_RUN = "right_run"
    RIGHT_RUN_JUMP = "right_run_jump"
    JUMP = "jump"
    LEFT = "left"


# These indices match gym_super_mario_bros.actions.SIMPLE_MOVEMENT.
ACTION_TO_INDEX: dict[Action, int] = {
    Action.NOOP: 0,
    Action.RIGHT: 1,
    Action.RIGHT_JUMP: 2,
    Action.RIGHT_RUN: 3,
    Action.RIGHT_RUN_JUMP: 4,
    Action.JUMP: 5,
    Action.LEFT: 6,
}

JUMP_ACTIONS = frozenset({Action.RIGHT_JUMP, Action.RIGHT_RUN_JUMP, Action.JUMP})

JUMP_RELEASE_ACTION: dict[Action, Action] = {
    Action.RIGHT_JUMP: Action.RIGHT,
    Action.RIGHT_RUN_JUMP: Action.RIGHT_RUN,
    Action.JUMP: Action.NOOP,
}


ACTION_DESCRIPTIONS: dict[Action, str] = {
    Action.NOOP: "Release the controls and let current momentum continue.",
    Action.RIGHT: "Move right at normal speed without jumping.",
    Action.RIGHT_JUMP: (
        "Start a controlled forward jump, or keep holding jump while rising to preserve height."
    ),
    Action.RIGHT_RUN: (
        "Run right only while trusted terrain is clear and "
        "`hazard.jump_must_start_this_decision` is false."
    ),
    Action.RIGHT_RUN_JUMP: (
        "Start a running jump when terrain or projected contact requires it, or keep holding "
        "it while rising. Prefer this when `hazard.jump_must_start_this_decision` is true."
    ),
    Action.JUMP: (
        "Jump mostly in place, or keep holding jump while rising when forward motion is unsafe."
    ),
    Action.LEFT: "Move left to evade danger or recover from an overshoot.",
}
