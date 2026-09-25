from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .actions import ACTION_DESCRIPTIONS, Action
from .state import MarioSnapshot


@dataclass(frozen=True)
class Decision:
    action: Action
    confidence: float
    probabilities: Mapping[str, float]
    latency_ms: float
    jump_needed_probability: float | None = None
    danger_score: float | None = None


class Policy(Protocol):
    def choose(self, snapshot: MarioSnapshot, actions: Sequence[Action]) -> Decision: ...


class TypeSafePolicy:
    def __init__(self) -> None:
        try:
            from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
        except ImportError as exc:
            raise RuntimeError(
                "typesafe-sdk is not installed. Install the project before using Jev."
            ) from exc
        self._Choice = Choice
        self._Noul = Noul
        self._Score = Score
        self._client = TypeSafeClient()

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _answer(response: Any, question_id: str, typed_collection: str) -> Any:
        collection = getattr(response, typed_collection, None)
        if collection is not None and question_id in collection:
            return collection[question_id]
        answers = getattr(response, "answers", None)
        if answers is not None and question_id in answers:
            return answers[question_id]
        raise KeyError(f"TypeSafe response omitted {question_id!r}")

    def choose(self, snapshot: MarioSnapshot, actions: Sequence[Action]) -> Decision:
        criteria = {action.value: ACTION_DESCRIPTIONS[action] for action in actions}
        questions = {
            "next_action": self._Choice(
                instructions={
                    "question": "Which controller macro should Mario commit to next?",
                    "goal": "Advance toward the stage flag while avoiding death.",
                    "timing": "The selected action is held for at least 8 emulator frames.",
                    "geometry": (
                        "Use `terrain.observation_reliability`. While airborne, prefer "
                        "`terrain.last_grounded_preview` over low-reliability current geometry. "
                        "A trusted obstacle or gap within three tiles requires a forward jump."
                    ),
                    "trajectory": (
                        "Use `trajectory`. If `crossing_known_gap` is true, preserve forward "
                        "speed and keep a forward jump held while rising. Do not switch to noop "
                        "or left over a gap."
                    ),
                    "stall": (
                        "If `episode.stalled_frames` is increasing and "
                        "`recent_control.outcome` is blocked, the current non-jump action failed."
                    ),
                    "enemy_timing": (
                        "Use `hazard` projections, not distance alone. Code has already accounted "
                        "for inference delay, action cadence, and the frames needed to clear an "
                        "enemy. If `jump_must_start_this_decision` is true, choose a forward jump "
                        "now; another right-run decision will miss the takeoff deadline. If "
                        "`contact_within_reaction_horizon` is true, also jump immediately. If "
                        "`will_land_before_contact` is true, the current jump will not clear the "
                        "enemy and another takeoff will be needed after landing. Use "
                        "`upcoming_enemies` and their spacing to avoid landing on a second or "
                        "third enemy hidden behind the nearest one."
                    ),
                    "delay": (
                        "`reaction_timing` describes how far the world moves before this choice "
                        "takes effect. Judge urgency from projected rather than current distance."
                    ),
                },
                criteria=criteria,
            ),
            "jump_needed": self._Noul(
                instructions=(
                    "Do trusted `terrain`, projected `hazard`, `trajectory`, and "
                    "`player.jump_phase` indicate that a forward jump should begin or remain "
                    "held now? `hazard.jump_must_start_this_decision=true` is unambiguously yes. "
                    "Also count a trusted obstacle/gap within three tiles, immediate projected "
                    "contact, or a rising jump over a known gap as yes."
                )
            ),
            "danger": self._Score(
                instructions="How dangerous is Mario's immediate situation?",
                criteria=[
                    "Safe open movement",
                    "Potential obstacle or enemy soon",
                    "Immediate collision, fall, or enemy threat",
                ],
            ),
        }
        started = time.perf_counter()
        response = self._client.system_one(state=snapshot.to_state(), questions=questions)
        latency_ms = (time.perf_counter() - started) * 1000

        action_answer = self._answer(response, "next_action", "choices")
        jump_answer = self._answer(response, "jump_needed", "nouls")
        danger_answer = self._answer(response, "danger", "scores")
        action = Action(str(action_answer.choice))
        probabilities = {
            str(key): float(value) for key, value in dict(action_answer.probabilities).items()
        }
        return Decision(
            action=action,
            confidence=float(action_answer.confidence),
            probabilities=probabilities,
            latency_ms=latency_ms,
            jump_needed_probability=float(jump_answer.noul),
            danger_score=float(danger_answer.score),
        )


class HeuristicPolicy:
    """Offline smoke-test policy; not intended as the Mario benchmark baseline."""

    def choose(self, snapshot: MarioSnapshot, actions: Sequence[Action]) -> Decision:
        allowed = set(actions)
        action = Action.RIGHT_RUN if Action.RIGHT_RUN in allowed else actions[0]
        if snapshot.stalled_steps >= 2 and Action.RIGHT_RUN_JUMP in allowed:
            action = Action.RIGHT_RUN_JUMP
        return Decision(
            action=action,
            confidence=1.0,
            probabilities={candidate.value: float(candidate == action) for candidate in actions},
            latency_ms=0.0,
        )
