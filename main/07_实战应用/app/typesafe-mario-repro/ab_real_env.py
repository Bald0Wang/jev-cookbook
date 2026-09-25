"""Prove the missing button-up edge on the real emulator, not just the synthetic one.

The synthetic A/B (`ab_release_edge.py`) showed the effect in a controlled world.  This
script repeats it against the **real** ``gym_super_mario_bros`` environment and the real
NES ROM, which is the version of the finding that matters.

The observable is unambiguous: in World 1-1 the first tall pipe sits at x≈608.  A policy
holding a forward-jump macro on consecutive grounded decisions gets one jump and then
cannot jump again, so Mario walks into the pipe and stops — ``jump_phase`` stays
``grounded`` for hundreds of decisions while the policy keeps asking to jump.

Both variants run the real ``run_episode``, the real emulator, and the real
``TypeSafePolicy``; only the model's HTTP hop is served locally, and the wrapper supplies
the release frame the dashboard path would insert.

Run:  ../typesafe-mario/.venv/bin/python ab_real_env.py [--decisions 300]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("TYPESAFE_API_KEY", "local-replay-not-a-real-key")

import gymnasium as gym  # noqa: E402
from gym_super_mario_bros.actions import SIMPLE_MOVEMENT  # noqa: E402
from nes_py.wrappers import JoypadSpace  # noqa: E402

import typesafe_mario.runner as runner_module  # noqa: E402
from typesafe_mario.actions import (  # noqa: E402
    ACTION_TO_INDEX,
    JUMP_ACTIONS,
    JUMP_RELEASE_ACTION,
)
from repro_run import ScriptedPilotTransport, patched_client  # noqa: E402
from typesafe_mario.policy import TypeSafePolicy  # noqa: E402

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts" / "ab_real_env"


class GroundedRelay:
    """Carries the `grounded` flag from the snapshot the policy saw to the env wrapper.

    The real emulator exposes no ``grounded`` attribute, and the upstream dashboard reads
    it from the snapshot::

        if decision_updated and action in JUMP_ACTIONS and snapshot.grounded:

    So the flag is relayed from the very same snapshot — the policy records it as it
    chooses, and the wrapper consults it at the start of each decision batch.  That keeps
    the injected condition identical to the dashboard's, rather than an approximation of it.
    """

    def __init__(self) -> None:
        self.grounded = False


class GroundedAwarePolicy:
    """The real policy, plus a tap on the snapshot's grounded flag."""

    def __init__(self, relay: GroundedRelay) -> None:
        self._relay = relay
        self._inner = TypeSafePolicy()

    def choose(self, snapshot, actions):
        self._relay.grounded = bool(snapshot.grounded)
        return self._inner.choose(snapshot, actions)

    def close(self) -> None:
        self._inner.close()


class RealReleaseEdgeEnv:
    """Injects the dashboard's release frame into the headless loop, on the real env."""

    def __init__(self, env, frames_per_decision: int, relay: GroundedRelay) -> None:
        self._env = env
        self._frames_per_decision = frames_per_decision
        self._relay = relay
        self._batch_frame = frames_per_decision
        self._injected = 0
        self._a_held = False
        self.terminal: dict | None = None

    def __getattr__(self, name):
        return getattr(self._env, name)

    def reset(self, **kwargs):
        self._batch_frame = self._frames_per_decision
        self._a_held = False
        return self._env.reset(**kwargs)

    def step(self, action_index: int):
        action = _INDEX_TO_ACTION.get(action_index)
        if self._batch_frame >= self._frames_per_decision:
            self._batch_frame = 0
            if (
                action is not None
                and action in JUMP_ACTIONS
                and self._relay.grounded
                and self._a_held
            ):
                self._injected += 1
                action = JUMP_RELEASE_ACTION[action]
                action_index = ACTION_TO_INDEX[action]
        self._batch_frame += 1
        if action is not None:
            self._a_held = _HOLDS_A[action]

        result = self._env.step(action_index)
        _, _, terminated, truncated, info = result
        if (terminated or truncated) and self.terminal is None:
            self.terminal = {
                "reason": "death" if info.get("is_dead") or info.get("is_dying") else "stage_clear",
                "x": int(info.get("x_pos", 0)),
            }
        return result

    def close(self) -> None:
        self._env.close()


