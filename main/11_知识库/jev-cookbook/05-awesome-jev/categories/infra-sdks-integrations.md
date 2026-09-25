# Infra / SDKs / Integrations

Use this category for ecosystem tooling built around Jev — SDKs, wrappers, gateways, framework adapters, evaluation scaffolds, local ports.

## Submission format

```md
- [Name](URL) - Industry: one-sentence description of the Jev use case.
```

## Entries

- [eve](https://github.com/vercel/eve) - Agent frameworks: Vercel's eve engine ships Jev as the default evaluation model (`typesafe-ai/jev`) in its experimental evaluate path.
- [AI CLI](https://github.com/vercel-labs/ai-cli) - Developer tooling: Vercel Labs CLI that can run Jev as the evaluation model for its `evaluate` command.
- [jev-mcp (jkudish)](https://github.com/jkudish/jev-mcp) - MCP ecosystem: proof-of-concept MCP server that puts Jev claim verification, content screening, and candidate ranking behind standard MCP tools.
- [jev-mcp (blakestone-x)](https://github.com/blakestone-x/jev-mcp) - MCP ecosystem: MCP server exposing Jev classify, score, check, match, and screen as tools for any agent, with confidence on every answer.
- [zio-typesafe-ai](https://github.com/jamesward/zio-typesafe-ai) - Scala ecosystem: ZIO client for TypeSafe AI with a typed DSL over Jev decisions.
- [laya-mlx](https://github.com/mizorewww/laya-mlx) - Local runtime: independent MLX port of the Laya checkpoints that runs typed decisions natively on Apple Silicon — 13.4 ms median end-to-end per short English decision, 7.4 ms with the multilingual checkpoint, and zero output tokens, with no PyTorch, Transformers runtime, or cloud API.
- [TypeSafe AI Swift SDK](https://github.com/alterhq/typesafe-sdk-swift) - Swift ecosystem: dependency-free Swift 6 client for Jev Choice, Score, and Noul questions with strict concurrency, configurable authentication and retries, and offline transport tests.
- [laravel-typesafe-jev](https://github.com/Butochnikov/laravel-typesafe-jev) - PHP ecosystem: unofficial Laravel integration for Jev with typed responses, async requests, scoped dependency injection, and testing fakes.
- [advocaat](https://github.com/pithings/advocaat) - Data tooling: small type-safe client for asking Jev questions about a dataset.
- [jevclient](https://pypi.org/project/jevclient/) - Python ecosystem: async client for Jev published on PyPI.
- [LlamaIndex Jev](https://github.com/WiktorB2004/llama-index-jev) - Retrieval / RAG: unofficial LlamaIndex adapter where Jev `Score`s each retrieved passage and `Choice`/`Noul` selects the query engine, with nfcorpus nDCG@5 0.340→0.396 at about $0.0003/query.
- [safer-with-jev](https://github.com/andrelandgraf/safer-with-jev) - Cloud infrastructure: Neon Function proxy for the Neon AI Gateway that routes decisions with Jev.
- [typesafe-ai/skills](https://github.com/typesafe-ai/skills) - Official tooling: installable agent skills package (`npx skills add typesafe-ai/skills`) that teaches agents the Jev workflow.
- [Smithers](https://github.com/smithersai/smithers) - Agent frameworks: TypeScript workflow framework with a Jev session checker wired into its workflows.
- [skillbox](https://github.com/kitze/skillbox) - Skills infrastructure: self-hosted versioned skills library that adds optional Jev recommendations using your own TypeSafe or Gateway key.
- [Jevbridge](https://github.com/tacticocc/Jevbridge) - Agent bridges: ACP and MCP adapter that exposes Jev typed decisions to Codex, Claude, Grok, and other LLMs.
- [jev (Elixir)](https://github.com/dannote/jev) - Elixir ecosystem: GenServer client that replies with Jev's answer so callers can pattern match on it directly.
- [jev-go](https://github.com/Stumble/jev-go) - Go ecosystem: community Go SDK for Jev.
- [jev-cli](https://github.com/tumf/jev-cli) - Developer tooling: small dependency-free CLI for Jev.
- [decide-mcp](https://github.com/dakdevs/decide-mcp) - MCP ecosystem: configurable decision server with percentage scores and bias-profile routing on top of Jev.
- [typesafe-jev-examples](https://github.com/rajivkuriakose/typesafe-jev-examples) - Starter examples: worked ticket-triage and reranking examples runnable through OpenRouter without an early-access key, shipped with their own sample data and Makefile.
- [ai-python](https://github.com/vercel-labs/ai-python) - Python ecosystem: the official Vercel AI SDK for Python carries Jev through its evaluation operation and Gateway examples.
- [Cline plugins](https://github.com/cline/plugins) - Coding agents: Cline's official plugin collection includes a Jev-driven browser plugin (`jev-browser`), so Jev arrives as a first-class Cline capability.
- [hono-jev-router](https://github.com/yusukebe/hono-jev-router) - Web frameworks: Hono middleware that routes HTTP requests by meaning rather than by method and path, deciding with Jev.
- [rotom](https://github.com/RyanKung/rotom) - Local gateways: OpenAI- and Anthropic-compatible API gateway that carries Jev through its model catalog and evaluation path.
- [Jev AI](https://jev-ai.pro) - Developer tooling: public Jev playground and API that puts typed `Choice`, `Score` and Yes/No questions to the model about pasted text - ticket triage, moderation, review scoring - and returns a parsed answer with a confidence value in about 0.5 s per decision.
- [jevql](https://github.com/kylemclaren/jevql) - Data tooling: psql-shaped CLI and Go/TypeScript/Python SDKs that run plain SQL on a vanilla Postgres (no extension) and then ask Jev Noul, Choice, or Score questions about each surviving row so the client can apply `jev()` filters, `jev_prob` sorts, and `jev_choice` groups.
- [sqlite-jev](https://github.com/mgaitan/sqlite-jev) - SQLite ecosystem: loadable C extension and Python package that expose Jev Noul, Choice, and Score judgments as SQL functions and batched virtual-table queries with confidence results.
- [jevkit](https://github.com/ariel-frischer/jevkit) - Developer tooling: Rust CLI that validates `Choice`/`Score`/`Noul` question sets with 13 offline lint rules before any Jev call, then sends the canonical wire payload and prints parsed, confidence-bearing JSON answers to stdout using exit code 2 to reject a billed-but-useless request.
- [jev-use](https://github.com/shitianfang/jev-use) - MCP ecosystem: Claude Code / Codex / pi plugin (MCP server + library, native pi extension) that hands agent steps needing no text output to Jev as typed judgments — untypeable and generation-needing questions are rejected before the call, low-confidence answers come back flagged as priors, and a fail-open PreToolUse gate can only deny or ask.
- [huncho](https://github.com/edgardcham/huncho) - TypeScript ecosystem: dependency-free SDK that turns Jev `Noul`, `Choice` and `Score` answers into named decisions with `enter`/`exit` thresholds (hysteresis), nested decision trees settled in one call, a JSONL journal, replay of a threshold change over recorded answers with no inference, and Brier/reliability calibration, over TypeSafe direct, OpenRouter or Vercel AI Gateway.
- [jev-experiments](https://github.com/dabit3/jev-experiments) - Demo collection: 22 latency-focused Jev applications built by Devin, each with its own README and testing notes, spanning shell guards, log sentinels, instant search, reranking, and voice turn-taking.
- [ruby_decision_model](https://github.com/obie/ruby_decision_model) - Ruby ecosystem: client for decision models such as Jev, so Ruby applications can put typed questions directly to the model.
- [s1_ruby](https://github.com/innocentdiaz/s1_ruby) - Ruby ecosystem: makes System One measurement, and the collapse that follows it, a Ruby primitive, with a TypeSafe provider behind its own spec suite.
- [JarvisCore](https://github.com/Prescott-Data/jarviscore-framework) - Agent frameworks: Python multi-agent runtime that ships Jev natively from 1.12, where agents ask typed `Choice`, `Score` and `Noul` questions through a decision client separate from the text model, the Kernel picks a specialist subagent by `Choice`, and each retrieved RAG passage is withheld from the generating model when its prompt-injection `Noul` exceeds 0.70.
- [hunch](https://github.com/carldaws/hunch) - Ruby ecosystem: turns judgment calls into control flow — `if Hunch.likely?("fraudulent", given: order)` reads like plain Ruby but branches on a typed Jev answer, with `pick` for Choice, `rate` for Score, and graded predicates from `possibly?` to `definitely?`.
- [Early experimentation using Jev to rethink harness UX](https://www.elvex.com/blog/early-experimentation-using-jev-to-rethink-harness-ux) - Harness integration: an agent platform wires Jev into its LLM harness as a callable tool for search, approvals and context, reporting 2,000 expense reports categorized in 20 seconds for five cents.
- [jev-mcp (burnigtm)](https://github.com/burnigtm/jev-mcp) - MCP ecosystem: server that puts Jev into the coding loop for Cursor, Codex, and any MCP client, with 20 test files behind it.
- [jev-skill-suggester](https://github.com/win4r/jev-skill-suggester) - Coding agents: recommends which installed skills apply to a request, keeping the recommendation bounded and letting Jev decide.
- [grok-bot-jev](https://github.com/Bodila51/grok-bot-jev) - Agent bridges: connects Jev to Grok Bot as a cheap decision layer, with usage gates, a skill template, and worked examples.
- [jev-architect](https://github.com/karanb192/jev-architect) - Design skill: finds, designs, and evaluates Jev decision loops, packaged as a skill with references on decision design and delivery.
- [Building a Harness with Jev](https://www.langchain.com/blog/building-a-harness-with-jev) - Framework guide: LangChain's walkthrough of wiring Jev into an agent harness as the decision layer, from a team that then published its own evaluation of Jev as a judge.
- [openrouter-jev-mcp](https://github.com/ctmx/openrouter-jev-mcp) - MCP ecosystem: Python decision gateway and stdio MCP server exposing TypeSafe's Jev model through OpenRouter's alpha decisions endpoint.
