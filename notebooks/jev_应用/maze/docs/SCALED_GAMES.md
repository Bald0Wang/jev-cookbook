# Scaled maze and Snake pipeline

Run commands from the repository root, using new data/output directories for new experiments. Data generation and environment tests use Python's standard library. GPU training/inference require CUDA, the packages in [requirements-toy.txt](../requirements-toy.txt), and a local checkpoint at `checkpoints/NanoJev`; checkpoint download and environment setup are in the [pipeline runbook](../research/pipeline_runbook.md). API reference collection additionally needs Node.js 22+, `npm ci`, and a locally configured `.env`.

## Environments and question semantics

The default curriculum trains on 8×8, 16×16, and 32×32 boards and reserves 50×50 for size OOD. To include 50 in training and hold out 64, use `--train-sizes 8,16,32,50 --ood-sizes 64`. Every maze cell is rendered; larger boards are not cropped.

| Maze topology | Construction and difficulty |
| --- | --- |
| `corridor` | DFS tree with a straight-run bias; few junctions can still require a long detour. |
| `tree` | Unbiased DFS tree; one route between each pair of free cells, with more turns and dead ends. |
| `loops` | Additional passages create cycles and competing routes. |
| `random_obstacle` | Seeded obstacle density; retain the largest free component. |

Difficulty metadata records turns, junctions, dead ends, cycle rank, and shortest-path length; board size alone is not the difficulty measure. The renderer reads geometry and legal one-step destinations, never these metrics or BFS answers. Maze action Choice exists only with at least two legal moves; a sole move is executed directly and zero moves stop the episode.

Maze records combine four atomic `clear_<direction>` Boolean propositions with a separate planning stress profile: shortest-path action, reachability, and a seven-level distance Score. Atomic questions ask whether a geometric attempt stays in bounds and avoids a wall; they do not solve the route. Instructions contain the complete proposition, including direction. Choice names/descriptions are semantic inputs; IDs are transport metadata. Score leaves contain their own descriptions, without injected ordinal indices or neighboring levels. See [the question contract](TYPESAFE_CONTRACT.md).

Snake exposes the current head-first body, direction, and current food. Reverse moves are excluded, but collision-causing non-reverse proposals remain candidates. The tail vacates unless the move eats food; entering the vacated tail is legal. Food generation stores a reproducible 64-bit RNG stream in simulator state, excluded from model input. The v4b action target first avoids immediate collision, then minimizes next-head Manhattan distance to **current** food, uniformly resolving ties; it is a local policy, not a global planning or eventual-success probability. Per-action Boolean targets measure immediate safety.

## 1. Generate and validate data

```bash
export SCALED_DATA=data/scaled_games_run
python3 scripts/build_scaled_games.py --output-dir "$SCALED_DATA" --seed 20260920 \
  --train-sizes 8,16,32 --ood-sizes 50 --train-maps-per-size 12 --eval-maps-per-size 4 \
  --maze-states-per-map 4 --snake-states-per-episode 4 --snake-horizon 96
python3 scripts/train_pipeline_decisions.py --input "$SCALED_DATA/policy" --validate-only
python3 scripts/train_pipeline_decisions.py --input "$SCALED_DATA/events" --validate-only
```

The recorded v4b pilot contains **589 policy states / 3,195 questions** and **2,356 event states**. A [fresh-generation check](../results/dataset_reproduction_check.json) reproduces all ten policy/event split files byte for byte. Policy changes updated Snake's action rule; all five `events/*.jsonl` files are byte-identical to v4. `manifest.json` records file hashes and actual retained counts. The current pilot has no `test/8/corridor` maze cell because canonical-map deduplication removed that map. Generated mazes are connected, so their `solvable` labels are all true; this pilot does not test negative reachability cases.

Each maze keeps its initial episode start and samples distinct near-goal path positions, distant junctions, and reachable decision positions. Additional starts require at least two legal moves; provenance lives in `metadata.maze_position_source`. These are programmatically sampled training positions, not model trajectories. D4-equivalent wall layouts share a source group, ignoring agent/goal/seed. Snake groups follow size and canonical 64-bit episode seed. All members retain one split; duplicate observable records are filtered. Snake symmetry separation is audited on the resulting dataset, not guaranteed by its episode grouping alone.

```bash
python3 -m unittest discover -s scripts -p 'test_scaled_*.py' -v
python3 -m unittest discover -s scripts -p test_snake_game.py -v
python3 -m unittest discover -s scripts -p test_question_contract.py -v
```

## 2. Collect optional API reference data, then freeze

The programmatic `gold`/`gold_probs` path works without API calls. For a separate API-reference run, collect reference distributions for the policy directory only:

```bash
npm ci
node --env-file=.env scripts/label_decision_dataset.mjs --input-dir "$SCALED_DATA/policy" \
  --budget-usd 1 --max-requests 600 --concurrency 2 --max-failures 4 --skip-prior-failures true
python3 scripts/freeze_scaled_labels.py --input-dir "$SCALED_DATA/policy" \
  --output-dir "$SCALED_DATA/frozen_policy"
```

Use concurrency **2**: an earlier eight-worker attempt encountered timeouts. The dollar limit is an application reservation, and requests are not automatically retried. Keep `label_journal.jsonl` and `label_summary.json`; resolve incomplete collection before freezing. The freezer requires exact raw/annotated cohort coverage, verifies rendered-input hashes and record consistency, and preserves original split assignments. A narrowly checked JavaScript numeric round trip may affect Snake's metadata-only `rng_state`; the authoritative raw integer is retained. Model inputs and target values are not repaired or rewritten.

