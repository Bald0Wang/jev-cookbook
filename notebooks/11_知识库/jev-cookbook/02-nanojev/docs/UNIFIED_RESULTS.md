# Unified Maze, Snake, and ViZDoom: first policy iteration

One shared Qwen3-0.6B checkpoint now completes the full cycle of policy SFT,
long-horizon outcome learning, Q-based game control, and fresh data collection
across Maze, Snake, and ViZDoom Basic / Predict Position.

With the same Q controller, the development-selected paired model changes
test task-macro success from **25.28% to 41.11%**
and OOD success from **9.72% to 25.28%**.
Its frozen-policy test vector Brier improves from **0.881312 to 0.122410**.
The task and scenario tables below show where those changes occur.

[Training commands and algorithm](UNIFIED_GAMES.md) ·
[All metrics, checkpoint hashes, and case results](../results/unified_games_v1.json) ·
[Frozen case definitions](../configs/unified_games_v1_cases.jsonl)

## Closed-loop game results

Every cell includes all episodes in that task and split. Test and OOD each
contain 10 Maze, 8 Snake, and 12 shooting episodes. Task-macro success is the
equal-weight mean of the three task success rates. This first experiment uses
training seed 17 and one rollout-seed setting.

### Test

| System | Maze | Snake | Shooting | Task-macro success |
| --- | --- | --- | --- | --- |
| Jev | 5/10 | 8/8 | 3/12 | 58.33% |
| Uniform random | 4/10 | 0/8 | 5/12 | 27.22% |
| SFT Choice | 4/10 | 4/8 | 4/12 | 41.11% |
| SFT Q (before) | 3/10 | 1/8 | 4/12 | 25.28% |
| Paired Q (after) | 4/10 | 6/8 | 1/12 | 41.11% |
| Direct Brier Q | 3/10 | 3/8 | 0/12 | 22.50% |
| CE Q | 3/10 | 3/8 | 1/12 | 25.28% |

### OOD

| System | Maze | Snake | Shooting | Task-macro success |
| --- | --- | --- | --- | --- |
| Jev | 3/10 | 5/8 | 3/12 | 39.17% |
| Uniform random | 1/10 | 0/8 | 4/12 | 14.44% |
| SFT Choice | 2/10 | 5/8 | 2/12 | 33.06% |
| SFT Q (before) | 0/10 | 1/8 | 2/12 | 9.72% |
| Paired Q (after) | 3/10 | 3/8 | 1/12 | 25.28% |
| Direct Brier Q | 1/10 | 1/8 | 1/12 | 10.28% |
| CE Q | 2/10 | 0/8 | 1/12 | 9.44% |

The paired model's test gain over SFT Q comes mainly from Snake (1/8 to 6/8),
while shooting falls from 4/12 to 1/12. Compared with SFT Choice, its overall
test score is equal and its OOD score is lower. The 50×50 deadline-limited
mazes and Predict Position remain the main unsolved scenarios in this cohort.

All Q systems use the same action-conditioned Boolean questions and select the
largest predicted success probability with **15% uniform exploration**. The
SFT Q baseline uses the same SFT checkpoint before outcome training. SFT Choice
selects the largest Choice probability with 15% exploration;
[Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) uses Choice
with 10% exploration. These settings are included in the machine-readable report.
SFT Choice is evaluated on the fixed 90-case dev/test/OOD subset; the other
listed systems complete all 228 cases.

### Test by scenario

| Variant | Jev | SFT Q | Paired Q | Direct Brier Q | CE Q |
| --- | --- | --- | --- | --- | --- |
| maze8 | 5/6 | 3/6 | 4/6 | 3/6 | 3/6 |
| maze16 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| maze50 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| snake8 | 6/6 | 1/6 | 5/6 | 3/6 | 3/6 |
| snake12 | 2/2 | 0/2 | 1/2 | 0/2 | 0/2 |
| doom_basic | 3/6 | 4/6 | 1/6 | 0/6 | 1/6 |
| doom_predict_position | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 |

### OOD by scenario

| Variant | Jev | SFT Q | Paired Q | Direct Brier Q | CE Q |
| --- | --- | --- | --- | --- | --- |
| maze8 | 2/6 | 0/6 | 3/6 | 1/6 | 2/6 |
| maze16 | 1/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| maze50 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| snake8 | 4/6 | 1/6 | 3/6 | 1/6 | 0/6 |
| snake12 | 1/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| doom_basic | 3/6 | 1/6 | 1/6 | 1/6 | 1/6 |
| doom_predict_position | 0/6 | 1/6 | 0/6 | 0/6 | 0/6 |

## Environment and data

The cohort contains **228 distinct environment groups**: 108 train and 30 each
in dev, calibration, test, and OOD. Each group stays within one split.

