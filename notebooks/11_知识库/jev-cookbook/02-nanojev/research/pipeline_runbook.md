# NanoJev pipeline: data, training, evaluation, and serving

[Back to NanoJev](../README.md)

This guide follows a complete new run: generate programmatic targets, train a 0.6B decision model, extend it with navigation data, evaluate the checkpoint, and serve batched decisions. Every path below is relative to the repository root. Use new output directories for each run.

## 1. Prepare the environment

Use Python 3.11 or newer for the scripts and a compatible NVIDIA CUDA environment for model training and inference. The package versions used by the implementation are recorded in [requirements-toy.txt](../requirements-toy.txt).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-toy.txt
```

The data generators and schema validation use the Python standard library. The programmatic-supervision workflow below requires no API key or model-service calls.

Cache the fixed Qwen3-0.6B revision before training:

```bash
python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3-0.6B",
    revision="c1899de289a04d12100db370d81485cdf75e47ca",
)
PY
```

## 2. Define questions and target distributions

Each JSONL training record contains a state, a question mapping, a split, and targets. The conceptual `target_distribution` is represented by the **`gold_probs`** field in the current training interface.

For example, this complete record describes an unobserved draw from a known distribution:

```json
{
  "id": "bag_001",
  "state_id": "bag_001",
  "family_id": "known_bag_probability",
  "split": "train",
  "state": "A token is drawn uniformly from a bag containing three red tokens and one blue token. The draw has not been observed.",
  "questions": {
    "color": {
      "type": "choice",
      "instructions": "What is the probability distribution of the drawn token's color?",
      "criteria": {"red": "The token is red", "blue": "The token is blue"}
    },
    "is_red": {
      "type": "boolean",
      "instructions": "The drawn token is red."
    }
  },
  "gold_probs": {
    "color": {"red": 0.75, "blue": 0.25},
    "is_red": {"false": 0.25, "true": 0.75}
  },
  "gold_probs_kind": "programmatic_conditional_distribution",
  "gold_label_kind": "unobserved",
  "metadata": {"source_group_id": "bag:red3:blue1"}
}
```

Use one complete JSON object per line. `id` identifies the record, `state_id` identifies its physical or semantic state, and `metadata.source_group_id` groups related variations into the same split. Supported splits are `train`, `dev`, `calibration`, `test`, and `ood`.

| Question type | Question fields | Target keys and output |
|---|---|---|
| `choice` | `instructions` and a `criteria` object with 2–255 candidates | Every candidate ID maps to a probability |
| `boolean` | `instructions`; optional `criteria` with `false` and/or `true` descriptions | `false` and `true`; inference returns `p_true` |
| `score` | `instructions` and an ordered `criteria` array with 2–10 descriptions | String indices `"0"` through `"K-1"`; inference returns the distribution and expected level |

Every probability must be finite and between zero and one. Each question's target must cover exactly its candidates and sum to one. Zero probabilities are valid. Candidate sets may differ between questions.

`gold_probs_kind` is either a string for the whole record or a mapping from question IDs to one of these values:

- `deterministic_truth`: a one-hot target.
- `programmatic_conditional_distribution`: a known conditional event distribution.
- `optimal_action_policy`: an action-policy distribution, such as equal mass on all optimal actions.

Optional hard targets use `gold`: a Boolean value, a Choice candidate ID, or a zero-based Score integer. When `gold_probs` is present, it supplies the distribution loss. An unobserved probabilistic target can omit `gold` entirely, as in the example above.

Only `type`, `instructions`, and optional `criteria` belong inside each question. Targets and grouping metadata stay outside the inference input.

## 3. Generate and assemble the programmatic dataset

Build support decisions, workflow tasks, and games:

```bash
python scripts/build_toy_decisions.py \
  --output-dir data/support --seed 17
python scripts/build_workflow_decisions.py \
  --output-dir data/workflows --seed 20260917
python scripts/build_game_decisions.py \
  --output-dir data/games --seed 17
```

The generators write split files. Combine the support and workflow splits in their fixed order, then create the empty optional overlay file used by the assembler:

```bash
python - <<'PY'
from pathlib import Path
splits = ("train", "dev", "calibration", "test", "ood")
for name in ("support", "workflows"):
    directory = Path("data") / name
    text = "".join((directory / f"{split}.jsonl").read_text() for split in splits)
    (directory / "all.jsonl").write_text(text)
