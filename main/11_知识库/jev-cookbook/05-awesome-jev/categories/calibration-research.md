# Calibration & Research

Use this category for work that studies or exploits Jev's calibrated confidence — RLCD-style training, probability quality, threshold selection, uncertainty analysis.

## Submission format

```md
- [Name](URL) - Industry: one-sentence description of the Jev use case.
```

## Entries

- [decider](https://github.com/Mapika/decider) - Open models: reproduces the System One shape with a Qwen3.5-2B fine-tune that emits typed decisions with calibrated probabilities in one pass.
- [openjev](https://github.com/zhihz/openjev) - Open research: independent local preview that answers bilingual probability questions from context, questions, and candidate answers, inspired by TypeSafe Jev.
- [Parallel Constrained Decoding (Qwen2.5-1B-RLCD)](https://huggingface.co/spaces/drinkmoonshine/parallel-constrained-decoding) - Open research: RLCD-trained Qwen2.5-1B demo exploring open-source parallel constrained decoding as an alternative to Jev.
- [NanoJev](https://github.com/TianyuCodings/NanoJev) - Open replica: a 0.6B parallel decision model that returns full probability distributions with no output-token decoding, shipped with its training pipeline, weights, and dataset.
- [open-alternative-jev](https://github.com/ikermoel/open-alternative-jev) - Open alternative: runs a Jev-shaped decision model locally on your own GPU.
- [mini-jev](https://github.com/r-ms/mini-jev) - Local reproduction: implements Jev's typed-decision interface on top of a local LLM.
- [Laya](https://github.com/NandhaKishorM/laya) - Open alternative: non-autoregressive decision model that answers `choice`, `score`, and `noul` questions with RLCD-trained calibrated probabilities in a single ~35 ms forward pass, published on PyPI and Hugging Face.
- [Jev-compatible public API](https://x.com/ekzhang1/status/2100651678110515383) - Open research: a public Jev-shaped API backed by an open Qwen3.6-35B-A3B model so anyone can try the typed-decision interface.
- [kev](https://github.com/jaredpalmer/kev) - Trainable replica: a tiny Jev-like model on top of Qwen2.5-0.5B that trains and runs on a MacBook, shipped with its own research runs and evaluation scripts.
- [jevinci](https://github.com/achimala/jevinci) - Creative experiment: paints images by having Jev predict every pixel's colour in parallel, with predicted confidence deciding how wide each stroke is drawn.
- [jev-local](https://github.com/us/jev-local) - Local reproduction: Jev-compatible `POST /v1/systemone` server answering typed `Choice`/`Score`/`Noul` questions with confidence from open weights, verified as an official-SDK drop-in with temperature-fit calibration (set3 n=1316, 0.83 overall).
- [LitJev](https://github.com/zhengxuyu/litjev) - Local reproduction: a reproduction of Jev that turns any Qwen model into a fast decision model, serving the same `/v1/systemone` schema (Choice, Score, Noul) with no training and no generated answer text.
- [CUA-S1-FORMS](https://huggingface.co/cua-ai/cua-s1-forms) - Specialist decision model: a 706,048-parameter, 2.8 MB jev-like option scorer that rates FILL / CHECK / CLICK / SKIP for each form field in one parallel pass, reporting 99.7% on its own form-filling eval against Jev's 83.6% - a specialist on home turf rather than a general win.
- [jevlike](https://github.com/vinnylarouge/jevlike) - Training library: build a small model that chooses among a changing list of text options and returns one probability per option in a single pass - the base CUA-S1-FORMS was built on.
- [jevbetter](https://github.com/olanotolu/jevbetter) - Improved scorer: a stronger one-pass scorer over a variable list of text options, using a hashed n-gram encoder, rival-aware attention, and gated heads.
- [jevlike-esp32](https://github.com/david-cermak/jevlike-esp32) - Edge deployment: exports a jevlike scorer as ESP32 firmware with a C scorer and a host-side check, putting one-pass decisions on a microcontroller.
- [von](https://github.com/wfzyx/von) - Open alternative: a 395M non-autoregressive System One model that answers typed questions with calibrated probabilities in under 15 ms, positioned as a local drop-in replacement for Jev.
- [JevForge](https://github.com/zwliJay/jev-forge) - Open research: an end-to-end stack for auditable data construction, Qwen3.5-0.8B training, fixed Mind2Web and OOD evaluation, local serving, and a preliminary RLCD baseline.
- [minojev](https://github.com/zeredy879/minojev) - Open replica: a 547k-parameter model that answers runtime-defined `Choice` (2-255 candidates), `Boolean`, and `Score` questions with dev-calibrated distributions in one forward pass and zero output tokens, trained from scratch on CPU with committed datasets, predictions, and ECE results (maze 0.016).
- [Luce](https://github.com/scienthoon/luce) - Open recipe: describe the decision task in a sentence, an LLM teacher writes the training data, a LoRA + decision head on Qwen3-4B-Base answers choice/score/boolean questions with calibrated probabilities in one forward pass; trains on a 12 GB card. Reports accuracy and ECE next to Jev on identical test items (rule-generated tickets 91.1 vs 75.1, phishing 97.4 vs 62.6, GitHub issue priority 41.1 vs 37.5); browser replay demo without a GPU.
- [poorjev](https://github.com/rupeshpoojary9/poorjev) - Local reproduction: implements Jev's typed `Choice`/`Score`/`Noul` interface on commodity zero-shot NLI models and makes the confidence honest with temperature scaling and conformal abstention, shipping a reproducible calibration eval (ECE 0.170 to 0.071, cross-validated) that runs offline with no API key.
- [openJev-verdict-2.0](https://github.com/Heman10x-NGU/openJev-verdict-2.0) - Open decision engine: a calibrated 151M non-autoregressive model that reports beating both TypeSafe Jev and Laya on typed-decision benchmarks, shipped with its own test suite.
