# APPO Basic versus Jev

All three public APPO checkpoints completed **48/48 ViZDoom Basic cases** when their original training rendering was restored. Each scored **6/6 on test and 6/6 on OOD**, compared with Jev's **3/6 on each split**. These checkpoints are practical candidates for generating Basic action demonstrations.

The rendering configuration was decisive in this experiment. The initial benchmark used NanoJev's existing framebuffer settings. We then checked the checkpoint's original source, restored its training rendering, verified all three policies on development cases, and ran the complete fixed case set. Both rounds are retained below.

## Results with the training rendering

All controllers in this table use greedy selection with 10% uniform exploration and sampling seed 17. Test repeats each action for up to four ticks; OOD repeats for up to eight. Native termination remains enabled. A successful episode has a positive kill-count increment.

| Controller | Train | Dev | Calibration | Test | OOD |
|---|---:|---:|---:|---:|---:|
| Jev | 10/24 | 3/6 | 4/6 | 3/6 | 3/6 |
| APPO 1111 | 24/24 | 6/6 | 6/6 | **6/6** | **6/6** |
| APPO 2222 | 24/24 | 6/6 | 6/6 | **6/6** | **6/6** |
| APPO 3333 | 24/24 | 6/6 | 6/6 | **6/6** | **6/6** |

| Controller | Test mean ticks | OOD mean ticks | Test mean ammo consumed | OOD mean ammo consumed |
|---|---:|---:|---:|---:|
| Jev | 167.33 | 235.67 | 12.00 | 16.67 |
| APPO 1111 | 21.50 | 25.00 | 1.17 | 1.00 |
| APPO 2222 | 17.67 | 25.00 | 1.00 | 1.00 |
| APPO 3333 | 17.67 | 37.00 | 1.00 | 1.50 |

These are means over every episode, including Jev's failures. They measure game time, not inference latency. Each split has six environment cases, reused across the three checkpoints; the three models do not create eighteen independent test scenarios.

The map, case seeds, buttons, action durations, and success criterion are shared. APPO consumes RGB frames with recurrent memory; Jev consumes structured visible-object boxes, player variables, and observation history. This is a comparison of complete controllers with their respective input representations. Predict Position is not covered by these Basic checkpoints.

Machine-readable results: [training-rendering follow-up](../results/appo_basic_v1/native_rendering_summary.json).

## Initial benchmark with the existing rendering

The [protocol](../configs/appo_basic_v1.json) fixed checkpoint 1111 with greedy selection and epsilon 0.1 as the primary comparison before APPO outcomes were inspected. Its initial test result tied Jev, and its OOD result was lower. All nine planned runs completed.

| APPO checkpoint and controller | Test | OOD |
|---|---:|---:|
| 1111 greedy, epsilon 0.1 — primary | 3/6 | 1/6 |
| 1111 greedy, epsilon 0 | 3/6 | 0/6 |
| 1111 sampled | 2/6 | 1/6 |
| 2222 greedy, epsilon 0.1 | 4/6 | 3/6 |
| 2222 greedy, epsilon 0 | 4/6 | 3/6 |
| 2222 sampled | 4/6 | 3/6 |
| 3333 greedy, epsilon 0.1 | 5/6 | 3/6 |
| 3333 greedy, epsilon 0 | 5/6 | 3/6 |
| 3333 sampled | 5/6 | 5/6 |

[Complete initial results](../results/appo_basic_v1/summary.md) include every split, metric, source hash, and paired case comparison. The training-rendering follow-up is recorded separately as an exploratory evaluation, retaining checkpoint 1111 and all secondary checkpoints.

## Rendering and model checks

| Setting | Initial benchmark | Training-rendering follow-up |
|---|---|---|
| Native framebuffer | 320×240 | 160×120 |
| HUD | Off | On |
| Decals and particles | On | Off |
| Network input | 128×72 RGB, CHW | 128×72 RGB, CHW |
| Resize | Nearest neighbor | Nearest neighbor |

Restoring these settings improved development success from 3/6, 4/6, and 4/6 to 6/6 for all three checkpoints. This tests the settings together; it does not isolate the contribution of HUD, resolution, or effects individually. The Basic WAD is byte-identical between the public training source and the installed ViZDoom scenario.

The APPO policy has **3,396,837 parameters**, a CNN encoder, and a 512-unit LSTM. Evaluation strictly loads all 22 model-state tensors, including the saved input normalization statistics. Packed recurrent state contains 1,024 values for the hidden and cell states and resets at every episode. Inference preserves every parameter and normalization buffer.

Public checkpoints:

- [edbeeching/doom_basic_1111](https://huggingface.co/edbeeching/doom_basic_1111), revision `fae3bfcd5ab5f98804fe4327a0be982776c8d7d3`.
- [edbeeching/doom_basic_2222](https://huggingface.co/edbeeching/doom_basic_2222), revision `459b453cce290edeb946d1f4c755dbed974cf00b`.
- [edbeeching/doom_basic_3333](https://huggingface.co/edbeeching/doom_basic_3333), revision `599f9aae7083798b207bfe05a9d0517c1da6de3c`.

The runtime uses their [original Sample Factory source](https://github.com/alex-petrenko/sample-factory/tree/9da68b57eecd73c3c884c1be2d938b46aa7a7f49), commit `9da68b57eecd73c3c884c1be2d938b46aa7a7f49` (2.0.0 source, using `gym`). Installed distribution metadata reports 2.1.1; the original source takes precedence on `PYTHONPATH`, and imported module hashes are recorded. Checkpoints load with `weights_only=True` and a scoped allowlist for legacy NumPy numeric metadata.

## Verification and reproduction

- The initial 432 episodes were independently replayed: **14,937 decisions, zero mismatches**.
- All 144 training-rendering follow-up episodes passed independent replay of **771 decisions**, including framebuffer hashes, rewards, physical ticks, and final metrics.
- Three APPO contract tests and thirteen existing Doom environment tests passed.
- The existing Jev reference has 48 Basic episodes and 2,068 decisions; request receipts, action distributions, RNG decisions, and source hashes were audited.

The [validation report](../results/appo_basic_v1/validation.json) records these checks. Raw episodes, model download manifests, checkpoints, and the pinned source archive are stored locally under `runs/appo_basic_v1/`. The existing Jev source remains `data/unified_v2/jev_complete.jsonl`.

With the pinned source and inference dependencies available on `PYTHONPATH`, reproduce the two evaluations using fresh output paths:

```bash
python scripts/run_appo_basic_experiment.py \
  --model-dir runs/appo_basic_v1/models \
  --output-dir runs/appo_basic_repeat/episodes --workers 3

python scripts/diagnose_appo_doom_rendering.py \
  --model-dir runs/appo_basic_v1/models \
  --splits train,dev,calibration,test,ood \
  --output runs/appo_basic_repeat/native_rendering_all.json
```

`summarize_appo_doom.py` accepts all nine `--run NAME=EPISODES` inputs and an optional `--rendering-report` to regenerate the comparison. `audit_appo_jev_reference.py` rechecks the existing Jev reference without inference or API calls. Evaluation used CPU inference with one Torch thread per process and ViZDoom 1.3.0; no optimization or new Jev calls were performed.

The next Basic data collection can use these APPO actions as categorical targets for cross-entropy SFT. Its state export must use the actual rendering dimensions. Maze and Snake recipes are unchanged. No checkpoints were uploaded to Hugging Face.
