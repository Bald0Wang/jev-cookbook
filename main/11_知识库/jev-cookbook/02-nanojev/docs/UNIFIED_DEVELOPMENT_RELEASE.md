# Unified game release

The current NanoJev model covers Maze, Snake, ViZDoom Basic and Predict Position
with one checkpoint. This release packages the exact step-400 checkpoint used
by the development demonstrations, its training initialization, both complete
mixed datasets and the recorded evaluation inputs.

| Resource | Hugging Face repository | Version |
|---|---|---|
| Model, initialization and inference source | [C-Tianyu/NanoJev](https://huggingface.co/C-Tianyu/NanoJev) | `unified-games-v1` |
| Mixed data, evaluation and demonstration sources | [C-Tianyu/NanoJev-Data](https://huggingface.co/datasets/C-Tianyu/NanoJev-Data) | `unified-games-v1` |

**Upload complete and verified.** Both repositories carry the fixed `unified-games-v1` tag. The model contains 149 release files (4,826,217,398 bytes), including the selected checkpoint and initialization; the dataset contains 214 release files (880,108,238 bytes).

- Model revision: `047b927b30882a1138fc504821b82ac145a4b81a`.
- Dataset revision: `7afc5257c0f3ff0ba08512729888a51d94b40e7e`.

All uploaded files pass remote LFS SHA256 or Git blob checks, and 13 representative files pass anonymous download checks. Both checkpoint files also pass anonymous byte-range download checks.

Both repositories are public and support downloads without signing in. Earlier
releases remain available through their original revisions and the
`legacy-before-unified-games-v1` tag. Their files outside the new release paths
remain in the repository.

## Model contents

The repository root contains the original 15-file checkpoint bundle:
`best.safetensors`, `config.json`, backbone configuration, tokenizer and the
recorded training audits and predictions. `training_initialization/` contains
the complete 15-file checkpoint from which this round started.

- Selected arm: `hard_lr1e5`, step **400** of a 600-update run.
- Selected weights SHA256:
  `f68c47d66998231b86b7e91b4ed5e82ae23acf104c8b7cd6d165c3ac7b7ffe1b`.
- Initialization weights SHA256:
  `38116340795de1c82369b7fe15819d92d79600a7b4dc7a3cd0d4390cb6782639`.
- `source/` contains the runtime, training and replay code and dependency files.

The model uses the project's structured `DecisionPredictor` interface. Its
backbone scores the supplied candidates and returns an action distribution.
See the model card for a complete inference example.

## Dataset contents

Each of `unified/hard/` and `unified/soft/` contains **18,760 rows** across the
same five splits. The variants compare hard and soft Predict Position targets;
Maze, Snake and Basic preserve their existing recipe and split assignments.

| Split | Rows per variant |
|---|---:|
| Train | 10,898 |
| Development | 1,715 |
| Calibration | 1,709 |
| Test | 2,496 |
| OOD | 1,942 |

The trainer quarantines 11 invalid-target questions across the splits. It uses
10,893 eligible training questions: 651 Maze, 400 Snake, 3,054 Basic and 6,788
Predict Position. The original rows and audit are retained.

The dataset repository also includes:

- The original mixed preparation input, 896 Predict Position expert episodes
  containing 17,498 decisions, and hard/soft preparation manifests.
- Frozen development and 548-case test/OOD registries; selection results,
  complete NanoJev/Jev/untuned-Qwen recordings and independent replay checks.
- Configurations and logs for the four hard/soft and learning-rate comparisons.
- The fixed hard Maze/Snake cases, all six source recordings and the source
  dependencies needed to rebuild those demonstrations without inference.
- Basic and Predict Position replay indices and their verification receipts.

## Training and reproduction

The selected run uses mixed-task supervised cross entropy with backbone
learning rate `1e-5`, head learning rate `1e-4`, seed 17 and 24 questions per
update: 8 Maze, 8 Snake, 4 Basic and 4 Predict Position. Computation uses BF16,
gradient checkpointing, eight-question microbatches and an 8,192-token maximum.
Development evaluation chooses the checkpoint and learning-rate/target variant.

Both repositories include `TRAINING_RECIPE.md`, with exact environment versions,
training flags, a data-only validation command and a CPU replay command. Download
both snapshots with `revision="unified-games-v1"`. Set `MODEL_DIR` and `DATA_DIR`
to their absolute paths before following the recipe.

The hard-navigation CPU reconstruction checks **8,412 transitions** across all
six recordings. Its output matches the development export byte-for-byte:
`a0cafaba6f49b97b1d1f00583b27d07347964df5802c8384f317d1a5fdc074a7`.
These selected demonstrations remain separate from the full frozen benchmark.

## Release verification

Each repository contains `SHA256_MANIFEST.json`. The publication script checks
every local file before upload, compares remote LFS SHA256 or Git blob identity
for every uploaded file, downloads representative files to verify their bytes,
and checks that both release tags resolve to their recorded public revisions.

The complete machine-readable result, exact remote revisions, file counts and
preserved earlier revisions and private-source checks are stored in
[`results/huggingface_unified_public_release.json`](../results/huggingface_unified_public_release.json).
Weights are verified against their remote LFS SHA256 without a second full
multi-gigabyte download.
