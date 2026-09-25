> **Unit note (added 20 Sep 2026).** The Cost column here is US dollars per 1,000 **decisions** — a whole question each (state, rubric, options) — never per 1,000 tokens. These are superseded numbers: v1.2.3 recomputed every price so each decision is counted once and priced once. Current results: [`RESULTS-v1.2.md`](RESULTS-v1.2.md), method and per-row figures: [`results/v1.2/cost-correction-v1.2.3.json`](results/v1.2/cost-correction-v1.2.3.json).

> [!WARNING]
> Superseded by **JevBench v1.2** — see [`RESULTS-v1.2.md`](RESULTS-v1.2.md). These results stay as published for their version.

# JevBench v1.1.3 - the GPU round

Generated from `results/v1.1.3/jevbench-v1.1.3-results.json` (2026-09-19 12:26 UTC).

**What v1.1.3 is:** the frozen v1.1 task set (314 typed decisions: 72 easy / 96 standard / 146 judge) and the v1.1.2 scoring, unchanged, plus open Jev rebuilds that need a GPU. We rented GPUs on RunPod and ran each rebuild the way its author serves it. Every v1.1.2 row is copied unchanged, so only the ranks move. The v1.1.2 numbers stay at tag `v1.1.2`.

![Main Score](results/v1.1.3/charts/main-score.png)

## Main Score (Balanced 33:33:33)

| # | System | Main | 60:20:20 | Capability | Speed | Cost | Easy | Standard | Judge | p50 / p95 | $ per 1,000 decisions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SemIf, formerly OpenJev (Qwen3.5-4B, TheoLeeCJ) **(GPU)** | **83.3** | 89.1 | 97.7 | 80.1 | 72.2 | 100.0 % | 97.9 % | 95.2 % | 0.20 s / 0.32 s | ~$0.0129 |
| 2 | open-alternative-jev, author's yes/no order* (post-hoc adapter mode) **(GPU)** | **79.7** | 82.3 | 86.3 | 79.4 | 73.3 | 100.0 % | 84.4 % | 74.7 % | 0.21 s / 0.32 s | ~$0.0117 |
| 3 | OpenJev (DiffusionGemma 26B-A4B NVFP4, razorback16) **(GPU)** | **78.2** | 85.2 | 95.6 | 78.3 | 60.7 | 100.0 % | 95.8 % | 91.1 % | 0.24 s / 0.31 s | ~$0.0372 |
| 4 | system-one (Qwen3-8B, Sean Goedecke) **(GPU)** | **77.9** | 84.4 | 94.1 | 82.4 | 57.0 | 100.0 % | 90.6 % | 91.8 % | 0.17 s / 0.30 s | ~$0.0523 |
| 5 | open-alternative-jev (Qwen3.5-4B, IkerMoel) **(GPU)** | **76.8** | 77.0 | 77.3 | 79.6 | 73.3 | 100.0 % | 81.2 % | 50.7 % | 0.20 s / 0.32 s | ~$0.0117 |
| 6 | system-one-open (Gemma 4 E2B LoRA on an L4) | **75.7** | 82.9 | 93.8 | 57.5 | 75.9 | 100.0 % | 93.8 % | 87.7 % | 0.65 s / 0.77 s | ~$0.0092 |
| 7 | Bespoke Nimble 9B (Bespoke Labs) **(GPU)** | **73.8** | 82.1 | 94.6 | 76.7 | 50.1 | 100.0 % | 94.8 % | 89.0 % | 0.19 s / 0.46 s | ~$0.0992 |
| 8 | Jev 1.13.0 (TypeSafe AI) | **73.6** | 83.3 | 97.8 | 58.2 | 64.7 | 100.0 % | 99.0 % | 94.5 % | 0.65 s / 0.72 s | $0.0259 |
| 9 | openjev-sglang (Qwen3.6-35B-A3B on SGLang) | **69.6** | 80.6 | 97.0 | 57.7 | 54.1 | 100.0 % | 95.8 % | 95.2 % | 0.68 s / 0.73 s | ~$0.0685 |
| 10 | Gemini 3.1 Flash-Lite | **65.0** | 78.0 | 97.4 | 54.5 | 43.3 | 100.0 % | 99.0 % | 93.2 % | 0.76 s / 0.88 s | $0.1856 |
| 11 | GPT-5.6 Luna (low reasoning effort) | **62.2** | 76.6 | 98.2 | 43.9 | 44.6 | 100.0 % | 97.9 % | 96.6 % | 0.97 s / 1.82 s | $0.1642 |
| 12 | open-jev-deberta-v3-large (local CPU) | **60.6** | 63.3 | 67.5 | 30.7 | 83.6 | 100.0 % | 49.0 % | 53.4 % | 1.77 s / 3.35 s | ~$0.0045 |
| 13 | DeepSeek V4.1 Flash (thinking default) | **55.7** | 72.2 | 96.9 | 29.0 | 41.2 | 98.6 % | 99.0 % | 93.2 % | 1.42 s / 4.89 s | $0.2252 |
| 14 | Needle 3, options as tools (post-hoc adapter mode) | **41.5** | 42.5 | 44.1 | 10.6 | 69.7 | 66.7 % | 31.2 % | 34.2 % | 3.78 s / 33.64 s | ~$0.0162 |
| 15 | Needle 3 (Cactus, 2-bit, local CPU) | **40.3** | 36.9 | 31.8 | 19.3 | 69.7 | 47.2 % | 16.7 % | 31.5 % | 1.69 s / 14.36 s | ~$0.0162 |

