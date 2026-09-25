"""Run the upstream harness against the REAL Super Mario Bros. emulator.

This is the run that should have come first.  ``gym-super-mario-bros`` 9.1.0 — the exact
dependency the upstream ``pyproject.toml`` declares — ships the NES ROM inside the
installed package, so the author's original emulator path works on this machine with no
extra download:

    .venv/lib/python3.13/site-packages/gym_super_mario_bros/_roms/super-mario-bros.nes

Nothing is substituted here except the HTTP hop to the model, because this machine has no
``TYPESAFE_API_KEY``:

* environment  — **real** ``gym_super_mario_bros`` + real NES emulation + real ROM;
* RAM          — **real** 2 KB NES memory, parsed by the upstream ``MarioStateParser``;
* runner       — **real** upstream ``run_episode``;
* policy       — **real** upstream ``TypeSafePolicy`` (questions, SDK call, answer
  decoding) with the HTTP hop served by the scripted pilot.

The scripted pilot is still not Jev; set ``TYPESAFE_API_KEY`` in the environment and this
script talks to the real API with no other change.

Run:  ../typesafe-mario/.venv/bin/python repro_real_env.py [--decisions 400]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("TYPESAFE_API_KEY", "local-replay-not-a-real-key")

import gymnasium as gym  # noqa: E402
from gym_super_mario_bros.actions import SIMPLE_MOVEMENT  # noqa: E402
from nes_py.wrappers import JoypadSpace  # noqa: E402

import typesafe_mario.runner as runner_module  # noqa: E402
from repro_run import ScriptedPilotTransport, patched_client, summarise  # noqa: E402
from typesafe_mario.policy import HeuristicPolicy, TypeSafePolicy  # noqa: E402

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts" / "real_env"
ROM = Path(gym.__file__).parent / ".."  # resolved below for the provenance record


def rom_path() -> Path:
    import gym_super_mario_bros
    return Path(gym_super_mario_bros.__file__).parent / "_roms" / "super-mario-bros.nes"


def real_env(env_id: str, render_mode: str = "human"):
    """The upstream ``create_mario_env`` body, verbatim, with no substitution."""
    env = gym.make(env_id, render_mode=render_mode)
    return JoypadSpace(env, SIMPLE_MOVEMENT)


def run(*, policy_name: str, decisions: int, frames_per_decision: int, seed: int):
    runner_module.create_mario_env = real_env  # type: ignore[assignment]
    out_dir = ARTIFACTS / policy_name
    transport = None

    def go(policy):
        return runner_module.run_episode(
            env_id="SuperMarioBros-1-1-v0",
            policy=policy,
            frames_per_decision=frames_per_decision,
            max_decisions=decisions,
            seed=seed,
            artifacts_dir=out_dir,
            display="none",
        )

    if policy_name == "typesafe":
        transport = ScriptedPilotTransport()
        with patched_client(transport):
            log_path = go(TypeSafePolicy())
    else:
        log_path = go(HeuristicPolicy())

    summary = summarise(log_path)
    summary["requests"] = len(transport.requests) if transport else 0
    return summary, log_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=int, default=400)
    parser.add_argument("--frames-per-decision", type=int, default=8)
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    rom = rom_path()
    report = {
        "rom": str(rom),
        "rom_bytes": rom.stat().st_size if rom.is_file() else None,
        "env_id": "SuperMarioBros-1-1-v0",
        "frames_per_decision": args.frames_per_decision,
        "seed": args.seed,
        "substitutions": ["model HTTP hop (no TYPESAFE_API_KEY on this machine)"],
        "real": ["emulator", "ROM", "NES RAM", "parser", "runner", "policy", "SDK codec"],
    }
    print(f"ROM: {report['rom']} ({report['rom_bytes']} bytes)")

    for policy_name in ("heuristic", "typesafe"):
        summary, log_path = run(
            policy_name=policy_name,
            decisions=args.decisions,
            frames_per_decision=args.frames_per_decision,
            seed=args.seed,
        )
        report[policy_name] = summary
        print()
        print(f"=== {policy_name} on the real emulator ===")
        print(
            f"  decisions={summary['decisions']}  final_x={summary['final_x']}  "
            f"best_x={summary['best_x']}"
        )
        print(
            f"  outcome={summary['ended_reason']}  died={summary['died']}  "
            f"cleared={summary['cleared']}"
        )
        print(f"  actions={summary['actions']}")
        print(
            f"  jumped-when-required triggers={summary['jump_must_start_triggers']}  "
            f"gap-crossing decisions={summary['crossing_gap_frames']}"
        )
        print(f"  log={summary['log']}")

    (ARTIFACTS / "real_env_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    print()
    print(f"wrote {ARTIFACTS / 'real_env_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
