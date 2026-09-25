# Unified MC versus multi-step TD: completed results

Eight-step TD mixed with actual terminal outcomes is the strongest follow-up candidate in this pilot: mean test game success reaches **57.22%**, compared with **45.97%** for MC. The predeclared three-step mixture reaches **46.25%** on test and falls from MC's **17.22% to 12.08%** on OOD. The TD bootstrap horizon and retaining real terminal supervision materially affect the result.

[Method and commands](UNIFIED_TD.md) · [Frozen protocol](../configs/unified_td_v1.json) · [Complete tables](../results/unified_td_v1/summary.md) · [Machine-readable results](../results/unified_td_v1/summary.json)

All eight arms completed 200 updates. Each selected checkpoint played the same 228 cases, giving **1,824 new episodes** across Maze, Snake, ViZDoom Basic, and Predict Position. Seeds 17 and 29 share the frozen dataset and rollout seed 17. Each arm is one shared Qwen3-0.6B model across all tasks.

## Game success

Values are the mean of two training seeds. Within each seed, task-macro success equally weights Maze, Snake, and shooting. Test and OOD each contain 10 Maze, 8 Snake, and 12 shooting cases. Every controller uses the same Q-based action selection with 15% uniform exploration.

| Condition | Test success | OOD success |
| --- | --- | --- |
| Initial Q (before this round) | 41.11% | 25.28% |
| MC | 45.97% | 17.22% |
| MC + 3-step TD (primary) | 46.25% | 12.08% |
| MC + 8-step TD (secondary) | 57.22% | 20.28% |
| 8-step TD only (secondary) | 41.67% | 13.75% |

Eight-step mixing gains **11.25 percentage points on test** and **3.06 points on OOD** relative to MC. Both seeds improve over their matched MC run. The condition was a registered secondary comparison; the result motivates a fresh replication. Its OOD mean remains below the initial controller's 25.28%.

### Predeclared primary comparison

| Split | Training seed | MC | MC + 3-step TD | Difference (points) |
| --- | --- | --- | --- | --- |
| test | 17 | 45.28% | 45.28% | +0.00 |
| test | 29 | 46.67% | 47.22% | +0.56 |
| ood | 17 | 15.28% | 11.67% | -3.61 |
| ood | 29 | 19.17% | 12.50% | -6.67 |

### Success counts by game and seed

Each cell is **Maze / Snake / shooting**, with denominators 10 / 8 / 12 respectively.

| Arm | Test: Maze · Snake · shooting | OOD: Maze · Snake · shooting |
| --- | --- | --- |
| mc_seed17 | 4/10 · 5/8 · 4/12 | 0/10 · 3/8 · 1/12 |
| mix_n3_seed17 | 4/10 · 7/8 · 1/12 | 1/10 · 2/8 · 0/12 |
| mix_n8_seed17 | 5/10 · 7/8 · 2/12 | 0/10 · 5/8 · 0/12 |
| td_n8_seed17 | 5/10 · 4/8 · 0/12 | 0/10 · 1/8 · 0/12 |
| mc_seed29 | 4/10 · 8/8 · 0/12 | 2/10 · 3/8 · 0/12 |
| mix_n3_seed29 | 5/10 · 6/8 · 2/12 | 0/10 · 3/8 · 0/12 |
| mix_n8_seed29 | 6/10 · 7/8 · 5/12 | 3/10 · 1/8 · 2/12 |
| td_n8_seed29 | 5/10 · 8/8 · 0/12 | 2/10 · 4/8 · 0/12 |

The 50×50 cases remain unsolved by every arm across all splits. Predict Position has isolated successes: `mix_n3_seed17` reaches 1/6 on test and `mc_seed17` reaches 1/6 on OOD. The eight-step mixed arms score 0/6 on Predict Position in both held-out splits; their shooting gains come from Basic. All scenario counts, including zero-success cells, appear in the complete tables.

## Fixed-policy probability prediction

These scores evaluate real terminal outcomes under the frozen continuation policy `pi_1`. They measure a different task from playing with the newly improved controller. NLL uses natural logarithms; vector Brier is `2 * (p_true - Y)^2`. Both are averaged within each task and then equally across tasks. Lower is better.

| Predictor | Test NLL | Test Brier | OOD NLL | OOD Brier |
| --- | --- | --- | --- | --- |
| Initial checkpoint | 0.743727 | 0.293627 | 0.437741 | 0.230235 |
| MC | 0.506496 | 0.253664 | 0.468760 | 0.249597 |
| MC + 3-step TD (primary) | 0.475428 | 0.271979 | 0.401192 | 0.214354 |
| MC + 8-step TD (secondary) | 0.456366 | 0.254180 | 0.445203 | 0.225507 |
| 8-step TD only (secondary) | 0.431571 | 0.236236 | 0.353625 | 0.205887 |
| Train-only task prior | 0.341398 | 0.200049 | 0.571536 | 0.400776 |

