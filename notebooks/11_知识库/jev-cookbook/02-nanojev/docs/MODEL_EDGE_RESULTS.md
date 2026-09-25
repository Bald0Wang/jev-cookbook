# Model-guided edge exploration: measured results

The model supplies four local safety probabilities. Code orders untried edges, records actual collision feedback, and repositions using only physically verified open edges. The policy receives no wall map, full-map solver, or hidden route. Every selected maze is retained.

The main comparison uses **2 × size² attempts**, including collisions: 128 for 8×8, 512 for 16×16, and 5,000 for 50×50. It supplements the original 128-attempt integration pilot on the same initial states; both sets remain available. See the [frozen cases](../results/rollout_pilot_episodes.jsonl), [original case-selection protocol](../results/rollout_pilot_protocol.json), and [replay audit](../results/model_edges_summary.json).

## System roles

Initial NanoJev is the existing trained checkpoint, not untouched Qwen. Local-atomic NanoJev adds focused local-question training. Jev supplies its recorded API probabilities. **Perfect local geometry** is an exact local parser using the same exploration controller, not a full-map BFS planner. **Constant 0.5 perception** always returns 0.5 for each Boolean proposition; it is not uniform random action selection.

All systems use the same threshold and code: among untried edges with p≥0.5, prioritize goal Manhattan distance, visits, then probability; otherwise physically probe the highest-ranked low-probability edge. Known-open graph search is used only to reach a remaining frontier. Probes and collisions count toward the attempt limit.

## Full-horizon results

Each cell is **attempts / collisions / status**. `goal` means completed; `limit` means the attempt budget expired.

| Case ID | Initial | Local atomic | Jev | Perfect local | Constant 0.5 |
|---|---:|---:|---:|---:|---:|
| `maze:test:8:23268921` | 25 / 9 / goal | 21 / 5 / goal | 16 / 0 / goal | 16 / 0 / goal | 27 / 11 / goal |
| `maze:test:16:23276922` | 32 / 8 / goal | 37 / 5 / goal | 108 / 40 / goal | 33 / 3 / goal | 43 / 13 / goal |
| `maze:ood:50:24310922` | 171 / 43 / goal | 244 / 36 / goal | 2738 / 1044 / goal | 133 / 5 / goal | 162 / 34 / goal |

Source reports: [Initial NanoJev](../results/model_edges_initial.json), [Local-atomic NanoJev](../results/model_edges_local_atomic.json), [Jev](../results/model_edges_jev.json), [Perfect local geometry](../results/model_edges_reference.json), [Constant 0.5 perception](../results/model_edges_constant.json).

| System | Completed | Total attempts | Successful moves | Collisions |
|---|---:|---:|---:|---:|
| Initial NanoJev | 3/3 | 228 | 168 | 60 |
| Local-atomic NanoJev | 3/3 | 302 | 256 | 46 |
| Jev | 3/3 | 2862 | 1778 | 1084 |
| Perfect local geometry | 3/3 | 182 | 174 | 8 |
| Constant 0.5 perception | 3/3 | 232 | 174 | 58 |

Local-atomic NanoJev records 46 collisions versus 60 for Initial NanoJev, but 302 total attempts versus 228. In this cohort, fewer collisions do not translate into better overall navigation efficiency.

## Original 128-attempt pilot, retained

Each cell is **attempts / collisions / status**. `goal` means completed; `limit` means the attempt budget expired.

| Case ID | Initial | Local atomic | Jev | Perfect local | Constant 0.5 |
|---|---:|---:|---:|---:|---:|
| `maze:test:8:23268921` | 25 / 9 / goal | 21 / 5 / goal | 16 / 0 / goal | 16 / 0 / goal | 27 / 11 / goal |
| `maze:test:16:23276922` | 32 / 8 / goal | 37 / 5 / goal | 108 / 40 / goal | 33 / 3 / goal | 43 / 13 / goal |
| `maze:ood:50:24310922` | 128 / 31 / limit | 128 / 14 / limit | 128 / 25 / limit | 128 / 5 / limit | 128 / 29 / limit |

Source reports: [Initial NanoJev](../results/model_edges_128_initial.json), [Local-atomic NanoJev](../results/model_edges_128_local_atomic.json), [Jev](../results/model_edges_128_jev.json), [Perfect local geometry](../results/model_edges_128_reference.json), [Constant 0.5 perception](../results/model_edges_128_constant.json).

The full-horizon controls complete 3/3 with perfect local predictions and 3/3 with constant perception. Their total attempts are 182 and 232; collisions are 8 and 58. Constant-perception completion shows that code exploration contributes substantially. Model value must be assessed through actual efficiency and error reduction, not completion alone.

## Interpretation and verification

Each controller visits different states. Its recorded atomic accuracy, scalar Brier, and NLL therefore describe its own visited-state distribution; they are not a direct comparison on identical questions. Use a separate fixed question cohort for model probability quality. This small three-maze study also does not establish generalization to arbitrary 50×50 maps.

The verifier reconstructs each original request from the simulator and uses a `RecordedEngine` to return only that node's saved probabilities. It checks state/question hashes, consumes every saved node once, and reproduces all actions, collisions, memory edges, and final states. It verifies source, renderer, and implementation hashes and embedded API-input/proxy consistency. It does not rerun inference or independently authenticate private API journals.

```bash
python scripts/summarize_model_edges.py
```

This command reads tracked artifacts and rebuilds the report without model or API calls. The earlier [direct-action pilot](DEVELOPMENT_RESULTS.md) asked models for whole-map actions. The separate `composed_*` diagnostic used full-map BFS with model judgments scored separately; neither should be conflated with this probability-guided exploration.
