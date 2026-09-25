"""A/B the JevHarness-style Mario harness v2 against the upstream harness, on real ROM.

Variants
--------
* **v1 (upstream, as shipped)** — ``TypeSafePolicy`` with its static instructions and
  static criteria.  This is the baseline the repro measured all along.
* **v2 (JevHarness-style)** — ``MarioHarnessV2``: pre-computed takeoff-window verdicts in
  the state, per-action criteria carrying this decision's measured consequences, and the
  cross-episode memory distilled into per-hazard lessons.  The reader (the scripted
  pilot) answers from the published verdict instead of redoing physics — the same
  division of labour the JevHarness reference harness uses (damage race computed in
  code, judge picks an option).

Both run on the real emulator with the release-edge wrapper, because the headless
branch's missing button-up edge (see README §4) would otherwise mask any harness
difference: a policy that cannot jump twice in a row dies at the first pipe regardless
of how good its information is.

Honest scope
------------
The reader is a rules-based stand-in, so what this measures is the value of harness
information quality to a faithful reader.  With ``TYPESAFE_API_KEY`` the same script
measures real Jev.

Run:  ../typesafe-mario/.venv/bin/python harness_ab.py [--episodes 6] [--max-decisions 1500]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

os.environ.setdefault("TYPESAFE_API_KEY", "local-replay-not-a-real-key")

import httpx2  # noqa: E402

import gymnasium as gym  # noqa: E402
from gym_super_mario_bros.actions import SIMPLE_MOVEMENT  # noqa: E402
from nes_py.wrappers import JoypadSpace  # noqa: E402

import typesafe_mario.runner as runner_module  # noqa: E402
from ab_real_env import (  # noqa: E402
    ACTION_TO_INDEX,
    JUMP_ACTIONS,
    JUMP_RELEASE_ACTION,
    GroundedRelay,
    _HOLDS_A,
    _INDEX_TO_ACTION,
)
from attempt_memory import AttemptMemory  # noqa: E402
from mario_harness_v2 import MarioHarnessV2, pilot_choose_v2  # noqa: E402
from parser_fix import CorrectedParser  # noqa: E402
from repro_run import patched_client  # noqa: E402
from typesafe_mario.actions import Action  # noqa: E402
from typesafe_mario.policy import TypeSafePolicy  # noqa: E402

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts" / "harness_ab"


# --------------------------------------------------------------- the stand-in judge
class PilotTransport(httpx2.BaseTransport):
    """Answers in the real wire format, choosing via a supplied reader function."""

    def __init__(self, decide) -> None:
        self.decide = decide
        self.requests: list[dict[str, Any]] = []
        self.choices: list[str] = []

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content or b"{}")
        state = payload.get("state", {})
        questions = payload.get("questions", {})
        pick, probabilities = self.decide(state)
        self.requests.append(payload)
        self.choices.append(pick)

        answers: dict[str, Any] = {
            "next_action": {
                "type": "choice",
                "choice": pick,
                "confidence": 0.88,
                "probabilities": probabilities,
            }
        }
        # Only answer what was asked; harness v2 sends a single question.
        if "jump_needed" in questions:
            answers["jump_needed"] = {"type": "noul", "noul": 0.7}
        if "danger" in questions:
            answers["danger"] = {
                "type": "score",
                "score": 1.0,
                "confidence": 0.85,
                "legend": {0: "safe", 1: "soon", 2: "immediate"},
                "probabilities": {"0": 0.2, "1": 0.6, "2": 0.2},
            }
        return httpx2.Response(
            200,
            json={
                "model": "scripted stand-in (NOT Jev)",
                "usage": {"input_tokens": len(json.dumps(state)), "output_tokens": 16},
                "answers": answers,
            },
        )


class ReaderPolicy:
    """Wraps a real policy class so the relay edge sees the snapshot's grounded flag."""

    def __init__(self, factory, relay: GroundedRelay, decide=None, memory=None) -> None:
        self._relay = relay
        self._decide = decide
        self._memory = memory
        self._inner = factory(memory=memory) if memory is not None else factory()

    def choose(self, snapshot, actions: Sequence[Action]):
        self._relay.grounded = bool(snapshot.grounded)
        if self._decide is not None:
            # The stand-in reader path: state assembly happens here (v2 features), the
            # transport only answers.  Mirrors what MarioHarnessV2.choose would send.
            state = snapshot.to_state()
            from mario_harness_v2 import feasibility_features

            state["takeoff_window"] = feasibility_features(state)
            if self._memory is not None:
                history = self._memory.as_context()
                if history is not None:
                    history = dict(history)
                    from mario_harness_v2 import lessons_from_deaths

                    history["lessons"] = lessons_from_deaths(history.get("deaths", []))
                    state["prior_attempts"] = history
            pick, probabilities = self._decide(state)
            from typesafe_mario.policy import Decision

            return Decision(
                action=Action(pick),
                confidence=0.88,
                probabilities=probabilities,
                latency_ms=0.5,
            )
        return self._inner.choose(snapshot, actions)

    def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if callable(close):
            close()


