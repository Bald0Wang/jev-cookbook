# NanoJev success showcase

**A nano replica of Jev.** These four navigation examples show NanoJev and Jev reaching the goal while Untuned Qwen reaches the step limit. The same outcome holds for both greedy and T=1 sampling.

The videos show a **selected success showcase**. We checked the existing 40-map cohort and chose the first two eligible test maps and first two eligible OOD maps in its original order. A map is eligible only when NanoJev and Jev both succeed and Untuned Qwen fails under **both** controllers. There are 11 eligible test maps and 6 eligible OOD maps, out of 20 in each split.

| Split | Episode ID | NanoJev steps, greedy / sample | Jev steps, greedy / sample | Untuned Qwen steps, greedy / sample |
|---|---|---:|---:|---:|
| Test | `navigation_v3:949e76c0d9a26606cb3373b6` | 2 / 4, success | 2 / 4, success | 32 / 32, step limit |
| Test | `navigation_v3:450cb63d0bbd444de9ae877c` | 3 / 3, success | 3 / 3, success | 32 / 32, step limit |
| OOD | `navigation_v3:06b38a6ade0754de661819ad` | 3 / 3, success | 3 / 3, success | 72 / 72, step limit |
| OOD | `navigation_v3:53d0165e341321ab56b81c37` | 3 / 3, success | 3 / 3, success | 72 / 72, step limit |

Playback is synchronized by environment step. A panel stays at the goal after success; playback speed does not compare model latency.

The **full 40-map benchmark is separate**: all three systems, both controllers, and all 240 successful and failed episodes remain in the published results. The maps, source trajectories, model settings, random seed, and aggregate scores were not changed to create this showcase. These examples illustrate behavior and do not replace the full results.

[Selection and per-example outcomes](nanojev_showcase_selection.json) · [Full comparison data](nanojev_comparison_public.json) · [240-episode verification](nanojev_comparison_verification.json)