Three-step mixing improves OOD Brier from **0.249597 to 0.214354**, while OOD game success falls. Pure eight-step TD has the lowest mean NLL/Brier among the trained conditions, but a lower mean game score than MC. Good prediction scores alone do not select the strongest game controller.

The constant task-prior reference has the lowest test NLL and Brier in this table. It uses only training outcome frequencies: Maze 0.120221, Snake 0.788945, and shooting 0.067639. Outcome proportions differ across tasks and splits; the frozen development shooting set contains 0 successful episodes out of 12. These distributions are preserved in the [prior reference](../results/unified_td_v1/task_prior_baseline.json).

Test contains 2,716 outcome questions and OOD 3,107. Questions from one episode are correlated, and longer episodes contribute more questions. These `pi_1` scores use a new dataset and must be kept separate from the first iteration's `pi_0` outcome scores.

## Training and cost

The predictor learns deadline-success probability with gamma=1. Multi-step targets use the recorded frozen behavior probabilities and a detached target network, refreshed every 25 updates. Outcome loss mixes observed MC Brier with soft-target TD Brier; 25% policy CE is retained. The TD mixture weight is 0.5 in both mixed conditions and 1 in the pure-TD condition. This experiment tests TD targets using direct Brier optimization; the earlier paired proper-reward objective is documented separately.

Every arm uses 4,800 online question instances, including 3,600 outcome and 1,200 retained policy questions. For a given seed, all four arms use exactly the same 200 sampled batches. Checkpoints minimize task-balanced development CE with 25% policy and 75% observed-outcome weight at updates 0, 100, and 200.

| Arm | Selected update | Training minutes | Peak GB | Online padded tokens | Target forwards | Target padded tokens | Target seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mc_seed17 | 100 | 21.67 | 16.80 | 13373928 | 0 | 0 | 0.0 |
| mix_n3_seed17 | 100 | 25.23 | 19.19 | 13373928 | 2581 | 10953589 | 212.6 |
| mix_n8_seed17 | 100 | 24.91 | 19.19 | 13373928 | 2165 | 9823890 | 192.2 |
| td_n8_seed17 | 200 | 25.06 | 19.19 | 13373928 | 2165 | 9823890 | 191.7 |
| mc_seed29 | 100 | 21.97 | 16.82 | 13614323 | 0 | 0 | 0.0 |
| mix_n3_seed29 | 100 | 25.52 | 19.21 | 13614323 | 2595 | 11107257 | 215.0 |
| mix_n8_seed29 | 100 | 25.08 | 19.21 | 13614323 | 2167 | 9772651 | 189.8 |
| td_n8_seed29 | 200 | 25.22 | 19.21 | 13614323 | 2167 | 9772651 | 190.4 |

All arms completed 200 updates regardless of the selected checkpoint. Training time includes the training loop and its development evaluations; initialization, cache preparation, and final held-out evaluation are outside that timer. Target inference is additional computation. The successful runs used seven A100 80GB GPUs with the eighth arm queued. An earlier storage-blocked attempt was restarted in full from identical initialization; none of its incomplete results enter these tables. This round made **zero API calls**.

## Validation and next iteration

All **152 unit tests** passed on the remote environment. A real-model smoke test verified backbone/head updates, detached target predictions, and exact hard target copies. The independent [training audit](../results/unified_td_v1/training_audit.json) verified every same-seed batch, the target refresh schedule, development selection, and held-out metrics against observed outcomes. The summarizer rehashed all selected weights and bound each rollout to the exact checkpoint and configuration.

Independent simulator replay verified all **1,824 episodes and 142,944 executed decisions with zero mismatches**. The [replay summary](../results/unified_td_v1/replay_summary.json) retains each report hash, episode hash, and matching collection/replay implementation hashes.

A [local reproduction](../results/unified_td_v1/local_reproduction.json) from downloaded predictions and episodes matches all eight arms' metrics and every game result under the unchanged protocol.

Keep the current default model while testing the eight-step mixture on fresh environment groups and fresh outcomes from its own frozen controller. Retain MC and the initial controller as controls, and expand successful Predict Position and large-maze experience. The next comparison should be registered before inspecting its new test outcomes. The two seeds here provide a pilot comparison, not a precision estimate across datasets or rollout randomness.
