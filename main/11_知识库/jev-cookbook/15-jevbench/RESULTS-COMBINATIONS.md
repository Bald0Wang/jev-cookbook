# JevBench v1.2.6 combination study

This is a frozen offline replay over all 534 decisions. It does not change the ranked
leaderboard. No combination beat the best published single-system composite,
classifier.dev Fast at **84.836**, so none is an honorable mention.

Thresholds were selected on the 231 redistributable public items only. The 303 remaining
items were opened once for evaluation. Cost pays every invoked member; committee and
best-of-n latency waits for the slowest parallel call, while cascade latency is serial.
The machine-readable result includes source hashes and every one-point cascade curve in
[`results/v1.2/jevbench-v1.2-combinations.json`](results/v1.2/jevbench-v1.2-combinations.json).

## Cascade sweep

The one operationally attractive pair was **classifier.dev Fast → Jev 1.13.0** at a
0.42 confidence threshold. It escalated 4.76% on tuning and 2.97% held out. Held-out
accuracy was 84.82% versus Jev's 85.15% (99.61% retained), cost was **$0.00452/1k**
versus $0.03991/1k, and p95 was **0.477 s** versus 0.722 s. Across all 534 items it scored
**81.225**, below classifier.dev Fast alone (84.836), so it is not published on the board.

The three most informative pairs at their public-selected threshold:

| First stage → backend | Threshold | Held-out escalation | Held-out accuracy | $/1k | p95 | Full composite | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| classifier.dev Fast → Jev | 0.42 | 2.97% | 84.82% | 0.00452 | 0.477 s | 81.225 | useful vs Jev, but worse than its first stage alone |
| djev → Jev | 0.79 | 12.21% | 85.15% | 0.03083 | 0.932 s | 72.197 | slower than Jev |
| SemIf 4B → djev | 0.39 | 3.96% | 79.87% | 0.02347 | 1.120 s | 72.365 | loses too much backend accuracy and is slower |

Selected held-out curve points (threshold: escalation / accuracy / cost / p95):

- classifier.dev→Jev: 0.0: 0.0% / 84.82% / $0.00333 / 0.457 s; 0.4: 2.64% /
  84.82% / $0.00439 / 0.474 s; 0.6: 9.90% / 85.48% / $0.00729 / 1.083 s;
  0.8: 18.48% / 85.15% / $0.01071 / 1.126 s; 1.0: 59.74% / 85.15% /
  $0.02718 / 1.154 s.
- djev→Jev: 0.0: 0.0% / 83.50% / $0.02595 / 0.345 s; 0.4: 0.99% / 83.17% /
  $0.02635 / 0.354 s; 0.6: 6.27% / 84.16% / $0.02845 / 0.874 s; 0.8: 12.87% /
  85.15% / $0.03109 / 0.944 s; 1.0: 100% / 85.15% / $0.06587 / 1.063 s.
- SemIf→djev: 0.0: 0.0% / 79.87% / $0.02244 / 1.115 s; 0.4: 4.62% / 79.87% /
  $0.02364 / 1.120 s; 0.6: 15.84% / 80.86% / $0.02656 / 1.256 s; 0.8: 26.73% /
  81.85% / $0.02938 / 1.349 s; 1.0: 100% / 83.50% / $0.04840 / 1.422 s.

## Committees

All plausible 3- and 5-member sets from nine complete Jev-class systems were evaluated.
The best set was Jev + SemIf + djev. Calibration weighting was best, followed by plain
probability averaging; majority voting was materially worse.

| Method (best set for that method) | Accuracy | Calibration axis | $/1k | p95 | Composite |
|---|---:|---:|---:|---:|---:|
| Calibration-weighted: Jev + SemIf + djev | 83.90% | 87.12 | 0.08831 | 1.135 s | **70.856** |
| Probability average: Jev + SemIf + djev | 83.52% | 85.47 | 0.08831 | 1.135 s | 70.462 |
| Majority: Jev + djev + open-alternative-jev | 81.46% | 68.80 | 0.08804 | 1.124 s | 66.383 |

The committee improves calibration, but paying three members collapses the cost axis and
the slowest member controls latency. It does not earn publication.

## Best-of-n

Only OpenJev razorback16 had two genuinely different frozen runs of the same system.
Their probabilities differed on 314/534 items and labels on 5/534. The hard-tier replay
was byte-identical, so no variance was invented there. Averaging the two real samples gave
78.65% accuracy, calibration 61.58, $0.13121/1k, p95 1.080 s and composite **62.029**.
It is worse than one call and does not earn publication. SemIf's three recorded easy-tier
replays were probability-identical; deterministic systems were skipped.

## Reproduction

Run `python scripts/analyze_combinations.py manifest.json output.json` with a local manifest
pointing at the frozen JSONL files. The manifest is intentionally not committed because it
contains paths to held-out task files. The program emits only aggregates and SHA-256 hashes,
never private task text or per-item held-out outcomes.