Path("data/empty_overlay.jsonl").write_text("")
PY

python scripts/assemble_pipeline_dataset.py \
  --workflows data/workflows/all.jsonl \
  --games-raw data/games/all.jsonl \
  --games-labels data/empty_overlay.jsonl \
  --toy data/support/all.jsonl \
  --output-dir data/base_dataset --freeze

python scripts/train_pipeline_decisions.py \
  --input data/base_dataset/merged.jsonl --validate-only
```

The default generators produce **2,312 states and 6,936 questions**. The assembler preserves the existing splits, checks state and source-group separation, and writes `merged.jsonl` plus a manifest. `--freeze` writes the assembled dataset; without it, the command performs a source-data check.

For your own JSONL dataset, pass its file directly to `train_pipeline_decisions.py`. The trainer also accepts a directory containing the standard split files. Use `--validate-only` to check either form before loading a model.

## 4. Train a new base run

The following command trains a new model from the requested Qwen revision using the generated target distributions:

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/train_pipeline_decisions.py \
  --input data/base_dataset/merged.jsonl \
  --output-dir runs/base_run \
  --model Qwen/Qwen3-0.6B \
  --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --objective gold_distribution --set-head attention \
  --seed 17 --head-steps 12 --steps 600 \
  --batch-questions 12 --microbatch-questions 4 \
  --max-microbatch-tokens 6000 --max-length 512 \
  --eval-every 50 --precision bf16 \
  --backbone-lr 2e-5 --head-lr 2e-4 --head-warmup-lr 1e-3
```

`--head-steps 12` performs 12 head-only updates, followed by the 600 full-model updates specified by `--steps`. The effective batch contains 12 complete questions. Microbatches contain at most four questions and must fit the declared padded candidate-token limit.

For each complete question, the model computes:

```text
p = softmax(z)
L = -sum_i q_i * log(p_i)
dL/dz_i = p_i - q_i
```

Each question has equal loss weight. Its entire candidate set shares one normalization denominator. Microbatches accumulate gradients into one optimizer update; padding does not enter the candidate distribution. Increase the explicit token limit when a complete question requires more space.

Choice uses a shared scalar head and set attention. Boolean uses a single-path sigmoid. Score reads its level descriptions independently of set attention and returns their expected index.

The trainer selects the checkpoint with the lowest dev target cross-entropy. It evaluates the selected checkpoint on the remaining splits after training. Results for this new run are saved under `runs/base_run`:

| Artifact | Contents |
|---|---|
| `best.safetensors` | Selected model parameters |
| `config.json` | Model, revision, training arguments, and environment information |
| `tokenizer/`, `backbone_config/` | Files needed to load the checkpoint locally |
| `train_log.json` | Updates and dev evaluations |
| `summary.json` | Selected step, split metrics, timing, and memory statistics |
| `predictions_dev.jsonl`, `predictions_calibration.jsonl`, `predictions_test.jsonl`, `predictions_ood.jsonl` | Predictions and targets for each available split |

The commands define your new programmatic-supervision run. Its generated artifacts are the results to use for evaluation and serving.

## 5. Add navigation data and continue from a checkpoint

Generate the navigation dataset while excluding every source map in the earlier game dataset:

```bash
python scripts/build_navigation_v3.py \
  --v2-input data/games/all.jsonl \
  --output-dir data/navigation --seed 20260918

python scripts/assemble_navigation_v3_views.py \
  --canonical data/navigation/all.jsonl \
  --labels data/navigation/all.jsonl \
  --replay data/base_dataset/merged.jsonl \
  --output-dir data/navigation_views --seed 17
```

For this programmatic path, `--labels` points to the same canonical records and uses their existing targets. The view assembler produces `ascii_single.jsonl`, `ascii_multi.jsonl`, `coords_single.jsonl`, and `coords_multi.jsonl`.

The default navigation generator creates **500 maps, 3,000 states, and 9,000 questions**. Training covers 300 maps with eight exposure slots per map. Each view adds the same 984 non-navigation training records from the base dataset. The assembled training split contains 3,384 records and 10,152 questions.