_HOLDS_A = {
    action: "A" in SIMPLE_MOVEMENT[index] for action, index in ACTION_TO_INDEX.items()
}
_INDEX_TO_ACTION = {index: action for action, index in ACTION_TO_INDEX.items()}


def real_env_factory(frames_per_decision: int, with_edge: bool, relay: GroundedRelay):
    """Build the upstream env; optionally wrap it with the dashboard's release edge."""
    created: dict[str, object] = {}

    def factory(env_id: str, render_mode: str = "human"):
        env = gym.make(env_id, render_mode=render_mode)
        env = JoypadSpace(env, SIMPLE_MOVEMENT)
        if with_edge:
            wrapper = RealReleaseEdgeEnv(env, frames_per_decision, relay)
            created["env"] = wrapper
            return wrapper
        created["env"] = env
        return env

    return factory, created


def analyse(log_path: Path) -> dict:
    records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    phases = Counter(r["state"]["player"]["jump_phase"] for r in records)
    grounded = Counter(r["state"]["player"]["grounded"] for r in records)
    max_x = max(r["state"]["player"]["x"] for r in records)
    stuck_at = None
    for record in records:
        if record["state"]["player"]["x"] >= max_x:
            stuck_at = record["decision"]
            break
    trailing = len(records) - (stuck_at or 0)
    return {
        "decisions": len(records),
        "max_x": max_x,
        "jump_phase_counts": dict(phases),
        "grounded_counts": {str(k): v for k, v in grounded.items()},
        "never_left_ground": phases.get("grounded", 0) == len(records),
        "decisions_at_final_x": trailing,
        "requests": None,
    }


def run_case(*, with_edge: bool, decisions: int, frames_per_decision: int, seed: int) -> dict:
    relay = GroundedRelay()
    factory, created = real_env_factory(frames_per_decision, with_edge, relay)
    runner_module.create_mario_env = factory  # type: ignore[assignment]
    out_dir = ARTIFACTS / ("with_edge" if with_edge else "baseline")
    transport = ScriptedPilotTransport()

    with patched_client(transport):
        policy = GroundedAwarePolicy(relay) if with_edge else TypeSafePolicy()
        log_path = runner_module.run_episode(
            env_id="SuperMarioBros-1-1-v0",
            policy=policy,
            frames_per_decision=frames_per_decision,
            max_decisions=decisions,
            seed=seed,
            artifacts_dir=out_dir,
            display="none",
        )

    result = analyse(log_path)
    result["requests"] = len(transport.requests)
    result["injected_release_frames"] = getattr(created.get("env"), "_injected", 0)
    result["log"] = str(log_path.relative_to(HERE))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=int, default=400)
    parser.add_argument("--frames-per-decision", type=int, default=8)
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "env": "real gym_super_mario_bros + real NES ROM",
        "env_id": "SuperMarioBros-1-1-v0",
        "decisions": args.decisions,
    }

    print("real emulator, real ROM, real TypeSafePolicy, real run_episode")
    print(f"{'variant':<24}{'max_x':>7}{'decisions_at_max_x':>20}{'never_left_ground':>19}{'release_frames':>16}")
    for label, with_edge in (("baseline (as shipped)", False), ("with release edge", True)):
        result = run_case(
            with_edge=with_edge,
            decisions=args.decisions,
            frames_per_decision=args.frames_per_decision,
            seed=args.seed,
        )
        report[label] = result
        print(
            f"{label:<24}{result['max_x']:>7}{result['decisions_at_final_x']:>20}"
            f"{str(result['never_left_ground']):>19}{result['injected_release_frames']:>16}"
        )

    print()
    for label in ("baseline (as shipped)", "with release edge"):
        result = report[label]
        print(f"{label}:")
        print(f"  jump_phase counts : {result['jump_phase_counts']}")
        print(f"  log               : {result['log']}")

    (ARTIFACTS / "ab_real_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    print()
    print(f"wrote {ARTIFACTS / 'ab_real_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
