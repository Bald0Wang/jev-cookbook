# Game checkpoints, datasets, and reproduction

The public [model repository](https://huggingface.co/C-Tianyu/NanoJev) contains the original root and `stage1/` checkpoints plus six game and calibrated-decision variants. The public [dataset repository](https://huggingface.co/datasets/C-Tianyu/NanoJev-Data) contains the original stages plus the `games_v4/` package. Each game variant includes complete model weights, tokenizer, backbone configuration, and the recorded training configuration and summary.

## Select the matching checkpoint and data

| Checkpoint under `variants/` | Purpose | Training data under `games_v4/data/` |
|---|---|---|
| `local_atomic_seed17` | 50×50 maze showcase; four local safety judgments | `local_maze_v1/` |
| `games_gold_seed17` | Snake showcase; dynamic action choices | `scaled_games_v4b/policy/` |
| `games_api_seed17` | Full-map game-question comparison | `scaled_games_labeled_v4/` |
| `events_ce_seed17` | Observed-event CE control | `scaled_games_v4b/events/` |
| `events_brier_seed17` | Observed-event Brier control | `scaled_games_v4b/events/` |
| `events_paired_seed17` | RLCD-inspired paired proper-reward experiment | `scaled_games_v4b/events/` |

The original event runs record `data/scaled_games_v4/events` in their configurations. The hosted `scaled_games_v4b/events` files are byte-identical and match those recorded input hashes. The root model remains the initialization checkpoint and the model for the earlier 40-map navigation benchmark.

## Download and verify

Clone the public code and install the CUDA runtime dependencies:

```bash
git clone https://github.com/TianyuCodings/NanoJev.git
cd NanoJev
python -m pip install -r requirements-toy.txt
```

Download the two showcase models and the complete game data package:

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="C-Tianyu/NanoJev",
    local_dir="checkpoints/NanoJev",
    allow_patterns=[
        "variants/local_atomic_seed17/*",
        "variants/games_gold_seed17/*",
        "GAMES_MODEL_MANIFEST.json",
    ],
)
snapshot_download(
    repo_id="C-Tianyu/NanoJev-Data",
    repo_type="dataset",
    local_dir="data/NanoJev",
    allow_patterns=["games_v4/*"],
)
```

Choose another variant from the table to download its complete directory. Exact file hashes and version receipts are recorded in [the release receipt](../results/huggingface_games_release.json), `GAMES_MODEL_MANIFEST.json`, and the dataset package's `manifest.json`.

```bash
python data/NanoJev/games_v4/verify_dataset.py
python scripts/train_pipeline_decisions.py \
  --input data/NanoJev/games_v4/data/local_maze_v1 --validate-only
python scripts/train_pipeline_decisions.py \
  --input data/NanoJev/games_v4/data/scaled_games_v4b/events --validate-only
```

## Run the two game controllers

The maze model supplies local safety probabilities. Shared code explores untried edges and repositions through physically verified open paths. A zero `--max-steps` selects the recorded size-dependent attempt budget, allowing the 50×50 episode to finish.

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/evaluate_model_edges_maze.py \
  --episodes results/rollout_pilot_episodes.jsonl \
  --engine checkpoint --checkpoint checkpoints/NanoJev/variants/local_atomic_seed17 \
  --max-steps 0 --batch-states 2 --batch-questions 0 --max-length 2048 \
  --output runs/hosted_game_repro/maze.json
```

For Snake, the shared code filters immediate collisions and retains actions on shortest static paths toward the visible food. The model chooses among remaining candidates. This runs all eight frozen cases using greedy control, including the `snake:showcase:12:61005` recording used in the README.

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/evaluate_composed_snake.py \
  --episodes data/NanoJev/games_v4/arcade/cohort.jsonl \
  --engine checkpoint --checkpoint checkpoints/NanoJev/variants/games_gold_seed17 \
  --controller greedy --max-steps 256 --seed 17 \
  --batch-states 2 --batch-questions 0 --max-length 8192 \
  --output runs/hosted_game_repro/snake.json
```

Use a new output path for subsequent runs. The recorded results use BF16 inference on A100 GPUs; the complete original trajectories are included in the dataset package.

## Rebuild the recorded showcase without model calls

The dataset includes all six Snake controller recordings as lossless gzip files. This restores the exact JSON bytes, then rebuilds both scenes with the original three-system results:

```python
import gzip
from pathlib import Path

source = Path("data/NanoJev/games_v4/arcade/rollouts")
target = Path("runs/hosted_arcade_sources")
target.mkdir(parents=True, exist_ok=False)
for compressed in sorted(source.glob("*.json.gz")):
    (target / compressed.stem).write_bytes(gzip.decompress(compressed.read_bytes()))
```

```bash
python scripts/build_arcade_demo.py \
  --snake-trained runs/hosted_arcade_sources/trained_greedy.json \
  --snake-jev runs/hosted_arcade_sources/jev_greedy.json \
  --snake-base runs/hosted_arcade_sources/base_greedy.json \
  --snake-case snake:showcase:12:61005 \
  --output runs/hosted_game_repro/arcade_results.json \
  --manifest runs/hosted_game_repro/arcade_manifest.json
```

The builder verifies planner candidates, recorded probabilities, simulator transitions, and final outcomes. [The viewer guide](../web/README.md) explains playback and GIF/MP4 rendering. For training, use the hosted input directories with the commands in [scaled games](SCALED_GAMES.md), [atomic maze judgments](ATOMIC_PLANNING.md), and [calibrated-decision learning](RLCD_EXPERIMENT.md).

## Frozen release revisions

- [Model snapshot](https://huggingface.co/C-Tianyu/NanoJev/tree/4a19595eada0857133c0d2be024f879a4077054b): `4a19595eada0857133c0d2be024f879a4077054b`.
- [Dataset snapshot](https://huggingface.co/datasets/C-Tianyu/NanoJev-Data/tree/87061eb91e8fc687e9b046454afdcc5551e3eff7): `87061eb91e8fc687e9b046454afdcc5551e3eff7`.

Pass the corresponding `revision` to `snapshot_download` to retrieve this exact release. Uploaded file hashes, anonymous download checks, and inference bundle checks are recorded in the release receipt above.
