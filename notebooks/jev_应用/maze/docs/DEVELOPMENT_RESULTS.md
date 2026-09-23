# Development results: fixed maze and Snake pilot

The primary pipeline combines **atomic judgments + code planning**: focused model propositions, exploration memory, and code that composes actions. This page preserves the separate **whole-map direct-action stress test**. See [atomic training](ATOMIC_PLANNING.md) and [model-guided exploration](MODEL_EDGE_RESULTS.md) for the implemented local pipeline. Planner success and event calibration have separate measurements.

All six cases were selected before the new rollouts, with a shared **128-step limit** and identical initial states. See the [frozen protocol](../results/rollout_pilot_protocol.json), [machine-readable audit](../results/development_results_summary.json), and [environment/runbook](SCALED_GAMES.md). This is a bounded integration pilot, not a full-size completion benchmark or a population estimate.

## Systems and roles

| System | Role | Controller |
|---|---|---|
| Initial NanoJev | Existing NanoJev checkpoint before this game training; not untouched Qwen. | greedy |
| Game-target NanoJev | NanoJev trained on programmatic game-question targets. | greedy |
| API-target NanoJev | NanoJev trained on saved API-reference game-question targets. | greedy |
| Jev | Recorded Jev API decision controller. | greedy |
| Reference code | Maze: exact shortest-path actions. Snake: local collision-avoidance/food-progress rule, not global optimal play. | greedy |
| Uniform random | Uniform sampling over the offered action set. | sample |

Initial NanoJev is the earlier trained checkpoint, not raw untrained Qwen. The two game-training arms begin from that same checkpoint. Reference-code wins are due to its explicit algorithm; they are not credited to a learned judgment model. Uniform random samples; the other five systems use greedy actions. This pilot does not compare both controllers for every system.

## Maze: success / steps

A success is reaching the goal. Every failure remains in the table. The three exact shortest-path lengths are 16, 24, and 96, so all three are feasible within 128 moves.

| Case ID | Initial | Game targets | API targets | Jev | Reference | Random |
|---|---:|---:|---:|---:|---:|---:|
| `maze:test:8:23268921` | 0 / 128 | 0 / 128 | 0 / 128 | 0 / 128 | 1 / 16 | 0 / 128 |
| `maze:test:16:23276922` | 0 / 128 | 0 / 128 | 0 / 128 | 0 / 128 | 1 / 24 | 0 / 128 |
| `maze:ood:50:24310922` | 0 / 128 | 0 / 128 | 0 / 128 | 0 / 128 | 1 / 96 | 0 / 128 |

## Snake: food score / steps / outcome

Food score counts food eaten. Surviving to the time limit is distinct from filling the board, and is not a win. `wall` means wall collision; `body` means self-collision; `limit` means the snake remained alive at step 128.

| Case ID | Initial | Game targets | API targets | Jev | Reference | Random |
|---|---:|---:|---:|---:|---:|---:|
| `snake:test:8:23268920` | 1 / 7 / wall | 1 / 5 / wall | 0 / 9 / wall | 8 / 58 / body | 8 / 51 / body | 0 / 15 / wall |
| `snake:test:16:23276920` | 0 / 21 / wall | 1 / 35 / wall | 0 / 8 / wall | 6 / 128 / limit | 14 / 128 / limit | 0 / 15 / wall |
| `snake:ood:50:24310920` | 0 / 128 / limit | 0 / 128 / limit | 0 / 25 / wall | 0 / 128 / limit | 2 / 128 / limit | 0 / 128 / limit |

The learned direct-action models and Jev do not solve any of these three mazes within the shared 128-step limit. Local Snake behavior varies substantially, and no system fills a board. These results motivated the separate local-question training and code-exploration pipeline linked above.

## Independent question and probability measurements

[The probability report](../results/scaled_probability_summary.json) and [RLCD experiment](RLCD_EXPERIMENT.md) measure fixed question outputs separately from game trajectories. Atomic `clear_*`/`safe_*` truths, planning truth questions, action preferences, and stochastic events have different targets. Better one-step probability scores do not establish long-horizon game success.

| Game model | Split | Atomic truth accuracy | Always-true accuracy | Questions |
|---|---|---:|---:|---:|
| `games_gold_seed17` | test | 0.722397 | 0.722397 | 317 |
| `games_gold_seed17` | ood | 0.750000 | 0.750000 | 112 |
| `games_api_seed17` | test | 0.716088 | 0.722397 | 317 |
| `games_api_seed17` | ood | 0.750000 | 0.750000 | 112 |

The aggregate atomic accuracies of these full-map game-training arms do not exceed the fixed always-true control. The OOD Snake subset contains only true safety labels. The subsequent [local-maze experiment](ATOMIC_PLANNING.md) uses matching local training inputs and reports true/false cases separately from these full-map runs.

| Game model | Split | Atomic family | Accuracy | Always true | Questions |
|---|---|---|---:|---:|---:|
| `games_gold_seed17` | test | `scaled_maze` | 0.562500 | 0.562500 | 176 |
| `games_gold_seed17` | test | `snake_one_step_safety_v4` | 0.921986 | 0.921986 | 141 |
| `games_gold_seed17` | ood | `scaled_maze` | 0.562500 | 0.562500 | 64 |
| `games_gold_seed17` | ood | `snake_one_step_safety_v4` | 1.000000 | 1.000000 | 48 |
| `games_api_seed17` | test | `scaled_maze` | 0.573864 | 0.562500 | 176 |
| `games_api_seed17` | test | `snake_one_step_safety_v4` | 0.893617 | 0.921986 | 141 |
| `games_api_seed17` | ood | `scaled_maze` | 0.562500 | 0.562500 | 64 |
| `games_api_seed17` | ood | `snake_one_step_safety_v4` | 1.000000 | 1.000000 | 48 |

The small JSON audit retains confusion counts, separate planning-truth and action-support diagnostics; they are not pooled into atomic accuracy. Maze optimal-action mass and Snake local reference-action mass are separate metrics.

## Verification and reproduction

The local audit replays **36 episodes / 3201 transitions**, checks every saved before/after hash, final outcome, offered probability support, greedy choice, cohort identity, and horizon. Source-file hashes are retained. This does not rerun model inference, verify private API receipts, or reconstruct random draws absent from the compact artifacts.

```bash
python scripts/summarize_development_results.py
```

This command reads the frozen compact reports and rebuilds the small JSON audit and this document without API/GPU calls. Keep all six source reports and the preselected episode file unchanged.
