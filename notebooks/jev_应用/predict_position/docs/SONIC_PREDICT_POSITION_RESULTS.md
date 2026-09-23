# Mixed expert SFT: completed game evaluation

One shared NanoJev checkpoint now reaches **27/128 Predict Position test
successes**, up from **11/128** before this training round. Snake improves from
**6/8 to 8/8**, Basic remains **128/128**, and Maze remains **4/10**.
The matched [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
run scores 11/128 on Predict Position, 56/128 on Basic, 8/8 on Snake and 7/10 on
Maze. This round improves shooting and Snake; Maze remains the weaker task in
the comparison.

## Test results

Each cell is successful episodes / evaluated episodes.

| Model | Maze | Snake | Basic | Predict Position | Weighted success |
|---|---:|---:|---:|---:|---:|
| **NanoJev, mixed expert SFT** | **4/10** | **8/8** | **128/128** | **27/128** | **66.85%** |
| NanoJev, before this round | 4/10 | 6/8 | 128/128 | 11/128 | 56.43% |
| Jev | 7/10 | 8/8 | 56/128 | 11/128 | 65.39% |
| Untuned Qwen3-0.6B | 2/10 | 0/8 | 56/128 | 11/128 | 15.39% |

Predict Position success rises from 8.59% to **21.09%**. Against Jev, the selected
model wins 25 paired cases and loses 9; the two-sided exact McNemar p-value is
0.00904 before multiple-comparison adjustment. The per-model Wilson 95% intervals
are 14.92–28.95% for NanoJev and 4.87–14.73% for Jev.

## OOD results

| Model | Maze | Snake | Basic | Predict Position | Weighted success |
|---|---:|---:|---:|---:|---:|
| **NanoJev, mixed expert SFT** | **2/10** | **5/8** | **128/128** | **10/128** | **45.47%** |
| NanoJev, before this round | 2/10 | 4/8 | 126/128 | 9/128 | 40.91% |
| Jev | 3/10 | 6/8 | 59/128 | 8/128 | 43.72% |
| Untuned Qwen3-0.6B | 1/10 | 0/8 | 59/128 | 9/128 | 12.19% |

Predict Position OOD changes the action cadence from four to eight physical
ticks. NanoJev records 10/128 successes versus Jev's 8/128, with 10 paired wins,
8 losses and an exact p-value of 0.8145. Maze and OOD Snake remain below Jev in
this cohort. These are the main gaps for the next round.

## Data and selected model

- Collected **896 expert episodes / 17,498 decisions** with the released
  [Sonic Doom](https://github.com/thainv0212/sonic_doom) visual policy.
- Prepared **11,173 Predict Position questions** across five splits, including
  **6,788 training questions** from 512 training episodes. The other 384 expert
  episodes belong to dev, calibration, test and OOD.
- Preserved **7,587 Maze, Snake and Basic rows**, their exact bytes and original
  splits. Each hard/soft dataset contains **18,760 rows** in total.
- Trained four matched arms: hard/soft action targets × backbone learning rates
  1e-5/2e-5. All completed 600 optimizer updates with training seed 17.
- Selected **`hard_lr1e5`, checkpoint step 400**, using development data only.
  Its weighted development success is 80.31%, versus initialization's 69.64%.
- Retained the shared Qwen3-0.6B backbone and dynamic Choice head. All four tasks
  use the same checkpoint and complete-question cross entropy.

The 600-step sampler draws 2,400 Predict Position questions, covering 2,021
distinct questions. The selected step-400 checkpoint uses the corresponding
shorter prefix of that schedule. This is a fixed-update training comparison.

## Evaluation protocol and verification

All four primary systems play the same **548 frozen cases**: 274 test and 274
OOD. They receive the same structured observation interface, candidate actions,
environment rules and seeded epsilon-greedy controller (epsilon 0.1, seed 17).
The weighted score assigns Maze and Snake 1/3 each, Basic and Predict Position
1/6 each. Navigation uses its existing shared code planner. Shooting success
requires an actual kill before the episode deadline.

Untuned Qwen uses the original Qwen3-0.6B weights, official chat template and
native vocabulary head, with probabilities restricted to the offered A–D
answer tokens. It receives no project training.

All **2,192 primary episodes** pass independent simulator replay with zero
mismatches. The frozen case registry, actual model identities, seeded action
sampling and recorded physical counters also pass the result validator.
The [machine-readable report](../results/sonic_sft_v1_summary.json) contains
per-task intervals, paired case IDs, physical metrics and source hashes.

The visual expert is a separate reference: RGB frames, recurrent state and pure
greedy actions. It succeeds on 125/128 PP test and 61/128 PP OOD cases. The
64-case development controller diagnostic records 62/64 with pure greedy
actions and 44/64 with epsilon 0.1. The primary comparison above keeps its
predeclared common controller.

## Artifacts and reproduction

Local experiment artifacts are organized as follows:

| Artifact | Location |
|---|---|
| Expert episodes and collection manifest | `runs/sonic_unified_sft_v1/expert/` |
| Prepared hard/soft datasets and preparation audit | `data/sonic_supervision_v1/unified/` |
| Selected complete checkpoint bundle | `runs/sonic_unified_sft_v1/experiment/hard_lr1e5/` |
| Training, dev selection, test trajectories and replays | `runs/sonic_unified_sft_v1/experiment/` |
| Jev matched trajectories | `runs/sonic_unified_sft_v1/jev_parallel_recovery_v2/` |
| Untuned Qwen matched trajectories | `runs/sonic_unified_sft_v1/native_test.jsonl` |
| Full generated report | `runs/sonic_unified_sft_v1/final_results/` |

All four complete model bundles also have verified persistent server backups
under `/data/rwang/nanojev_sonic_sft_20260920/checkpoint_archives/`. The selected
bundle's 15 files pass local SHA256 verification. The current model and complete
mixed dataset are available through the public Hugging Face repositories
[NanoJev](https://huggingface.co/C-Tianyu/NanoJev) and
[NanoJev-Data](https://huggingface.co/datasets/C-Tianyu/NanoJev-Data),
version `unified-games-v1`. See the
[unified release contents and verification](UNIFIED_DEVELOPMENT_RELEASE.md).

Selected weights SHA256:
`f68c47d66998231b86b7e91b4ed5e82ae23acf104c8b7cd6d165c3ac7b7ffe1b`.

See [collection and training commands](SONIC_PREDICT_POSITION.md). To regenerate
the full report in a fresh output directory:

```bash
python scripts/summarize_sonic_supervision.py \
  --cases runs/sonic_unified_sft_v1/test_cases.jsonl \
  --experiment runs/sonic_unified_sft_v1/experiment \
  --jev runs/sonic_unified_sft_v1/jev_parallel_recovery_v2/episodes.jsonl \
  --native runs/sonic_unified_sft_v1/native_test.jsonl \
  --expert runs/sonic_unified_sft_v1/expert/episodes.jsonl \
  --expert-protocol configs/sonic_predict_supervision_v1.json \
  --output runs/sonic_unified_sft_v1/report_reproduction
```
