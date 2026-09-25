# Multi-step TD for the unified game model

This experiment compares complete-episode Monte Carlo (MC) learning with
multi-step temporal-difference (TD) learning for one shared Maze, Snake, and
ViZDoom success-probability model. The input representation, network, candidate
actions, environment cases, and policy-retention objective remain fixed.

[Predeclared experiment](../configs/unified_td_v1.json) ·
[Completed results](UNIFIED_TD_RESULTS.md) ·
[First policy iteration](UNIFIED_RESULTS.md) ·
[Environment and collection commands](UNIFIED_GAMES.md)

## Prediction target

The first iteration produced a frozen Q controller, `pi_1`, and 228 complete
episodes. Its action selection includes 15% uniform exploration. The new
training set contains 17,969 outcome questions plus 4,346 retained policy
questions, separated into train, dev, calibration, test, and OOD files.

For observation/history `h`, executed action `a`, and remaining task budget,
the model learns:

```text
Q_pi_1(h, a) = P(success before the deadline | h, take a, then follow pi_1)
```

The continuation policy is fixed throughout each training run. Its probabilities
come from the recorded `behavior_probs`; they are not recomputed by greedily
selecting with the changing online critic. The previous iteration's checkpoint
provides the initialization. Its predictions initially describe the older
continuation policy, so the new data determines the updated prediction task.

## Multi-step target

At a recorded decision `t`, look ahead by `n` decision transitions, stopping at
the real episode terminal boundary:

```text
y_td = 1                                      if success occurs within n decisions
       0                                      if failure occurs within n decisions
       sum_a pi_1(a | h[t+n]) Q_target(h[t+n],a) otherwise
```

The discount is **gamma=1**. The task deadline is part of the state and defines
a genuine terminal failure. External collection truncation is rejected. Success
is counted once, and terminal states are never bootstrapped. Internal Maze
reposition moves consume the physical deadline but do not become extra model
decisions; forced singleton decisions do count as transitions.

The target network starts as a copy of the online model. It stays in evaluation
mode without gradients, and copies the online parameters after each 25 completed
optimizer updates. Target predictions are recomputed after those updates. Each
offered action receives its own Boolean success question; weighted probabilities
use the frozen behavior distribution, including its exploration component.

The TD branch uses a detached floating-point target and direct binary vector
Brier, `2 * (Q - y_td)^2`. The MC branch uses the actual terminal Boolean result,
`2 * (Q - Y)^2`. Training combines them as:

```text
L = 0.25 * policy_CE
    + 0.75 * ((1 - td_weight) * MC_Brier + td_weight * TD_Brier)
```

Tasks receive equal population weight. MC already labels every recorded action
with the terminal result; TD adds an estimate based on subsequent observations.
It changes the bias/variance trade-off and introduces bootstrap error. The
current structured observations contain compressed history, so empirical
evaluation also tests how well they support this temporal consistency relation.

## Fixed comparisons

| Condition | Lookahead | TD fraction of outcome loss | Training seeds |
| --- | --- | --- | --- |
| `mc` | No bootstrap | 0 | 17, 29 |
| `mix_n3` | 3 decisions | 0.5 | 17, 29 |
| `mix_n8` | 8 decisions | 0.5 | 17, 29 |
| `td_n8` | 8 decisions | 1 | 17, 29 |

The primary comparison is **`mix_n3` versus `mc`**, fixed before training.
The other conditions test lookahead and the contribution of real terminal
supervision. All eight arms start from the same checkpoint and use 200 optimizer
updates, 24 questions per update, online microbatches of at most eight questions and
32,768 path tokens, 8,192 tokens per path, BF16 forward passes, and gradient
checkpointing. Backbone/head learning rates are 2e-5/2e-4. AdamW weight decay is
0.01. The selected checkpoint minimizes task/role-weighted development CE at
updates 0, 100, and 200, evaluated against actual outcomes.

This is a comparison with equal online sample counts and optimizer updates.
TD uses target microbatches of at most four questions. It incurs additional
target-network forward passes; execution time and target
inference counts are reported separately.

## Evaluation

Each selected checkpoint runs the same 228 cases with `q_greedy`, 15% uniform
exploration, and rollout seed 17. Compare each TD arm against MC with the same
training seed. Report Maze, Snake, Basic, Predict Position, and map-size results
as well as the equal-task aggregate. Two training seeds provide an initial
replication and a range of results, rather than a precise uncertainty estimate.

Probability evaluation uses actual final outcomes from held-out `pi_1`
episodes. Bootstrap targets and TD residuals are optimization diagnostics;
they do not replace held-out NLL, vector Brier, or real game success. The
calibration split remains separate and no temperature is fitted.

Older-policy outcome labels are not mixed into the new outcome target.
The retained action-distribution examples keep their separate policy role.
Episode manifests, checkpoint hashes, sampled-question hashes, target-network
refreshes, and trajectory-to-target checks make each comparison reproducible.

## Commands

Use the previous cycle's complete paired checkpoint as
`checkpoints/paired_iteration1`. Place its episode collection and the verified
`outcomes_v2` dataset at the locations in the experiment JSON, including the
episode manifest and source snapshot. Model packages are complete local
DecisionModel bundles with weights, config, tokenizer, and backbone config.

```bash
python scripts/train_unified_games.py \
  --input data/unified_v2/outcomes_v2 --stage critic --loss brier \
  --td-episodes data/unified_v2/remote/q_paired_brier_pg_v1_episodes.jsonl \
  --td-n-step 3 --td-weight 0.5 --validate-only

CUDA_VISIBLE_DEVICES=0 python scripts/train_unified_games.py \
  --input data/unified_v2/outcomes_v2 \
  --init-checkpoint checkpoints/paired_iteration1 \
  --output-dir runs/unified_td_v1/mix_n3_seed17 \
  --stage critic --loss brier --steps 200 --eval-every 100 --seed 17 \
  --td-episodes data/unified_v2/remote/q_paired_brier_pg_v1_episodes.jsonl \
  --td-n-step 3 --td-weight 0.5 --target-update-every 25 \
  --batch-questions 24 --microbatch-questions 8 \
  --max-microbatch-tokens 32768 --max-length 8192 \
  --backbone-lr 2e-5 --head-lr 2e-4 --weight-decay 0.01 \
  --balance task --retention-fraction 0.25 \
  --precision bf16 --gradient-checkpointing --disable-native-triton

CUDA_VISIBLE_DEVICES=0 python scripts/unified_game_pipeline.py rollout \
  --cases configs/unified_games_v1_cases.jsonl --engine checkpoint \
  --checkpoint runs/unified_td_v1/mix_n3_seed17 \
  --controller q_greedy --epsilon 0.15 --seed 17 \
  --env-batch 16 --batch-questions 16 --max-length 8192 \
  --output data/unified_td_v1/q_mix_n3_seed17.jsonl

python scripts/replay_unified_episodes.py \
  --episodes data/unified_td_v1/q_mix_n3_seed17.jsonl \
  --output data/unified_td_v1/q_mix_n3_seed17_replay.json
```

Repeat the declared conditions/seeds using distinct output paths. For the MC
control, set `--td-weight 0`; it validates the same episodes but creates no
target network and performs no bootstrap inference. After all arms finish:

```bash
python scripts/summarize_unified_td.py \
  --experiment configs/unified_td_v1.json \
  --baseline 'Initial Q=data/unified_v2/remote/q_paired_brier_pg_v1_episodes.jsonl' \
  --output-dir runs/unified_td_v1_reproduced
```
