# Development shooting replay

[Open Basic](https://nanojev-dev.tianyuchen99.chatgpt.site/) · [Predict Position](https://nanojev-dev.tianyuchen99.chatgpt.site/predict-position) · [Maze](https://nanojev-dev.tianyuchen99.chatgpt.site/side-by-side#maze) · [Snake](https://nanojev-dev.tianyuchen99.chatgpt.site/side-by-side#snake)

All four development demos use the same unified NanoJev checkpoint: `hard_lr1e5`, step **400**, SHA256 `f68c47d66998231b86b7e91b4ed5e82ae23acf104c8b7cd6d165c3ac7b7ffe1b`.

The light Basic viewer compares **Jev, NanoJev and Untuned Qwen** with original ViZDoom frames and recorded action probabilities. Play, pause, seek, change speed or advance one physical tick. Each model freezes at its actual terminal transition while the shared clock continues.

## Featured wins

The player opens on **Cross the sightline**, seed **9030060**: NanoJev moves into position and eliminates the target in **49 ticks**. Jev and Untuned Qwen reach the **286-tick deadline** without a hit. The **Play the NanoJev win** button returns to this case and starts synchronized playback.

Two additional selected wins show a target on the left (seed **9030126**, **37 ticks**) and a smaller correction to the right (seed **9030033**, **49 ticks**). Both comparison models fail in all three selected illustrations.

## Full evaluation

The score strip uses the entire frozen cohort, separately from the selected illustrations:

| Policy | Test, four ticks/action | OOD, eight ticks/action |
| --- | ---: | ---: |
| NanoJev | 128/128 | 128/128 |
| Jev | 56/128 | 59/128 |
| Untuned Qwen | 56/128 | 59/128 |

The three systems share case definitions, visible-state questions, candidate actions and the epsilon-greedy controller (`epsilon=0.1`, sampling seed `17`). Untuned Qwen uses original `Qwen/Qwen3-0.6B` weights at revision `c1899de289a04d12100db370d81485cdf75e47ca` and its vocabulary head. Displayed probabilities precede the common exploration step.

The [Predict Position demo](PREDICT_POSITION_DEMO.md) features two wins from the same checkpoint: waiting to hit a moving target and turning before the shot. Maze uses the original **50×50** challenge with local safety questions and remembered edges. Snake returns to the **12×12, 256-step** challenge: keep growing and collect food throughout the full game. The shared Snake controller filters immediate collisions and available food routes, then asks each model to choose among the remaining actions. In these restored challenges, current NanoJev completes the maze in **225 attempts** and collects **30 food items** across the full Snake game.

## Export and verify

Each exporter replays complete recorded decisions in the original environment on CPU. Every observation, reward, transition and final outcome must match the source. ViZDoom images are captured after existing one-tick calls and decoded from lossless WebP atlases to verify exact pixels. No extra simulator ticks or model calls are added.

```bash
python scripts/build_unified_basic_demo.py \
  --output runs/unified_basic_demo_export \
  --receipt runs/unified_basic_demo_export/receipt.json

python3 -m http.server 8081 --bind 127.0.0.1 --directory web
```

Open `http://127.0.0.1:8081/dev/`. Export paths must be fresh; the recorded experiment files are inputs. `--validate-only` checks sources, model identity and selected outcomes without rendering.

`scripts/check_hard_development_demo.mjs` checks all four tasks, checkpoint identity, displayed frames, recorded outcomes, controls, navigation and desktop/mobile layout. `scripts/stage_development_site.py` stages the independent development assets and requires matching checkpoint hashes across the four tasks. The hosting bundle contains viewer code and recorded media.