Continue training from the base checkpoint created above:

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/train_pipeline_decisions.py \
  --input data/navigation_views/coords_multi.jsonl \
  --init-checkpoint runs/base_run \
  --output-dir runs/navigation_run \
  --model Qwen/Qwen3-0.6B \
  --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --objective gold_distribution \
  --seed 17 --head-steps 0 --steps 1200 \
  --batch-questions 12 --microbatch-questions 4 \
  --max-microbatch-tokens 6000 --max-length 512 \
  --eval-every 50 --precision bf16 \
  --backbone-lr 2e-5 --head-lr 2e-4
```

`--init-checkpoint` loads the exact model directory you select, including its decision-head configuration. It starts a new optimizer. Replace `runs/base_run` with another compatible checkpoint when continuing a different model, and give the new run its own output directory.

The coordinates view contains the agent, goal, walls, complete map, and legal next-position descriptions. The ASCII view presents the map without those explicit coordinates. Use the same representation when evaluating a checkpoint trained on a particular view.

## 6. Evaluate predictions and closed-loop navigation

Evaluate saved predictions by split, task family, and question type:

```bash
python scripts/evaluate_pipeline_decisions.py \
  --input runs/navigation_run/predictions_test.jsonl \
  --output runs/navigation_run/test_metrics.json

python scripts/evaluate_pipeline_decisions.py \
  --input runs/navigation_run/predictions_ood.jsonl \
  --output runs/navigation_run/ood_metrics.json
```

The metrics separate deterministic accuracy/Brier/ECE, known-distribution TV/KL, and optimal-action accuracy/probability mass. Use these groups to evaluate the targets represented in your data.

Run both navigation controllers with the same checkpoint and map cohort:

```bash
mkdir -p artifacts/navigation_run

CUDA_VISIBLE_DEVICES=0 python scripts/evaluate_navigation_v3.py \
  --data-dir data/navigation \
  --checkpoint-dir runs/navigation_run \
  --policy greedy --representation coords --precision bf16 \
  --seed 20260917 --per-split 20 \
  --name navigation_run_greedy \
  --output artifacts/navigation_run/greedy.json

CUDA_VISIBLE_DEVICES=0 python scripts/evaluate_navigation_v3.py \
  --data-dir data/navigation \
  --checkpoint-dir runs/navigation_run \
  --policy sample --representation coords --precision bf16 \
  --seed 20260917 --per-split 20 \
  --name navigation_run_sample \
  --output artifacts/navigation_run/sample.json
```

The evaluator takes one initial state from each of 20 reachable test maps and 20 reachable OOD maps. It uses independent per-episode RNG and a horizon of `2 × size²`. Every active-state batch runs in one model forward. Outputs include complete trajectories, success rates, path efficiency, repeated visits, action probabilities, and single-legal-action moves.

`--policy random` and `--policy oracle` run the corresponding environment controllers without a checkpoint. For the original Qwen option-token baseline, see the [model preparation and baseline commands](navigation_v3_native_qwen_zh.md).

## 7. Send batched inference requests

Create an inference request containing three independent questions. Target fields are not needed for inference:

```bash
cat > data/request.json <<'JSON'
{
  "states": [{
    "id": "living_room",
    "state": "The living room is 29 degrees. The target is 24 degrees. The window is closed and someone is home.",
    "questions": {
      "action": {
        "type": "choice",
        "instructions": "Choose the action that most directly lowers the room temperature.",
        "criteria": {
          "cool": "Turn on air conditioning",
          "light": "Turn on the lights",
          "wait": "Keep the current settings"
        }
      },
      "occupied": {"type": "boolean", "instructions": "Someone is home."},
      "heat": {
        "type": "score",
        "instructions": "Classify how far the room temperature exceeds the target.",
        "criteria": ["At or below target", "Above target by at most 3 degrees", "Above target by more than 3 degrees"]
      }
    }
  }]
}
JSON

CUDA_VISIBLE_DEVICES=0 python scripts/predict_toy_decisions.py \
  --checkpoint-dir runs/navigation_run \
  --input data/request.json \
  --output artifacts/navigation_run/decisions.json \
  --batch-questions 0 --precision bf16 --temperature 1