class EdgeEnv:
    """The dashboard's release-frame rule, applied to whatever env is wrapped."""

    def __init__(self, env, frames_per_decision: int, relay: GroundedRelay) -> None:
        self._env = env
        self._fpd = frames_per_decision
        self._relay = relay
        self._batch_frame = frames_per_decision
        self._a_held = False

    def __getattr__(self, name):
        return getattr(self._env, name)

    def reset(self, **kwargs):
        self._batch_frame = self._fpd
        self._a_held = False
        return self._env.reset(**kwargs)

    def step(self, action_index: int):
        action = _INDEX_TO_ACTION.get(action_index)
        if self._batch_frame >= self._fpd:
            self._batch_frame = 0
            if (
                action is not None
                and action in JUMP_ACTIONS
                and self._relay.grounded
                and self._a_held
            ):
                action_index = ACTION_TO_INDEX[JUMP_RELEASE_ACTION[action]]
        self._batch_frame += 1
        if action is not None:
            self._a_held = _HOLDS_A[action]
        return self._env.step(action_index)

    def close(self) -> None:
        self._env.close()


# ------------------------------------------------------------------- one episode
def run_episode(*, variant: str, episode: int, seed: int, max_decisions: int,
                frames_per_decision: int, memory: AttemptMemory | None) -> dict:
    relay = GroundedRelay()
    created: dict[str, object] = {}
    upstream_factory = runner_module.create_mario_env

    def factory(env_id: str, render_mode: str = "human"):
        env = JoypadSpace(gym.make(env_id, render_mode=render_mode), SIMPLE_MOVEMENT)
        env = EdgeEnv(env, frames_per_decision, relay)
        created["env"] = env
        return env

    runner_module.create_mario_env = factory  # type: ignore[assignment]
    runner_module.MarioStateParser = CorrectedParser  # sensor fix, see parser_fix.py

    # Everything that touches TypeSafeClient must be constructed INSIDE the patched
    # context: the patch swaps the class at construction time, so a policy built outside
    # would hold a real client pointed at the real API with the placeholder key.
    from repro_run import ScriptedPilotTransport

    if variant == "v2":
        transport = PilotTransport(pilot_choose_v2)
    else:
        transport = PilotTransport(ScriptedPilotTransport._decide)

    with patched_client(transport):
        if variant == "v2":
            policy = ReaderPolicy(
                lambda memory=memory: MarioHarnessV2(memory=memory),
                relay,
                decide=pilot_choose_v2,
                memory=memory,
            )
        else:
            policy = ReaderPolicy(TypeSafePolicy, relay)
        log_path = runner_module.run_episode(
            env_id="SuperMarioBros-1-1-v0",
            policy=policy,
            frames_per_decision=frames_per_decision,
            max_decisions=max_decisions,
            seed=seed,
            artifacts_dir=ARTIFACTS / variant / f"ep{episode:02d}",
            display="none",
        )

    records = [
        json.loads(line) for line in log_path.read_text().splitlines() if line.strip()
    ]
    if not records:
        return {"episode": episode, "best_x": 0, "ended": "empty", "cleared": False}
    last = records[-1]
    terminal = bool(last.get("terminated"))
    best_x = max(r["state"]["episode"]["best_progress"] for r in records)
    died = bool(last["state"]["episode"]["dead"])
    cleared = bool(
        last["state"]["episode"]["stage_clear"]
        or (terminal and not died and last.get("reward", 0.0) >= 100.0)
    )
    last_state = last["state"]
    # The §3.3 trap, again: each record holds the state BEFORE its action batch, so a
    # death in the final batch appears only as terminated=true with episode.dead still
    # false.  A terminated episode that is not a clear is a death, full stop.
    died = died or (terminal and not cleared)
    out = {
        "episode": episode,
        "seed": seed,
        "decisions": len(records),
        "best_x": best_x,
        "final_x": last_state["player"]["x"],
        "cleared": cleared,
        "died": died,
        "at_x": last_state["player"]["x"] if died else best_x,
        "airborne_at_end": not last_state["player"]["grounded"],
        "action_at_end": last.get("action"),
        "log": str(log_path.relative_to(HERE)),
    }

    if memory is not None:
        if out["died"]:
            # Record what the episode ended with; lessons_from_deaths turns these into
            # actionable per-hazard lessons for the next episode's criteria.
            memory.record_death_fields(
                at_x=out["at_x"],
                at_y=last_state["player"]["y"],
                action_when_lost=out["action_at_end"],
                airborne=out["airborne_at_end"],
                jump_phase=last_state["player"]["jump_phase"],
                gap_distance_tiles=last_state["terrain"].get("gap_distance_tiles"),
                obstacle_distance_tiles=last_state["terrain"].get(
                    "obstacle_distance_tiles"
                ),
                nearest_enemy=last_state["hazard"].get("nearest_enemy_kind"),
                cause=(
                    "fell after a jump did not reach safe ground"
                    if out["airborne_at_end"]
                    else "blocked or enemy contact"
                ),
            )
        memory.start_episode()
    return out


