# Classification & Routing

Use this category for programs where Jev sorts incoming state into categories or picks the next destination — tickets, intents, alerts, documents, or traffic.

## Submission format

```md
- [Name](URL) - Industry: one-sentence description of the Jev use case.
```

## Entries

- [Notra](https://github.com/usenotra/notra) - Marketing analytics: production GEO platform whose `NOTRA_JEV_CLASSIFIERS` flag routes brand-visibility classifiers off an LLM and onto Jev `Boolean` decisions at a 0.5 threshold, targeting 300 ms p50.
- [jev-router](https://github.com/gargpratyush/jev-router) - Developer tooling: routes Claude Code tasks to the cheapest capable model by asking Jev to choose among candidates.
- [jev-router (prismhq)](https://github.com/prismhq/jev-router) - LLM infrastructure: open-source LiteLLM-based router where a Jev decision picks which model serves each request.
- [pi-jev-router](https://github.com/mejiasd3v/pi-jev-router) - Coding agents: adds automatic per-request model routing to the Pi coding agent through Jev decisions on Vercel AI Gateway.
- [jcm-router](https://github.com/adarshmishra07/jcm-router) - Coding agents: local proxy that picks the Claude model and reasoning effort per message with a Jev decision while leaving the cached main chat untouched.
- [Jev Auto Router](https://github.com/miniLV/Jev-Auto-Router) - Coding agents: per-call Codex GPT routing where Jev makes one typed Choice over host-available (model, effort) pairs; a local Responses proxy keeps the tool loop continuous, then independent verification and Router Compass record whether the task still passed (prototype).
- [jev-agent-skill-router](https://github.com/GodsBoy/jev-agent-skill-router) - Agent infrastructure: routes agent skill selection through typed, confidence-aware Jev decisions so weak matches are declined instead of guessed.
- [typesafe-jev CV screener](https://github.com/gtaras7/typesafe-jev) - Recruiting: screens a folder of CVs with Jev typed judgments against an editable policy, re-scoring candidates for free when the policy changes.
- [Jev email intent workflow](https://github.com/GiesN/typesafe-jev-workflow) - Back-office automation: async LangGraph workflow gets a typed Jev `Choice` (`invoice` or `general`) and routes each inbound email to the matching handler.
- [unclutter](https://github.com/kitze/unclutter) - Browser tooling: WXT extension where Jev decides per page element whether it is clutter, removing it under reusable template rules.
- [typesafe-adblock](https://github.com/realZachi/typesafe-adblock) - Browser tooling: Chrome extension that asks Jev whether each DOM element is an ad, turning ad blocking into a stream of per-element typed questions.
- [DiffJury](https://github.com/raihankhan-rk/diffjury) - Code review: routes each pull request by risk with Jev before a human reviewer is assigned, doubling as a review coach.
- [HA-Jev](https://github.com/AboveColin/HA-Jev) - Smart home: Home Assistant integration that answers questions about the house as a probability, a choice, or a score.
- [secondlayer](https://github.com/ryanwaits/secondlayer) - Fault triage: self-hosted Stacks data service whose Slack gate and fault-triage paths both run on Jev decisions.
- [jev-logtriage](https://github.com/jyatesdotdev/jev-logtriage) - On-call operations: batches collapsed Loki logs into one Jev call of Noul, Score, and Choice questions, then maps answers in code to suppress, watch, review, notify, or page, with low confidence going to review and nothing executed.
- [new-api-typesafe-plugin](https://github.com/FFatTiger/new-api-plugin-typesafe) - LLM gateway: adds a native `/v1/systemone` endpoint to new-api so typed decisions sit behind the same gateway as chat models.
- [duet-agent](https://github.com/dzhng/duet-agent) - Agent harness: keeps a Jev-backed routing table for deciding which model should serve a request.
- [json-render](https://github.com/vercel-labs/json-render) - Generative UI: Vercel Labs' UI framework uses Jev in its compose path to pick which components and actions a rendered interface should contain.
- [omo-jevlike-router](https://github.com/islee23520/omo-jevlike-router) - Skill routing: shrinks the skill catalog in a system prompt with one forward pass over a frozen Qwen, routing each request Jev-style.
- [jev-cookbook](https://github.com/nexibeo/jev-cookbook) - Developer education: 15 runnable Node recipes that route support tickets, file documents, categorize bank transactions and label Gmail with Jev `Choice` and `Noul` questions, sending low-confidence answers to human review.
- [flue-jev-demo](https://github.com/matthewp/flue-jev-demo) - Agent routing: routes a Flue agent's work with Jev through Cloudflare AI Gateway.
- [sift](https://github.com/bohutang/sift) - Content labelling: Chrome extension that labels every post in an X timeline - substance, humour, chit-chat, promo, junk, or AI-written - with Jev decisions.
- [DocJev](https://github.com/jerryjliu/docjev) - Document pipelines: LlamaIndex's open-source library that classifies a document against natural-language category rules or finds the boundaries between sub-documents, with swappable OCR backends (liteparse or LlamaParse) and a benchmark harness whose 40-document pilot classified 40/40 originals correctly at about 182 ms Jev decision p50.
- [jev-fit](https://jev-fit.com) - Developer tooling: hosted fit checker that sends a pasted software idea and a fixed typed rubric to Jev in one call, where a `Choice` picks plain code, Jev or a reasoning LLM behind a `Noul` gate for non-tasks, code vetoes Jev when the idea needs images, and low confidence returns "not sure"; closed source, free page and API.
