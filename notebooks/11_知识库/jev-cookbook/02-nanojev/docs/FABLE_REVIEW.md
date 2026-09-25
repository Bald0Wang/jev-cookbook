# Fable implementation assistance and code review

On 2026-09-17, two local Claude Code requests explicitly selected `claude-fable-5-1` with `--effort xhigh`. Both returned that canonical model identifier in their usage records. Tools, Chrome integration, customizations, and session persistence were disabled. Only an authored specification or selected project source was supplied; no credentials were included.

| Request | Actual result | Reported list cost, USD |
|---|---|---:|
| Snake implementation request | Reached configured limits without returning implementation text. The project agent therefore implemented Snake independently. | 1.537427 |
| Independent code review | Completed successfully and returned concrete findings on Snake and the probability-training code. | 1.223819 |
| **Total** | Includes the CLI's auxiliary model usage. | **2.761246** |

These are the CLI's reported list costs, not a reconciled Vercel invoice. The first request demonstrates that the CLI budget option is checked after requests and is not a strict per-request billing ceiling. The second request allowed one turn and returned its review within the remaining allocation. Private prompts and raw response logs remain outside the repository.

## What was reviewed

The successful review received complete snapshots of [snake_game.py](../scripts/snake_game.py), [test_snake_game.py](../scripts/test_snake_game.py), and [calibrated_objectives.py](../scripts/calibrated_objectives.py), plus the training integration diff for [train_pipeline_decisions.py](../scripts/train_pipeline_decisions.py).

Fable approved the core Snake transition rules: reverse moves are rejected; nongrowing moves may enter the cell vacated by the tail; eating retains the tail; food never occupies the body; full-board completion is a win; collision preserves the last valid body; and transitions do not mutate their input. The stored RNG state preserves reproducible continuation through JSON round trips. Rendered model inputs contain physical state and explicit action-specific propositions, with no RNG or exact safety labels.

The review also approved the paired proper-reward gradient, its detached baseline, complete-question normalization, Boolean `[0,z]` representation, and the common optimizer-update denominator. This is a review of our explicit research implementation. It does not establish TypeSafe's undisclosed training procedure or demonstrate a learned model's performance.

## Probability-gradient conclusion

For independent categorical draws `A_i` from `p`, with replacement, the implemented reward is:

```text
R = (2/M) sum_i 1[A_i=Y]
    - sum_{i!=j} 1[A_i=A_j] / (M(M-1))
```

For each score-function term, retain the reward terms that depend on that sample:

```text
h_i = (2/M) 1[A_i=Y]
      - 2 sum_{j!=i} 1[A_i=A_j] / (M(M-1))

gradient E[R] = sum_i E[h_i gradient log p(A_i)]
```

The factor of two accounts for both ordered-pair positions. This gradient identity does **not** require or assert `R = sum_i h_i`.

The baseline for sample `i` depends on the other samples, the observed outcome, and detached probabilities, but not on sample `i`. Its expected score-function contribution is therefore zero. This requires conditionally independent model draws and an outcome observation independent of those prediction draws under the specified event experiment. It applies for every finite `M >= 2`. No group-standard-deviation normalization is used.

Unbiasedness does not guarantee lower gradient variance for every distribution. We did not adopt the review's suggestion to require the conditional-mean baseline to reduce gradient variance in every test. Numerical gradient checks and event-adapter validation are separate from this text review.

## Findings and follow-up decisions

| Finding | Resolution or boundary |
|---|---|
| Snake's deterministic safety records are not automatically eligible for the trainer's `observed_outcome` objective. | Correct separation. The event adapter must supply observed-outcome records; an ordinary action-preference target must not be relabelled as an observed event. The trainer owner covers this integration. |
| Seeds separated by a multiple of `2**64` share a random stream but originally had different episode groups. | Fixed: episode grouping uses the canonical 64-bit seed. An alias-grouping test was added. Ordinary nonnegative 64-bit seed groups are unchanged. |
| Boolean criterion insertion order differs from probability-map insertion order. | No label inversion in this implementation: the loader explicitly selects `false, true` by key. A test now verifies the resulting ordered target vector. |
| Loss configuration and numerical gradient tests need verification. | Assigned to trainer validation. The review alone is not evidence that an experiment ran. |
| Some external numeric scalar types are rejected. | The current public JSON contract uses Python integer outcome indices; strict type validation remains intentional. |

## Changes after the paid review

The reviewed action target was uniform over collision-free moves. At the user's request, the final action question now uses a **local food-progress heuristic**: first avoid one-step collision, then minimize Manhattan distance from the next head cell to the current food, sharing probability uniformly across ties. If every offered move collides, all offered actions tie. This is an action-policy target, separate from the individual safety propositions and from global Snake planning.

That change, the seed-grouping correction, and the additional tests were implemented and checked by the project agent after the paid review; they were not sent for another paid review. The source-group description was also corrected: this module groups an episode by size and canonical seed and does not claim to perform symmetry grouping.

Seven standard-library tests pass, covering determinism, JSON continuation, immutability, reverse and terminal rules, wall/body collisions, tail entry, growth, a full-board win, hidden-input exclusion, schema compatibility, food progress, tied moves, and the all-dangerous-action case:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p test_snake_game.py -v
```

An additional comparison against the exact reviewed source checked 2,880 states across board sizes 8, 16, 32, and 50. Safety-event input bytes, event specifications and outcomes, transition/RNG results, and ordinary nonnegative seed groups were unchanged. A preceding 8,640-candidate-transition check covered state immutability, safety/outcome consistency, and training-row validation. These are environment and interface checks, not evidence of a trained policy's playing strength.
