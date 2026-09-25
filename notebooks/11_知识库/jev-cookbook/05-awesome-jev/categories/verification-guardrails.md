# Verification & Guardrails

Use this category for programs where Jev gates output — verifying claims, reviewing diffs, checking generated content, or blocking unsafe agent actions before they ship.

## Submission format

```md
- [Name](URL) - Industry: one-sentence description of the Jev use case.
```

## Entries

- [is-malicious](https://github.com/luantak/is-malicious) - Software supply-chain security: asks Jev `Noul` checks about source and build files, escalates suspicious chunks for a second pass, and returns implicated files and lines before execution.
- [jev-review](https://github.com/devagrawal09/jev-review) - Software engineering: staged code-review workflow and local dashboard where Jev gates each review stage before a change advances.
- [pi-jev](https://github.com/y0usaf/pi-jev) - Agent safety: adds a measured tool-call gate to the Pi coding agent so risky calls are checked by Jev before execution.
- [OpenWork](https://github.com/different-ai/openwork) - Engineering workflow: wires Jev into its eval testkit as a verification judge so agent-produced work is gated by typed verdicts rather than a text model.
- [jev-guard](https://github.com/leepokai/jev-guard) - Agent security: prompt-injection and dangerous-action guard for Claude Code, Codex, Pi, and ACP agents, with Jev deciding what to block.
- [Foreman](https://github.com/thruwire/foreman) - Software factory: sits above Codex workers and has Jev independently judge whether an implementation is complete, its tests sufficient, or a human is needed.
- [stanley-code](https://github.com/devagrawal09/stanley-code) - Coding agents: bounded Jev workflows that keep agent judgments typed instead of free-form.
- [opencompany](https://github.com/useopencompany/opencompany) - Agent workspace: runs its approval review through Jev so workspace actions are gated by a typed decision.
- [jev-git](https://github.com/AkashPriyadarshii/jev-git) - Developer tooling: sub-second Git pre-commit & pre-push reflex gate that screens staged diffs for secrets and destructive commands using Jev.
- [pi-heed](https://github.com/Nyarlathoteppppp/pi-heed) - Runtime constraints: checks every side-effecting tool call from the Pi agent against what the user actually asked for.
- [Hunch](https://github.com/Kelbie/hunch) - Code review: plain-English rules that Jev checks code against, locally or on every pull request, with Jev picking one label per finding.
- [Abide](https://github.com/coldteadotai/abide) - Agent supervision: reads every edit a coding agent makes and has Jev flag rule violations, with the project reporting that an independent reviewer confirmed 10 of the 39 flagged edits and 11 of the 15 flagged turns.
- [fx](https://github.com/vercel-labs/fx) - Coding agent: ships a `typesafe_permission_reviewer` builtin so the agent's permission decisions run through Jev rather than an LLM call.
- [Sniff Test](https://github.com/DanRWilloughby/snifftest) - Writing: prose linter that asks Jev ten `Boolean` questions per paragraph (stacked hedges, restating closers, not-X-but-Y turns, naked cost figures) at a 0.7 threshold; CLI, pre-commit hook, GitHub Action and Claude Code skill; measured 182 ms median and 1 of 54 clean paragraphs flagged against 37 for Haiku 4.5.
- [jev-pref](https://github.com/doeixd/jev-pref) - Code review: turns the preferences in a project's AGENTS.md into `jev-pref.json` rules that Jev checks against each diff hunk, staged file set, or pull request, returning `fix_now` or advisory findings to the coding agent and a nonzero exit code on blocking ones.
- [jev-axi](https://github.com/shiftynick/jev-axi) - Agent safety: PreToolUse gate for Claude Code and Codex that has Jev score each shell command for destructiveness, exfiltration, remote code execution, and security weakening, deciding routine commands locally so nothing is sent for them, and scoring 44/44 on the 44 labeled tool calls in its repository.
- [pi-verdict](https://github.com/jesset/pi-verdict) - Agent safety: Pi permission gate where Jev answers one Choice (allow/ask/deny) per gray-zone tool call — deterministic rules settle clear cases first, deny blocks, ask escalates to a human confirm, and errors or timeouts deny; Jev is an optional backend, experimental, reached through OpenRouter or TypeSafe's direct API.
- [jev-commit](https://github.com/valentynkit/jev-commit) - Developer tooling: pre-commit hook where one Jev call judges whether the commit message matches the staged diff, flags debug leftovers and unmentioned work, and blocks only on a detected credential.
- [Blink](https://blink.review) - Code review: CLI that coding agents run after every change, with Jev checking the diff near-instantly in place of an LLM reviewer.
- [hermes-jev-approvals](https://github.com/anpicasso/hermes-jev-approvals) - Agent approvals: proof of concept that puts Jev in front of Hermes Agent's command approvals, reporting 8.7x faster decisions and 4.4x fewer prompts to the user.
- [taste-lint](https://github.com/mblode/taste-lint) - Writing / UI: CLI that uses Jev probabilities on semantic taste checks to catch AI slop in UI, copy, and agent instructions before ship; measurable rules stay local and active findings can fail a run.
- [jev-engineering](https://github.com/eugeniughelbur/jev-engineering) - Agent safety: gates coding-agent tool calls with deterministic rules first and one typed Jev call second, then publishes a rerunnable 300-call injection test showing what the gate catches and what walks past it.