```

Add more objects to `states` to batch multiple states. `--batch-questions 0` evaluates all questions in one forward; a positive value batches complete questions. The response includes per-question distributions and execution counters.

## 8. Start the persistent service

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/serve_decisions.py \
  --checkpoint-dir runs/navigation_run \
  --web-root web --host 127.0.0.1 --port 8765 \
  --precision bf16
```

Open **http://127.0.0.1:8765**. The checkpoint is loaded once and reused across requests. From a second terminal in the repository root:

```bash
curl http://127.0.0.1:8765/api/health

curl http://127.0.0.1:8765/api/evaluate \
  -H 'Content-Type: application/json' \
  --data-binary @data/request.json
```

The local service accepts up to 32 states, 96 questions, and 256 candidate paths per request. Boolean uses one path; Choice and Score use one path per candidate or level.

Both the inference CLI and service support `--precision fp32` as well as BF16. Add `--disable-native-triton` only when using the original host's PyTorch native-Triton compatibility fallback.

## 9. Replay completed games

The repository's interactive replay can be served independently of the model:

```bash
python -m http.server 8080 --bind 127.0.0.1 --directory web
```

Open **http://127.0.0.1:8080/comparison.html**. To assemble your completed navigation runs into a separate replay data file:

```bash
python scripts/build_demo_artifact.py \
  --models artifacts/navigation_run/greedy.json \
           artifacts/navigation_run/sample.json \
  --output artifacts/navigation_run/demo_results.json
```

For a separate viewer using this run, copy the web files and install the generated replay data:

```bash
cp -R web artifacts/navigation_run/web
cp artifacts/navigation_run/demo_results.json artifacts/navigation_run/web/demo_results.json
python -m http.server 8081 --bind 127.0.0.1 \
  --directory artifacts/navigation_run/web
```

Open **http://127.0.0.1:8081** to inspect your completed runs and their recorded action distributions.

## 10. Use the hosted checkpoint and dataset

[Model: C-Tianyu/NanoJev](https://huggingface.co/C-Tianyu/NanoJev) · [Dataset: C-Tianyu/NanoJev-Data](https://huggingface.co/datasets/C-Tianyu/NanoJev-Data)

The model and dataset are publicly downloadable. Install the dependencies in section 1 before continuing. The root checkpoint below reproduces the earlier navigation pipeline; the [game release guide](../docs/GAME_RELEASE.md) maps the Maze, Snake, and calibrated-decision variants to their exact data.

Download the final model and the complete dataset into explicit local directories:

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="C-Tianyu/NanoJev",
    local_dir="checkpoints/NanoJev",
    allow_patterns=[
        "best.safetensors",
        "config.json",
        "tokenizer/*",
        "backbone_config/*",
    ],
)
snapshot_download(
    repo_id="C-Tianyu/NanoJev-Data",
    repo_type="dataset",
    local_dir="data/NanoJev",
)
```

The model patterns select the final root checkpoint. The dataset provides `stage1/all.jsonl` and `stage2/all.jsonl`, each with its existing split assignments. Both files use the training record interface described in section 2.

Validate the downloaded data locally:

```bash
python scripts/train_pipeline_decisions.py \
  --input data/NanoJev/stage1/all.jsonl --validate-only
python scripts/train_pipeline_decisions.py \
  --input data/NanoJev/stage2/all.jsonl --validate-only
```

Serve the downloaded model directly:

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/serve_decisions.py \
  --checkpoint-dir checkpoints/NanoJev \
  --web-root web --host 127.0.0.1 --port 8765 --precision bf16
```

To start a new continuation run from this model using the prepared stage 2 targets:

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/train_pipeline_decisions.py \
  --input data/NanoJev/stage2/all.jsonl \
  --init-checkpoint checkpoints/NanoJev \
  --output-dir runs/nanojev_continued \
  --model Qwen/Qwen3-0.6B \
  --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --objective gold_distribution \
  --seed 17 --head-steps 0 --steps 300 \
  --batch-questions 12 --microbatch-questions 4 \
  --max-microbatch-tokens 6000 --max-length 512 \
  --eval-every 50 --precision bf16 \
  --backbone-lr 2e-5 --head-lr 2e-4
```

This command creates a new model run with a fresh optimizer and selects its checkpoint on dev target cross-entropy. Use `data/NanoJev/stage1/all.jsonl` as the input to section 4 when starting a new base run instead. The resulting run directories work with the same prediction and service commands above.