# ------------------------------------------------------------------- the experiment
def run_variant(*, variant: str, episodes: int, max_decisions: int,
                frames_per_decision: int, base_seed: int) -> dict:
    memory = AttemptMemory(max_deaths=8) if variant == "v2" else None
    results = []
    for i in range(episodes):
        seed = base_seed + i
        result = run_episode(
            variant=variant,
            episode=i,
            seed=seed,
            max_decisions=max_decisions,
            frames_per_decision=frames_per_decision,
            memory=memory,
        )
        results.append(result)
        flag = "CLEAR" if result.get("cleared") else ""
        print(
            f"  {variant} ep{i}: best_x={result['best_x']:<5} "
            f"decisions={result['decisions']:<4} "
            f"{'died@' + str(result.get('at_x')) if result.get('died') else flag}",
            flush=True,
        )
    clears = sum(1 for r in results if r.get("cleared"))
    best = max(r["best_x"] for r in results)
    mean = sum(r["best_x"] for r in results) / len(results)
    deaths = [r for r in results if r.get("died")]
    return {
        "variant": variant,
        "episodes": results,
        "clears": clears,
        "best_x_max": best,
        "best_x_mean": round(mean, 1),
        "death_xs": [int(r.get("at_x") or 0) for r in deaths],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=6)
    parser.add_argument("--max-decisions", type=int, default=1500)
    parser.add_argument("--frames-per-decision", type=int, default=8)
    parser.add_argument("--base-seed", type=int, default=123)
    args = parser.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "env": "real gym_super_mario_bros + bundled ROM",
        "release_edge": "applied to BOTH variants (see README §4: the headless bug would mask harness quality)",
        "reader": "scripted stand-in, NOT Jev (set TYPESAFE_API_KEY for the real model)",
        "episodes_per_variant": args.episodes,
        "max_decisions": args.max_decisions,
        "base_seed": args.base_seed,
    }

    print(f"v1 = upstream harness (static questions), v2 = JevHarness-style "
          f"(feasibility + dynamic criteria + lessons); both with release edge")
    for variant in ("v1", "v2"):
        print(f"=== {variant} ===", flush=True)
        report[variant] = run_variant(
            variant=variant,
            episodes=args.episodes,
            max_decisions=args.max_decisions,
            frames_per_decision=args.frames_per_decision,
            base_seed=args.base_seed,
        )
        r = report[variant]
        print(
            f"  -> clears={r['clears']}/{args.episodes}  "
            f"best_x max={r['best_x_max']}  mean={r['best_x_mean']}  "
            f"deaths@={r['death_xs']}"
        )

    (ARTIFACTS / "harness_ab_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    print()
    print(f"wrote {ARTIFACTS / 'harness_ab_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