| Variant | Test contract | OOD contract |
| --- | --- | --- |
| maze8 | 8×8 tree, 32 physical attempts | 16×16 tree, 160 attempts |
| maze16 | 16×16 tree, 160 attempts | 16×16 tree, 160 attempts |
| maze50 | 50×50 corridor, 800 attempts | 50×50 corridor, 800 attempts |
| snake8 | 8×8, collect 2 food, 96 attempts | 10×10, collect 3 food, 160 attempts |
| snake12 | 12×12, collect 3 food, 160 attempts | 12×12, collect 3 food, 160 attempts |
| doom_basic | Up to 75 decisions × 4 ticks | Up to 38 decisions × 8 ticks |
| doom_predict_position | Up to 75 decisions × 4 ticks | Up to 38 decisions × 8 ticks |

Maze exposes a 5×5 local window and the complete observed edge graph. Code can
reposition through already traversed open edges, charging every physical move
to the deadline. All maze goals are reachable within the stated deadlines;
the twelve 50×50 shortest paths require 446–690 attempts. The current cases,
800-attempt deadline, and controller differ from the earlier website showcase.

Snake exposes its current body and food. ViZDoom uses visible object labels,
player health/ammo/pose, and recent observations; its native timeout can end an
episode before the configured decision limit. Shooting success requires a
kill-count increase. The shared model currently consumes structured state text.

| Stage | Completed collection |
| --- | --- |
| Initial policy data | 228 episodes; 16,637 decision transitions, including 2,134 forced actions |
| Policy training set across splits | 4,346 stored questions; 23 excluded from loss for unusable targets |
| Frozen SFT behavior data | 228 episodes; 16,449 outcome questions |
| First outcome dataset | 20,795 records including policy retention |
| New paired-controller behavior data | 228 episodes; 17,969 outcome questions |
| Next iteration dataset | 22,315 records including policy retention; validated |

Outcome datasets retain every recorded decision transition, including forced
singleton actions. The actual final success is assigned only to the action
that was executed. Internal Maze reposition movements remain in physical-move
logs rather than becoming separate model questions. Train, dev, calibration,
test, and OOD files remain separate throughout.

## Long-horizon probability learning

For an observation/history, an offered action, and the remaining deadline,
the Boolean predictor estimates eventual success after taking that action and
then following the frozen SFT sampling policy. Each action gets an independent
probability; the values need not sum to one. The outcome benchmark evaluates
those predictions on completed episodes from that same frozen policy.

| Predictor | Test NLL | Test vector Brier | OOD NLL | OOD vector Brier |
| --- | --- | --- | --- | --- |
| SFT before outcome training | 1.148377 | 0.881312 | 1.064681 | 0.819541 |
| Paired Brier PG, M=32 | 0.224576 | 0.122410 | 0.834155 | 0.407323 |
| Direct Brier | 0.174095 | 0.089576 | 0.839846 | 0.487428 |
| Observed CE | 0.195647 | 0.115958 | 1.374576 | 0.555119 |
| Train-only task prior | 0.410367 | 0.252160 | 0.462562 | 0.297264 |

NLL uses natural logarithms. Binary vector Brier is `2 * (p_true - outcome)^2`;
both scores are averaged within each task, then equally across tasks. Test has
2,448 outcome questions and OOD 3,061. The constant prior uses train-only
positive-question fractions for each task. No temperature is fitted.

All three trained predictors improve over the task prior on test. The prior
remains stronger on OOD. Direct Brier has the lowest test prediction error;
paired remains the primary model selected using development CE before test
scores and fresh-controller outcomes were inspected. Predictions for the old
continuation policy and actual success under the new controller are evaluated
separately.

## Training and the next iteration

Training starts from the existing `games_api_seed17` NanoJev checkpoint.
Policy SFT performs 200 base updates followed by 100 full-curriculum updates.
Each of the three outcome-learning arms starts from the same selected SFT
weights and runs 200 updates with identical sampled questions, seed, optimizer
settings, and **25% policy-retention weight**. Each arm is one shared model
across all tasks. Checkpoint selection compares updates 0 and 200 using
task/role-weighted development CE.

The RLCD-inspired `paired_brier_pg` objective uses 32 independent predictive
category samples to estimate a proper Brier-reward gradient. Direct Brier
optimizes the same expected objective without that sampling; CE is the third
control. The predictor update is followed by an explicit Q-controller change
and real game evaluation. This implementation is specified in the linked
runbook and [objective document](RLCD_EXPERIMENT.md).

The selected new controller has now collected a complete new cohort.
`outcomes_v2` stores its own continuation-policy identity and retains the policy
SFT examples. The subsequent round has now completed eight MC/TD training arms
and their game evaluations; see the [multi-step TD results](UNIFIED_TD_RESULTS.md).

Validation includes 97 passing remote unit tests, a tiny-data fitting check,
exactly matched training samples across the three controls, and independent
replay of all **684 new Q-controller episodes / 54,449 decisions with zero
differences**. All 17,969 next-iteration outcome questions match their actual
executed actions and terminal outcomes one-to-one. Episode-level counts,
Wilson intervals, split identities, source hashes, and checkpoint hashes are
included in the machine-readable results.