For the existing frozen run, use `data/scaled_games_labeled_v4` directly: all 589 states are present. Non-unit rounded API distributions are excluded only from the API-target objective, without inventing missing probability mass or removing independent gold targets. The generic `assemble_pipeline_dataset.py` has a different multi-source interface; this scaled-data workflow uses `freeze_scaled_labels.py`.

## 3. Train policy and observed-event models

The policy example starts from the downloaded NanoJev checkpoint with a fresh optimizer. Complete candidate sets stay together, even when microbatches shrink. Length/budget violations fail explicitly; inputs are never silently truncated.

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/train_pipeline_decisions.py \
  --input "$SCALED_DATA/policy" --output-dir runs/scaled_policy_gold \
  --init-checkpoint checkpoints/NanoJev --objective gold_distribution --loss ce \
  --steps 300 --head-steps 0 --seed 17 --eval-every 50 --batch-questions 12 \
  --microbatch-questions 1 --max-microbatch-tokens 16384 --max-length 8192 \
  --gradient-checkpointing --precision bf16 --disable-native-triton
```

For API targets, use `--input "$SCALED_DATA/frozen_policy" --objective teacher` and a distinct output directory. For a fresh Qwen initialization, replace `--init-checkpoint` with `--model Qwen/Qwen3-0.6B --revision c1899de289a04d12100db370d81485cdf75e47ca` and use `--head-steps 12`. These are executable starting settings, not a claim of optimal hyperparameters.

Event records specify a noisy actuator: the intended action occurs with reliability ρ, and alternatives split the remaining mass. Each record stores a sampled Boolean outcome and a separately known exact event distribution. **Use `--objective observed_outcome`** for the following comparison: exact probabilities are evaluation references, not training targets.

```bash
for EVENT_LOSS in ce brier paired_brier_pg; do
  CUDA_VISIBLE_DEVICES=0 python scripts/train_pipeline_decisions.py \
    --input "$SCALED_DATA/events" --output-dir "runs/scaled_events_$EVENT_LOSS" \
    --init-checkpoint checkpoints/NanoJev --objective observed_outcome --loss "$EVENT_LOSS" \
    --reward-samples 32 --steps 300 --head-steps 0 --seed 17 --eval-every 50 \
    --batch-questions 12 --microbatch-questions 1 --max-microbatch-tokens 16384 \
    --max-length 8192 --gradient-checkpointing --precision bf16 --disable-native-triton
done
```

All three runs use the same initialization, seed, data, and update budget. `paired_brier_pg` samples categorical actions with an explicit proper-reward policy-gradient objective; it does not generate reasoning text. Checkpoint selection uses dev target cross-entropy. Test/OOD are evaluated after selection; exact event distributions remain separate probability-recovery references. Oracle, outcome seed, realized actuator action, and RNG metadata never enter `state`/`questions` encoding.

## 4. Run frozen closed-loop episodes

```bash
python scripts/evaluate_scaled_games.py --episodes "$SCALED_DATA/episodes.jsonl" \
  --output results/scaled_policy_full.json --engine checkpoint --checkpoint runs/scaled_policy_gold \
  --splits test,ood --limit-per-cell 2 --max-steps 0 --controller sample --seed 17 \
  --max-length 8192 --batch-questions 2
for CONTROL_ENGINE in random reference; do
  python3 scripts/evaluate_scaled_games.py --episodes "$SCALED_DATA/episodes.jsonl" \
    --output "results/scaled_${CONTROL_ENGINE}_full.json" --engine "$CONTROL_ENGINE" \
    --splits test,ood --limit-per-cell 2 --max-steps 0 --controller sample --seed 17
done
```

`--max-steps 0` means **2 × size²** moves per episode. Selection takes the first fixed episodes per split/game/size/topology before predictions; runs record the source-file hash and retain every failure. Random always samples its uniform distribution. Reference uses exact shortest-path actions for mazes and the stated local food/safety rule for Snake. Returned probabilities must cover exactly the offered candidates and form a finite unit-sum distribution. For Jev execution, replace the checkpoint engine/options with `--engine jev --env-file .env --journal-dir results/jev_scaled_journal --budget-usd 1`.

The separate **six-episode, 128-step integration pilot** uses the committed [episode inputs](../results/rollout_pilot_episodes.jsonl) and frozen [pilot protocol](../results/rollout_pilot_protocol.json). Reproduce that pilot with `--episodes results/rollout_pilot_episodes.jsonl --max-steps 128 --limit-per-cell 1`; its horizon is not the full-size completion benchmark.

The primary development path uses [local atomic questions and code planning](ATOMIC_PLANNING.md). It has a matching local training dataset, a fixed-route judgment benchmark, and a controller that explores edges using model probabilities and remembers actual movement feedback. Whole-map next-action prediction remains the separate stress profile above.

Checkpoints include `best.safetensors`, model/tokenizer configuration, `train_log.json`, `summary.json`, and split prediction files. Aggregate observed-event runs with `python3 scripts/summarize_scaled_results.py --runs-dir runs --event-runs scaled_events_ce scaled_events_brier scaled_events_paired_brier_pg --output results/scaled_probability_summary.json`; report event probability recovery, atomic question accuracy, and planning success as separate measurements.
