# Unified supervised training with Predict Position experts

This pipeline adds moving-target shooting demonstrations to the existing unified
Maze, Snake and Basic decision model. One Qwen3-0.6B backbone and dynamic candidate
scoring head answer all four decision pools. Each candidate receives a score;
softmax over the offered candidates gives the action distribution.

[Completed results, selected checkpoint and reproduction](SONIC_PREDICT_POSITION_RESULTS.md)
cover the full 548-case comparison against the previous NanoJev model, Jev and
untuned Qwen.

The visual expert is the ordinary no-sound Predict Position policy released by
[Sonic Doom](https://github.com/thainv0212/sonic_doom). Its CNN and recurrent GRU
receive RGB frames. Sound, Auto Aim and Sonic Aim assistance are disabled.

## Expert collection

The collector runs two synchronized ViZDoom 1.3.0 instances. The expert sees its
validated 160x120 rendering with the Freedoom materials shipped in ViZDoom 1.2.4.
The student receives the existing 320x240 structured visible-state observation
with the current materials. Both instances use the same scenario, random seed,
buttons, reward and termination rules. Every physical tick must match, and every
completed episode is replayed independently in the standard student environment.

The expert adapter strictly validates its checkpoint, configuration and tensor
shapes. It records real action logits, the complete four-action probability
distribution, recurrent-state hashes, executed actions and terminal outcomes.
The student's model input contains its public state, question and candidates.

The frozen cohort contains 896 episodes:

| Split | Episodes | Ticks per decision | Visible history |
| --- | ---: | ---: | ---: |
| Train | 512 | 4 | Up to 4 observations |
| Dev | 64 | 4 | Up to 4 observations |
| Calibration | 64 | 4 | Up to 4 observations |
| Test | 128 | 4 | Up to 4 observations |
| OOD | 128 | 8 | Up to 4 observations |

Collection completed with **17,498 recorded decisions**. Preparation retains
**11,173 Predict Position questions**, including **6,788 training questions**,
and preserves **7,587 existing Maze, Snake and Basic rows** byte for byte across
the five splits. Each hard/soft dataset contains 18,760 rows. The policy trainer
uses 10,893 training questions that pass the existing target-validity filter.

Splits use distinct scenario/seed groups. The OOD split changes decision cadence;
the teacher advances its GRU once per eight-tick decision. Full traces retain
failures and states after firing. For supervised Predict Position rows, preparation
keeps observations with positive ammunition before the action. The firing action
itself remains included. This focuses supervision on decisions that can affect the
single rocket's trajectory; closed-loop evaluation still runs the full episode.

```bash
python scripts/sonic_predict_data.py \
  --cases configs/sonic_predict_supervision_v1_cases.jsonl \
  --config configs/sonic_predict_supervision_v1.json \
  --checkpoint /path/to/sonic/best_000097758_400416768_reward_0.920.pth \
  --expert-config /path/to/sonic/config.json \
  --old-game-wad /path/to/freedoom2_vizdoom_1.2.4.wad \
  --output /path/to/new/expert --workers 8 --device cpu

python scripts/prepare_sonic_supervision.py \
  --original data/appo_basic_supervision_v1/unified/hard \
  --expert /path/to/new/expert \
  --protocol configs/sonic_predict_supervision_v1.json \
  --output /path/to/new/unified
```

## Mixed supervision

Preparation preserves every existing Maze, Snake and Basic row, its original
split and its exact serialized bytes. Only Predict Position rows are replaced.
Two datasets differ only in the new Predict Position target:

- **Hard:** the expert's highest-probability action.
- **Soft:** its complete normalized action distribution.

Both use categorical cross entropy, `-sum_a target(a) log policy(a)`. Every update
contains all four pools, with exact loss weights independent of corpus size:

| Pool | Loss weight |
| --- | ---: |
| Maze | 1/3 |
| Snake | 1/3 |
| Basic | 1/6 |
| Predict Position | 1/6 |

Training starts from the existing Basic-supervised unified checkpoint, whose
SHA256 is `38116340795de1c82369b7fe15819d92d79600a7b4dc7a3cd0d4390cb6782639`.
The four declared arms compare hard/soft Predict Position targets and backbone
learning rates of 2e-5/1e-5, each with a head learning rate ten times larger.
Each arm uses 600 updates, 24 questions per update, BF16 forward computation and
gradient checkpointing. The complete settings are in
[`sonic_unified_sft_v1.json`](../configs/sonic_unified_sft_v1.json).

The deterministic seed-17 schedule presents 2,400 Predict Position training
questions across 600 updates, covering 2,021 distinct questions from 453 training
episodes. This is a fixed-budget comparison. All four arms receive the same
sample sequence, so target type and learning rate are compared on matched data.

## Model selection and comparison

Within each arm, the existing trainer chooses the checkpoint with the lowest
weighted development cross entropy. The next stage evaluates those checkpoints
and the unchanged initialization on 146 development episodes, selecting by
weighted episode success. The selection file is written before closed-loop test
evaluation. The best newly trained arm is also retained if initialization wins.

The final cohort has 548 episodes: 20 Maze, 16 Snake, 256 Basic and 256 Predict
Position, covering test and OOD splits. NanoJev, Jev and untuned Qwen use the same
case specifications, observation interface, questions, candidate actions,
epsilon-greedy controller (epsilon 0.1) and sampling seed. Untuned Qwen uses its
original vocabulary head and the official chat template; no project decision head
or language generation is added to that baseline. Jev is described in its
[System One model introduction](https://typesafe.ai/blog/introducing-system-one-models-and-jev).

Reports separate test from OOD and show results for each task. Shooting success
requires an actual KILLCOUNT increase before the deadline. Expert action agreement
and cross entropy describe policy matching; episode success describes gameplay.

```bash
python scripts/run_sonic_supervision.py \
  --protocol configs/sonic_unified_sft_v1.json \
  --expert-protocol configs/sonic_predict_supervision_v1.json \
  --datasets /path/to/new/unified \
  --init-checkpoint /path/to/current/nanojev \
  --dev-cases /path/to/frozen/dev_cases.jsonl \
  --test-cases /path/to/frozen/test_cases.jsonl \
  --output /path/to/new/experiment \
  --gpus 0,1,2,3 --baseline-gpu 4
```

The scripts produce complete trajectories, source hashes, data-preparation audits,
training logs, checkpoint bundles and model-selection records. The code
does not upload checkpoints or publish a website.

## Development controller diagnostic

On the same 64 development cases, the visual expert succeeds in 62/64 episodes
with pure greedy actions and 44/64 with epsilon-greedy exploration at epsilon 0.1.
The diagnostic uses the benchmark's case-specific seed-17 random stream. Sixteen
episodes first issue `shoot` as a non-argmax exploratory action; fourteen of those
fail, accounting for fourteen of the eighteen additional failures.

All 64 mirrored trajectories and independent standard-environment replays pass.
This diagnostic runs on CPU through `scripts/evaluate_sonic_dev_epsilon.py`.
It compares controllers on the same visual expert; primary model comparisons
retain their predeclared common controller and structured observation interface.