`~` = estimate (no tariff for us): priced like a large inference provider hosting the same weights or size class, never the GPU rental we paid. **(GPU)** = new in v1.1.3. A `*` in a name marks an adapter mode added after the frozen run, shown beside it.

**Shown, not ranked** (a tier was not attempted in full):

| System | Main | Coverage (easy / standard / judge) | Why |
|---|---|---|---|
| Qwen3.8 27B (Chutes TEE) | 42.5 | 100.0 % / 100.0 % / 87.0 % | v1.0 run stopped at 223 of 242 after three empty completions in a row (unchanged from v1.1.2) |

## How the GPU entrants were run

| System | Author's serving path we reproduced | GPU (RunPod) | Speed measured | GPU-side p50 / p95 | Same answers, GPU-side vs network run |
|---|---|---|---|---|---|
| SemIf, formerly OpenJev (Qwen3.5-4B, TheoLeeCJ) | author's direct mode (semif_phase1.direct.score), torch 2.10 / transformers 5.17 as pinned by the repo; Score mapping is our extension | RunPod RTX PRO 4500 Blackwell 32 GB (EU-RO-1) | from a Hetzner server in Germany over the internet to the pod's public TCP port (plain HTTP, one connection per request) through a thin transport around the author's library; model loaded before timing | 0.070 s / 0.197 s | 242 / 242 |
| open-alternative-jev, author's yes/no order* (post-hoc adapter mode) | loaded exactly like the author's HF Space demo (HFBackend bf16, batch_size 1, temperature 1.0), mode 'separate'; same question mapping as our v1.1 Space attempt | RunPod RTX PRO 4500 Blackwell 32 GB (EU-RO-1) | as open-alternative-jev | 0.079 s / 0.185 s | 242 / 242 |
| OpenJev (DiffusionGemma 26B-A4B NVFP4, razorback16) | author's Docker image razorback16/openjev:0.2.0 (vLLM PR #57250 + Jev-compatible API), defaults except OPENJEV_MAX_MODEL_LEN=32768 | RunPod RTX PRO 4500 Blackwell 32 GB (EU-RO-1) | from a Hetzner server in Germany over the internet to the pod's public TCP port (plain HTTP, one connection per request); model loaded before timing | 0.127 s / 0.186 s | 237 / 242 |
| system-one (Qwen3-8B, Sean Goedecke) | the author's library in-process (SystemOne.from_pretrained, bf16, device_map cuda), one question per call; only Choice is native, yes/no and score are mapped to Choice by us (fixed before the run) | RunPod RTX PRO 4500 Blackwell 32 GB (EU-RO-1) | from a Hetzner server in Germany over the internet to the pod's public TCP port (plain HTTP, one connection per request) through a thin transport around the author's library; model loaded before timing | 0.055 s / 0.199 s | 242 / 242 |
| open-alternative-jev (Qwen3.5-4B, IkerMoel) | loaded exactly like the author's HF Space demo (HFBackend bf16, batch_size 1, temperature 1.0), mode 'separate'; same question mapping as our v1.1 Space attempt | RunPod RTX PRO 4500 Blackwell 32 GB (EU-RO-1) | from a Hetzner server in Germany over the internet to the pod's public TCP port (plain HTTP, one connection per request) through a thin transport around the author's library; model loaded before timing | 0.079 s / 0.185 s | 242 / 242 |
| Bespoke Nimble 9B (Bespoke Labs) | the author's deploy/modal_app.py recipe on a pod: lmsysorg/sglang:v0.5.19-cu130 + openjev-sglang@7f84bed + nimble.serving.server (Jev-compatible /v1/systemone). Only change: API port 8000 -> 8080; Rust toolchain installed because SGLANG_RUST_SERVER=1 builds an extension. | RunPod A40 48 GB (EU-SE-1) | from a Hetzner server in Germany over the internet to the pod's public TCP port (plain HTTP, one connection per request); model loaded before timing. An earlier run through an SSH tunnel (RunPod's HTTPS proxy rejected the harness with a Cloudflare bot check) is kept as evidence and superseded. | 0.170 s / 0.421 s | 242 / 242 |

- **Same items, same scorer, same rules as v1.1.** Serial, no retries, immutable run folders, no label changes after seeing predictions. The answer key never leaves our machine: library-only entrants get the task without its gold label.
- **Speed is network-included, like every remote entrant in v1.1:** requests go from our Hetzner server in Germany over the internet to the rented GPU (EU data centres, TCP round trip about 55 ms to Romania). The GPU-side column is the same 242 decisions with the client on the GPU machine: it shows how much of each number is the network (for OpenJev, SemIf and open-alternative-jev that run was on an earlier pod with the same GPU model). API entrants (Jev, Gemini, GPT, DeepSeek, the Modal endpoints) pay their own, usually longer, round trip; a self-hosted model can sit next to its caller, so this is a real advantage of self-hosting, and it is also why these Speed scores are not a like-for-like comparison of model compute.
- **Models are loaded before timing starts**, as a running server would be. v1.1's CPU entrants counted their load in the first decision (1 of 242, so p50/p95 barely move).
- **Cost** follows v1.1.2 exactly: hosted-provider list price of the same weights (or the nearest larger sibling), times measured input tokens, plus one output token. What we actually paid RunPod is in SPEND below and is not the Cost score.

## Findings

- **Self-hosted open rebuilds take the top of the Balanced ranking; Jev drops from #2 to #8.** The reason is Speed and Cost, not accuracy. A 4-9B model on a GPU in a nearby data centre answers in about 0.2 s from Germany, against 0.65 s for Jev's API, and costs about $0.01-0.05 per 1,000 decisions at hosted-provider prices. On Capability, Jev (97.8) and SemIf (97.7) are level; only GPT-5.6 Luna is higher (98.2). With the accuracy-heavy 60:20:20 weights, SemIf still leads (89.1) and Jev is #4 (83.3).
- **SemIf (Qwen3.5-4B, frozen, no training) is the strongest rebuild:** 97.9 % standard, 95.2 % judge, #1 under five of six weightings.
- **Option order matters a lot for small frozen models.** open-alternative-jev reads the answer as a letter. Our v1.1 mapping listed yes/no questions as `A. no, B. yes`; on the 68 answer-judging items it then said "no" 61 times where 61 of 68 gold answers are "yes" (20.6 % on that cohort). With the author's own `yes_no()` order (`A. yes, B. no`) the same model scores 72.1 % there. The frozen run is the official row; the author-order run is shown beside it with a `*`, as v1.1 did for Needle 3's tools mode.
- **Bespoke Nimble 9B refuses prompts over its trained 2,048-token limit** (HTTP 422). On this task set that costs it 2 long answer-judging items (counted wrong, as for everyone).
- **OpenJev (DiffusionGemma) is not fully deterministic:** 237 of 242 answers matched between two runs. All other GPU entrants matched 242/242.
- **A preview of why v1.2 needs a hard tier:** on the 220-item hard tier being frozen for v1.2, these entrants score 44-66 % (OpenJev 65.5, SemIf 59.5, open-alternative-jev 55.0 / 56.8*, system-one 50.0, Nimble 43.6 with 69 items over its token limit), against Jev 74.1 % and GPT-5.6 Luna 94.5 % (the v1.2 job's runs). The near-100 % ceiling here hides real gaps. Those runs belong to v1.2 and are handed to that job.

## Sensitivity (rank under each weighting)

| System | 33/33/33 balanced (headline) | 60/20/20 accuracy emphasis | 20/60/20 speed emphasis | 20/20/60 cost emphasis | capability only | 33/33/33 geometric |
|---|---|---|---|---|---|---|
| SemIf, formerly OpenJev (Qwen3.5-4B, TheoLeeCJ) | 1 (83.3) | 1 (89.1) | 1 (82.1) | 1 (78.9) | 3 (97.7) | 1 (82.7) |
| open-alternative-jev, author's yes/no order* (post-hoc adapter mode) | 2 (79.7) | 6 (82.3) | 3 (79.6) | 2 (77.1) | 11 (86.3) | 2 (79.5) |
| OpenJev (DiffusionGemma 26B-A4B NVFP4, razorback16) | 3 (78.2) | 2 (85.2) | 4 (78.3) | 5 (71.2) | 7 (95.6) | 3 (76.9) |
| system-one (Qwen3-8B, Sean Goedecke) | 4 (77.9) | 3 (84.4) | 2 (79.7) | 8 (69.5) | 9 (94.1) | 5 (76.2) |
| open-alternative-jev (Qwen3.5-4B, IkerMoel) | 5 (76.8) | 10 (77.0) | 5 (77.9) | 4 (75.4) | 12 (77.3) | 4 (76.7) |
| system-one-open (Gemma 4 E2B LoRA on an L4) | 6 (75.7) | 5 (82.9) | 7 (68.4) | 3 (75.8) | 10 (93.8) | 6 (74.2) |
| Bespoke Nimble 9B (Bespoke Labs) | 7 (73.8) | 7 (82.1) | 6 (75.0) | 9 (64.3) | 8 (94.6) | 8 (71.4) |
| Jev 1.13.0 (TypeSafe AI) | 8 (73.6) | 4 (83.3) | 8 (67.4) | 6 (70.0) | 2 (97.8) | 7 (71.7) |
| openjev-sglang (Qwen3.6-35B-A3B on SGLang) | 9 (69.6) | 8 (80.6) | 9 (64.8) | 10 (63.4) | 5 (97.0) | 9 (67.2) |
| Gemini 3.1 Flash-Lite | 10 (65.0) | 9 (78.0) | 10 (60.8) | 11 (56.3) | 4 (97.4) | 10 (61.2) |
| GPT-5.6 Luna (low reasoning effort) | 11 (62.2) | 11 (76.6) | 11 (54.9) | 12 (55.2) | 1 (98.2) | 11 (57.7) |
| open-jev-deberta-v3-large (local CPU) | 12 (60.6) | 13 (63.3) | 12 (48.6) | 7 (69.8) | 13 (67.5) | 12 (55.7) |
| DeepSeek V4.1 Flash (thinking default) | 13 (55.7) | 12 (72.2) | 13 (45.0) | 15 (49.9) | 6 (96.9) | 13 (48.7) |
| Needle 3, options as tools (post-hoc adapter mode) | 14 (41.5) | 14 (42.5) | 15 (29.1) | 13 (52.8) | 14 (44.1) | 15 (31.9) |
| Needle 3 (Cactus, 2-bit, local CPU) | 15 (40.3) | 15 (36.9) | 14 (31.9) | 14 (52.1) | 15 (31.8) | 14 (35.0) |

## Scoring (unchanged from v1.1.2)

- **Capability.** Mean of the three tier accuracies (easy, standard, judge), each weighted 1/3, times 100. Frozen with the v1.1 dataset before any v1.1 inference. Pooled accuracy over all 314 decisions is published beside it.
- **Calibration.** Reported, not scored. Brier and ECE are published for every system that returns a distribution. They are not part of Capability or the Main Score, because label-only systems (Needle 3) have no distribution and any penalty we invented for that would be our choice, not a measurement; and verbalised LLM probabilities and native model distributions are different things.
- **Speed.** Median (p50) and 95th-percentile latency of successful requests in the system's serial run of the 242 standard+judge decisions (one request at a time, from a Hetzner server in Germany, network included; local models on 2 CPU threads of a Ryzen 5 3600). Each latency t maps to 100 * (log10(10 s) - log10(t)) / 2, clipped to 0..100: 0.1 s = 100, 1 s = 50, 10 s = 0. Speed = mean of the p50 and p95 scores. Log scale because 0.2 s vs 0.4 s matters as much as 2 s vs 4 s. v1.1.3 GPU entrants: measured on the named rented GPU, client on the same machine.
- **Cost.** Dollars per 1,000 decisions over all attempted decisions. Metered APIs: the provider's public tariff times measured tokens. No tariff for us (open weights, author demos, local runs): an ESTIMATE, labelled as such, priced as if a large inference provider hosted the model - the OpenRouter list price of the same weights (else the nearest larger sibling; else the DeepInfra list price of the same weights or of the nearest larger model of the same size class, e.g. same-size encoders for an encoder) times the tokens per decision (measured, or the input tokens of the gemini-3.1-flash-lite run on the same prompts). Not GPU rental by the minute and not our own CPU time: providers buy capacity in bulk or own the hardware. Each cost c maps to 100 * (log10($10) - log10(c)) / 4, clipped to 0..100: $0.001 per 1,000 = 100, $0.01 = 75, $0.10 = 50, $1 = 25, $10 = 0. Log scale over four decades, so every benchmarked system lands inside the scale and real price differences (e.g. an encoder vs a tiny generator) show up as different scores.
- **Main.** JevBench Main Composite Score = (Capability + Speed + Cost) / 3, 'Balanced 33:33:33'. Since v1.1.2 (19 Sep 2026); v1.1 and v1.1.1 used 0.6 * Capability + 0.2 * Speed + 0.2 * Cost, which is kept as the named weighting 'Emphasis on Accuracy (60:20:20)'. The sensitivity table shows the ranking under five other weightings.
- **Ranked.** Ranked: every tier attempted in full or nearly (>= 95% of decisions). Partial runs are shown, marked, and not ranked.

## Still not measured, and why

- **Dasein Labs open-jev**: MLX on Apple Silicon only; no Linux path.
- **JoshuaSP open-jev** (DiffusionGemma 26B-A4B, BF16): the repository ships bounded Modal batch jobs (`modal run infer.py`), not a decision service, and needs an 80 GB GPU. Not run in this round.
- **mini-jev** (r-ms): a preregistered study and teaching bench of letter-reading on Qwen3-4B, not a decision service.
- **system-one-gemma** (Akash Kamat): the base model, Gemma 3 270M, is gated behind Google's licence click-through; we do not accept binding terms on Florian's behalf.
- **jevlike, AlexWortega/openjev, GLiNER2, Needle-style routers**: unchanged from v1.1 (no general text-decision checkpoint, or no distribution over an arbitrary label set without an assumption we would be measuring instead).

## GPU bill for this round

RunPod, one pod at a time, hard cap $16. This is what we paid to measure, not the Cost score.

| # | Pod id | Entrant(s) | GPU | Cloud | $/h | Start (UTC) | End (UTC) | Hours | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1d7m4x7j8amn8l | razorback16 OpenJev, SemIf, open-alternative-jev (+ post-hoc variant) | RTX PRO 4500 Blackwell 32 GB | secure | 0.72 | 09:01:06 | 09:34:31 | 0.557 | $0.40 |
| 2 | fa4rk7jh3zyq5t | Bespoke Nimble 9B | A40 48 GB (EU-SE-1) | secure | 0.49 | 09:34:54 | 10:13:28 | 0.643 | $0.32 |
| 3 | x1daavk5xe45k0 | (OpenJev network rerun) - killed at 61 min by Sandy's global runpod-reaper before the server was up; no results | RTX PRO 4500 Blackwell 32 GB (EU-RO-1) | secure | 0.72 | 10:13:48 | 11:15:03 | 1.021 | $0.74 |
| 4 | v1d9uha0lh4fiz | network runs of OpenJev, SemIf, open-alternative-jev (+ variant), system-one (new); hard tier for all five | RTX PRO 4500 Blackwell 32 GB (EU-RO-1) | secure | 0.72 | 11:21:52 | 11:59:01 | 0.619 | $0.45 |
| 5 | stqy2bs9yoxzr6 | Bespoke Nimble 9B: network rerun over a direct TCP port + hard tier | A40 48 GB (EU-SE-1) | secure | 0.49 | 11:59:14 | 12:26:11 | 0.449 | $0.22 |

## Files

- `results/v1.1.3/jevbench-v1.1.3-results.json` - the artifact (aggregates only).
- `results/v1.1.3/charts/` - main score, sub-benchmarks, tiers, sensitivity.
- `jevbench/adapters/semif_direct.py`, `so1_decider.py`, `sg_system_one.py`, `remote_inproc.py` - the new adapters; the two server entrants (OpenJev, Nimble) use the existing `typesafe` adapter against the author's own `/v1/systemone`.
- `jevbench/runner.py` - one change: an HTTP 422 (the system refusing an input, e.g. over its context limit) no longer counts toward the three-consecutive-errors stop rule; it still counts as a wrong answer.
- `scripts/v1.1.3/` - the pod runner, the thin transport, the aggregator and the charts.
