# RLCD-inspired probability learning: specification and measured controls

This experiment implements an explicit sampled proper-reward objective and compares it with direct probability losses. The gradient checks pass, and both CPU and Qwen experiments learn useful probability information. The evidence does not establish that the sampled method is better than direct controls.

## What is public, and what is our method?

TypeSafe expands RLCD as **Reinforcement Learning for Calibrated Decisions** and describes decisions with probabilities instead of generated text. Its checked public materials do not disclose a reproducible reward, optimizer, or training implementation. Our formula below is an independent research candidate, not a recovered official recipe. See the [official primer](https://docs.typesafe.ai/introduction/machine-learning-primer) and [launch article](https://typesafe.ai/blog/introducing-system-one-models-and-jev).

An action policy `pi(a|state)` specifies how frequently a controller chooses an action. An event prediction `p(Y|state,question)` forecasts a defined outcome. A distribution over preferred actions is not automatically a distribution of success probabilities. Event calibration and game-policy quality are evaluated separately.

## Objective and necessary conditions

For visible input `x`, let `Y ~ q(.|x)` be an observed outcome and `p = softmax(logits)` cover the complete candidate set. Draw `M >= 2` independent predictions with replacement, `A_i ~ p`, and let `c[k]` count occurrences of candidate `k`.

```text
R = (2/M) sum_i 1[A_i=Y] - sum_k c[k](c[k]-1)/(M(M-1))
E[R | x] = 2 p.q - ||p||^2 = ||q||^2 - ||p-q||^2
r_i = (2/M) 1[A_i=Y] - 2(c[A_i]-1)/(M(M-1))
b_i = (2/M) p[Y] - 2 sum_{j!=i} p[A_j]/(M(M-1))
L_PG = -sum_i stop_gradient(r_i-b_i) log p[A_i]
E[grad L_PG | x] = grad ||p-q||^2
```

The other samples and `Y` are fixed when taking the conditional expectation over `A_i`: the detached baseline must not depend on `A_i` itself. All sample-dependent reward terms must be included. Zero baseline is also valid. The scalar surrogate is not a reported Brier score, and its mean need not numerically equal the direct loss.

`Y` must be independent of the predictive draws conditional on `x`. The predictions are possible labels of the same event, not physical actions that change that event's outcome. Correlated draws, including self-pairs in the agreement penalty, or differentiating through the baseline breaks this argument. Rewarding only `1[A=Y]` is linear in `p` and favors a winning class instead of recovering `q`.

Direct controls are observed cross-entropy `-log p[Y]` and vector Brier `sum_k(p[k]-1[Y=k])^2`. Their population optima also recover `q`; the pair method is a stochastic gradient estimator of the same expected Brier objective. This follows [proper-scoring theory](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf), not an unpublished TypeSafe algorithm.

The implementation accepts a different complete candidate set per question, excludes padding before normalization, and averages equally across questions. It scores candidate paths in tensor batches with a decision head; there is no autoregressive generation or textual reasoning loop. The event experiment uses Boolean candidates; separate numerical checks cover dynamic `K` through 255.

## Mathematical and CPU evidence

[calibrated_objectives_check.json](../results/calibrated_objectives_check.json) records float64 enumeration for `M=2, K=2/3/5` and `M=3, K=2`, with and without the conditional baseline. Maximum exact gradient error was **1.39e-16**. Fixed-seed Monte Carlo checks, Boolean scaling, candidate relabeling, invalid inputs, padding isolation, and per-question mean checks all passed; the largest Monte Carlo gradient discrepancy was **2.003 standard errors**.

[calibrated_learning_benchmark.json](../results/calibrated_learning_benchmark.json) uses a small shared candidate MLP, non-degenerate known `q`, and dynamic `K=2/3/5`. Fixed train/dev/test sizes are 1,536/768/2,048. Seeds 17/18/19 share the same data; within each seed, every arm shares initialization and the batch schedule. Each arm completes 600 Adam updates, batch 32, learning rate 0.003; sampled arms use `M=32`.

| CPU arm | Test known-q squared L2, mean ± sample SD |
|---|---:|
| Initial random scorer | 0.038371 ± 0.005178 |
| Observed CE | 0.002581 ± 0.000516 |
| Direct Brier | 0.003279 ± 0.000530 |
| Paired proper-reward PG | 0.003377 ± 0.000908 |
| Correctness-only REINFORCE | 0.017131 ± 0.013953 |

All CPU arms select the minimum observed dev NLL, including step zero, before one test evaluation. Correctness-only selected steps 50/0/50; its final-step dev NLL rose to 3.146/2.814/3.162. Early selection therefore limits the damage visible in its test row. Seed SD conditions on one dataset and is not a confidence interval over new tasks. These results support correctness of the proper-reward implementation, not a superiority claim.

## Qwen event experiment

The three arms start from the same existing NanoJev checkpoint, `v3_teacher_coords_multi_seed17`, built on Qwen3-0.6B revision `c1899de289a04d12100db370d81485cdf75e47ca`. “Initial” below is this checkpoint before event training, not an untouched language model. All arms use seed 17, 100 full-model steps, effective batch 16, BF16 forward, and an 8,192-token limit with complete inputs. AdamW uses backbone/head rates 2e-5/2e-4, weight decay 0.01, and gradient-norm clipping at 1.0. The unbiased-estimator proof describes the raw gradient, not the nonlinear optimizer or clipping operation.

The frozen simulator inputs specify maze or Snake geometry and a random actuator: execute a named move with reliability `rho`, otherwise choose another offered move uniformly. The target event is one-step collision-free movement. Exact `q` follows from simulator transitions; a separately seeded actuator draw supplies observed `Y`. Only observed outcomes enter the three training losses. Exact probabilities remain available for evaluation, outside the model request.

Frozen split counts are train **1,124**, dev **372**, calibration **368**, test **364**, and OOD **128** questions. Sizes 8/16/32 form the regular curriculum; size 50 is OOD. The saved manifest records source-group isolation. Evaluation questions from the same map or episode are not independent maps. The summary retains every question, including deterministic event cases: all 64 OOD Snake questions have `q(true)=1`. Therefore the aggregate OOD slice is not a clean test of richer stochastic reasoning or long-horizon play.

Results below come directly from [scaled_probability_summary.json](../results/scaled_probability_summary.json); lower is better for all three metrics. Each cell contains **NLL / vector Brier / known-q squared L2**.

| Qwen event arm | Test, 364 questions | OOD, 128 questions |
|---|---:|---:|
| Initial NanoJev | 0.639286 / 0.446492 / 0.277078 | 0.679861 / 0.486668 / 0.319949 |
| Observed CE | 0.460450 / 0.299032 / 0.124226 | 0.332381 / 0.229906 / 0.072497 |
| Direct Brier | 0.450525 / 0.303270 / 0.138445 | 0.316682 / 0.208351 / 0.067186 |
| Paired proper-reward PG | 0.427911 / 0.278123 / 0.118444 | 0.329677 / 0.201326 / 0.062022 |

All three trained checkpoints were selected at step 100 by minimum observed dev NLL among steps 50/100. Test outcomes did not select checkpoints or remove examples. The paired arm has lower L2 in this one run, while direct Brier has lower OOD NLL; one seed and a narrow event family cannot establish a general ranking.

The summary checks both `gold_probs_kind=programmatic_conditional_distribution` and `gold_label_kind=observed_outcome`, reports family-specific metrics, and keeps action targets outside event calibration. Vector Brier is twice scalar Bernoulli Brier. Boolean ECE uses ten fixed bins of `p(true)` against finite-sample observed frequencies; it is not top-label ECE or a calibration guarantee. Invalid files make the report incomplete. Zero-probability errors are retained, with `max(p,1e-12)` only inside logarithms; these measured event runs had no zero or floored probabilities. Export sum errors within 1e-5 are normalized and logged; no other distribution repair is applied.

## Reproduction: frozen input to complete report

Run from the repository root. Use the versions in `requirements-toy.txt` and a CUDA device for the Qwen stage; the mathematical and MLP checks run on CPU. The five frozen files under `data/scaled_games_v4/events/` must match each run's `config.json:data_sha256` and the dataset manifest. `build_scaled_games.py` and `game_outcomes.py` implement environment snapshots, visible requests, observed labels, and exact references; do not silently substitute regenerated data after changing those sources.

```bash
python scripts/test_calibrated_objectives.py --mc-repeats 2000 --output results/calibrated_objectives_check.json
python scripts/benchmark_calibrated_learning.py --steps 600 --seeds 17 18 19 --output results/calibrated_learning_benchmark.json
python scripts/train_pipeline_decisions.py --input data/scaled_games_v4/events --validate-only
export NANOJEV_EVENT_INIT=/path/to/v3_teacher_coords_multi_seed17
python scripts/evaluate_game_questions.py --input data/scaled_games_v4/events \
  --checkpoint "$NANOJEV_EVENT_INIT" --output-dir runs_repro/events_initial --max-length 8192
for objective in ce brier paired_brier_pg; do
  run_name="events_${objective}_seed17"
  if [ "$objective" = paired_brier_pg ]; then run_name=events_paired_seed17; fi
  python scripts/train_pipeline_decisions.py --input data/scaled_games_v4/events \
    --output-dir "runs_repro/$run_name" --init-checkpoint "$NANOJEV_EVENT_INIT" \
    --objective observed_outcome --loss "$objective" --reward-samples 32 \
    --steps 100 --head-steps 0 --batch-questions 16 --microbatch-questions 4 \
    --max-microbatch-tokens 16384 --eval-every 50 --max-length 8192 --seed 17 \
    --backbone-lr 2e-5 --head-lr 2e-4 --precision bf16 \
    --gradient-checkpointing --disable-native-triton
done
python scripts/summarize_scaled_results.py --self-check
python scripts/summarize_scaled_results.py --runs-dir runs_repro \
  --initial-run events_initial --output results/scaled_probability_summary_reproduced.json
```

Use fresh run directories. Replace the checkpoint path with the complete recorded checkpoint package; a backbone-only download is not the same initialization. Training saves config/input hashes, dev selection, checkpoint, token/target audits, logs, and held-out `predictions_{test,ood}.jsonl`; the summarizer reads those predictions without rerunning inference. Probability quality and environment rollouts remain separate outputs. The saved original reports remain the evidence for the tables above.

## Next priorities

The accepted development direction is **atomic judgments + code planning**; planner-driven game success and event-probability calibration remain separate measurements.

Expand semantic task coverage and outcome definitions before increasing optimizer complexity: richer game states, nontrivial Snake risk, and explicitly defined multi-step events under a frozen continuation policy. Keep complete observations and future outcomes separated, preserve map/episode groups, and evaluate the full probability vector with proper losses and known-q diagnostics where available.

Retain CE and direct Brier as first-class controls, add training seeds and matched event cohorts, and measure estimator variance and compute. For a small finite candidate set, exact Brier avoids unnecessary sampling variance. Use policy gradients when the experimental question or interaction setting warrants them, rather than adding them merely to obtain an RL label. Better game return and better event probabilities each require their own evidence.
