# Scoring & Ranking

Use this category for programs where Jev produces rubric scores, quality grades, or relevance and priority orderings that drive a downstream decision.

## Submission format

```md
- [Name](URL) - Industry: one-sentence description of the Jev use case.
```

## Entries

- [Clean Code Judge](https://github.com/frostney/clean-code-review) - Code quality: scores every file of a pull request on 31 boolean Clean Code smells plus function size and nesting, then hands the verdicts to a writing model for the review prose.
- [citation-verifier](https://github.com/MarissaFamularo/citation-verifier) - Academic publishing: checks whether each cited paper actually supports the sentence citing it, with Claude locating the quote, Jev scoring the support, and a human making the final call.
- [jev-bfs](https://github.com/komikat/jev-bfs) - Search tooling: finds link paths between English Wikipedia articles by having Jev rank each page's outgoing links while Python controls the search.
- [Jev Search](https://github.com/superagents-lab/jev-search) - Web search: uses Jev Noul judgments on result titles and snippets to rank Search1API results by relevance, with application code merging duplicate URLs and grouping lower-scoring matches separately.
- [pagegrade](https://github.com/kitze/pagegrade) - Content quality: grades page sections for clarity, writing, and on-page SEO with Jev and returns per-section scores.
- [jev-scout](https://github.com/AkashPriyadarshii/jev-scout) - Developer tooling: sub-second zero-hallucination open-source repo and crate scout using TypeSafe Jev speculative fan-out scoring.
- [jev-seo](https://github.com/AkashPriyadarshii/jev-seo) - Zero-cost, agent-first SEO & Generative Engine Optimization (GEO) search radar CLI suite and MCP server powered by DuckDuckGo and TypeSafe Jev System One.
- [JevSlop](https://github.com/TKY-27/JevSlop) - Writing quality: scores public note.com articles on eight Jev `Score` axes inside a single `systemOne` request and turns them into a 0-100 Slop Score in ordinary TypeScript.
- [SemanticSpace](https://semanticspace.dev/) - Semantic mapping: places phrases in 2D by asking Jev how strongly each one relates to two chosen axis concepts and using those scores as coordinates.
- [Supercov](https://github.com/supercorp-ai/supercov) - Code quality for coding agents: Jev answers twelve `Noul` properties per source file so the agent knows what to fix first.
- [jev.nvim](https://github.com/valentynkit/jev.nvim) - Developer tooling: Neovim plugin that splits the buffer into functions with Treesitter, scores each against a plain-language question with Jev, and ranks answers by probability in quickfix.
- [jev-reranker](https://github.com/hotchpotch/jev-reranker) - Retrieval and RAG: uses Jev Noul judgments to assess retrieved documents for relevance and usefulness as answer evidence, then sorts results and optionally filters them using a configurable threshold.
- [Jev Reranker (Rust CLI)](https://github.com/shinpr/jev-reranker) - Retrieval and RAG: JSON-in/JSON-out CLI that uses separate Jev `Noul` checks to rank candidates, apply evidence thresholds, or extract source text while keeping those decisions independent.
- [jev-skip](https://github.com/valentynkit/jev-skip) - Media: browser extension that reads the YouTube caption track and scores each segment's sponsor probability on the seek bar before the intro ends, reporting 77% of SponsorBlock's sponsor seconds caught over 23 videos at $0.0008 a video.
- [jev-semgrep](https://github.com/uehaj/jev-semgrep) - Semantic search: greps by meaning across languages, having Jev score every line against a meaning and letting meanings combine with AND, backed by a 13-file test suite.
- [nlgrep](https://github.com/YehuiTang0316/jev-nlgrep) - Developer tooling: uses Jev `Noul` judgments to find code, docs, logs, and text satisfying natural-language conditions, with a configurable probability threshold and ranked file results linked to source lines.
- [slop-grader](https://github.com/lukstei/slop-grader) - Content quality: CLI tool that grades text files against custom rulesets for AI slop, grammar, and technical doc quality using Jev scores and line-level flags, then guides an AI agent to auto-fix violations.
- [jselect](https://github.com/keltokhy/jselect) - Research and retrieval: selects source-linked evidence within a token budget using Jev Noul relevance judgments and local diversity-aware selection.
- [jsort](https://github.com/keltokhy/jsort) - Text measurement: ranks text along a plain-English criterion using pairwise Jev Noul comparisons and a locally fitted Bradley-Terry scale.
- [jgrep (kyu1204)](https://github.com/kyu1204/jgrep) - Developer tools: semantic grep that asks Jev one Noul per 5-60 line code chunk, diff hunk or CSV row (16 per request) and prints grep-style file:line hits above a threshold, so English sentences work as CI lint rules.
