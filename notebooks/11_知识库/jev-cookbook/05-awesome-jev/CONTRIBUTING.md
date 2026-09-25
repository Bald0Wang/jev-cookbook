# Contributing to awesome-jev

Thanks for helping improve this list.

The goal is simple: collect public, concrete projects and practices built on **Jev** — TypeSafe AI's System One model for typed decisions — and make them easy to scan.

## What is Jev (the short version)

Jev is not a chat model. It takes unstructured state plus a **typed question** and returns a **typed decision**:

| Shape | Returns | Typical use |
| --- | --- | --- |
| `Choice` | one option from a set | routing, classification, tool selection |
| `Score` | a number on a defined scale | rubric grading, quality scoring, ranking |
| `Boolean` | true / false | verification gates, guardrails, policy checks |

Each answer carries a confidence score, and TypeSafe AI reports per-decision cost in the fractions of a cent rather than per-token bills. If you want the vendor framing, read [the launch post](https://typesafe.ai/blog/introducing-system-one-models-and-jev).

## What belongs here

We accept public examples such as:

- GitHub repositories
- Project homepages or public write-ups
- Blog posts and engineering posts
- X threads, Reddit discussions, Hacker News threads
- Benchmark or evaluation results against Jev

A good entry clearly shows:

- **Scenario**: what decision is being automated
- **Method**: what typed question is asked, and how the answer is gated or escalated
- **Value**: why it matters (latency, cost, accuracy, auditability)

It should also satisfy at least one of these:

- explicitly names `Jev` / `jev`
- explicitly cites TypeSafe AI's System One models
- clearly implements a typed-decision loop (typed question → typed answer + confidence → accept / reject / escalate)

If a project is merely a classifier, router, or LLM judge that happens to resemble the pattern but does not use Jev, it probably does **not** belong here.

## What does not belong here

Please do not submit:

- Generic classifiers, routers, or decision agents with no Jev involvement
- Generic LLM-as-judge harnesses that never touch Jev
- Pure conceptual discussion or launch-hype commentary
- Vendor marketing copy with no concrete usage
- Private, dead, or inaccessible sources
- Multi-paragraph explanations inside category files
- Repositories that only *describe* a Jev integration without implementing one
- Repositories whose documentation outweighs their code while claiming to be tools

For AI-assisted work, project depth, and submission-rate rules, see [AI-assisted work, and bulk submissions](#ai-assisted-work-and-bulk-submissions).

## Core rules

### 1. One entry, one category — no cross-posting

Every entry lives in exactly one category file. When a project straddles multiple categories, choose the one closest to its direct application domain and commit only there. Never add the same entry to two category files.

If you're torn between two categories, ask: "What decision is Jev actually making?" — that's the category.

### 2. Keep every entry to one sentence

Every entry must stay on a single bullet line.

### 3. Classify by the decision, not the toolchain

Choose the category based on what Jev decides, not on whether the project is an "agent", a "pipeline", or a "platform".

### 4. Prefer clarity over cleverness

If a reader cannot understand the use case in one quick pass, rewrite it.

### 5. Prefer fewer, stronger entries

High-signal curation is more important than volume. A list of forty vague prototypes is worth less than five entries with numbers in them.

### 6. Depth over surface area

An entry has to describe something that **runs**, not something that is described. Before submitting, make sure:

- the repository performs the typed decision it claims — a real Jev request carrying typed questions, and a parsed answer coming back;
- there is at least one runnable check that would fail if the logic broke — a test, an example with expected output, or a public demo;
- any number in your entry (accuracy, latency, cost, volume) is traceable to the linked page.

If a project is mostly prompt documents, skills, or templates, that is fine — but submit and describe it as such. Do not present a prompt pack as a tool.

## AI-assisted work, and bulk submissions

AI-assisted development is welcome here. Plenty of listed projects were built with coding agents, and that is not a reason to exclude them.

### Rule: do not submit bulk drops of AI-generated projects

This is a rule, not a preference, and it is the one rule in this document that will get a submission **queued rather than reviewed**.

Bursts of AI-generated repositories are the fastest way to bury the signal this list exists to collect. So:

- **One project per pull request, one pull request per project.** Do not bundle siblings.
- **At most three entries per author per rolling seven days**, however many repositories exist. Entries beyond that are queued to the next cycle — not reviewed early, and not rejected on sight.
- **A batch counts as one submission.** Repositories sharing a scaffold, a README template, an `AGENTS.md` / `CLAUDE.md` / `STATE.md` set, or a single-commit history are treated as one project family. Eight siblings released on one afternoon do not become eight entries.
- **A shared release date is a risk signal, not momentum.** Projects released together are reviewed individually and are not credited to each other.
- **Undisclosed AI generation pauses the whole batch.** If a submission turns out to have been generated without disclosure, every pending entry from that author waits until the disclosure is made. The disclosure costs nothing; the concealment costs the queue position.

None of this restricts AI-written code. It restricts the pattern in which volume stands in for depth.

### Disclose AI generation

If a project was generated or substantially written by an AI system, say so in the pull request, and preferably in the repository. Disclosure is not a penalty — it sets the review bar honestly, and it tells maintainers to check depth rather than authorship.

Disclosure is usually unnecessary anyway once the pattern is obvious: a shared scaffold, a single bulk commit, documents outweighing code. Being caught that way costs more trust than saying so up front would have.

### Do not ship a scaffold as evidence

One `AGENTS.md` / `CLAUDE.md` / `STATE.md` / `CHANGELOG.md` template reused across several repositories does not make any of them more complete. Neither does a README that documents features the code does not implement.

### The depth bar in practice

Maintainers may accept a project with a caveat when the code is real but depth is unproven, and may decline one member of a batch while accepting its siblings. A reviewer will check:

- Does the code perform the decision it claims, or only describe it?
- Is there at least one runnable check — a test, an example with expected output, or a public demo?
- If the repository is mostly prompt documents, is it submitted and described as a skill rather than as a tool?
- Do the numbers in the entry trace back to the linked page?

## Entry format

Use this exact format:

```md
- [Name](URL) - Industry: one-sentence description of the Jev use case.
```

### Good examples

```md
- [TicketTriage](https://example.com) - Support operations: asks Jev to classify 40k inbound tickets per day into a fixed queue taxonomy, escalating anything below 0.8 confidence to a human.
- [DiffGate](https://example.com) - Code review: gates agent-authored pull requests with a Jev `Boolean` check against repository conventions, blocking merges on a false verdict.
- [RubricGrader](https://example.com) - Education: scores short-answer submissions with a Jev `Score` against a locked rubric, replacing a per-submission LLM call at a fraction of the cost.
```

Why these work:

- names the decision being automated
- names the typed shape (`Choice` / `Score` / `Boolean`)
- states the gate or escalation rule
- gives a concrete consequence

### Weak examples

```md
- [CoolRouter](https://example.com) - AI routing for agents.
```

Why weak:

- No concrete scenario
- No typed decision
- No method or threshold
- Too vague to classify

## Where to place entries

Add entries to exactly one of these category files:

- `categories/classification-routing.md` — sorting state into categories or destinations
- `categories/verification-guardrails.md` — gating output, verifying claims, blocking unsafe actions
- `categories/scoring-ranking.md` — rubric scores, quality grades, relevance and priority orderings
- `categories/agent-decisions.md` — the decision step inside an agentic loop
- `categories/data-labeling-curation.md` — annotating, filtering, deduplicating, triaging data at scale
- `categories/evaluation-benchmarking.md` — judging model or system outputs, eval harnesses, regression gates
- `categories/calibration-research.md` — calibrated confidence, probability quality, RLCD-style work
- `categories/infra-sdks-integrations.md` — SDKs, wrappers, gateways, framework adapters, local ports
- `categories/related-practices-discussions.md` — threads, interviews, articles (no standalone repo)

Open categories, seeded when evidence appears:

- `categories/content-moderation.md` — policy and abuse decisions
- `categories/compliance-legal.md` — regulatory, contract, policy-conformance decisions
- `categories/game-simulation.md` — decisions inside games and simulations
- `categories/scientific-pipelines.md` — experiment gating, hypothesis triage, result validation

Decision flow:

```
Is there a standalone repo or project page?
  ├─ No  → related-practices-discussions.md
  └─ Yes → What does Jev actually decide?
            ├─ Sorts/destines state          → classification-routing.md
            ├─ Gates or verifies output      → verification-guardrails.md
            ├─ Produces a score or ranking   → scoring-ranking.md
            ├─ Picks the next agent action   → agent-decisions.md
            ├─ Labels or curates data        → data-labeling-curation.md
            ├─ Judges a model/system output  → evaluation-benchmarking.md
            ├─ Studies confidence itself     → calibration-research.md
            └─ Tooling with no decision of its own → infra-sdks-integrations.md
```

`README.md` is auto-generated from category files — never edit it directly. After editing category files, run:

```bash
python3 scripts/build-readme.py
```

## Style guidance

- Keep wording concrete.
- Name the industry or domain explicitly.
- Describe the decision and its gate, not just the tool.
- Include a number when the source provides one (accuracy, latency, cost, volume).
- Do not add long commentary under entries.

## Pull request checklist

Before submitting, confirm:

- [ ] The source is public and accessible.
- [ ] The entry is one sentence.
- [ ] Jev is explicitly used (or a documented port/derivative).
- [ ] The entry explains scenario + typed decision + value.
- [ ] The category reflects the direct Jev application domain.
- [ ] The entry was added to a category file, not to `README.md`.
- [ ] The wording is concise and easy to scan.
- [ ] The repository actually performs the decision (not a README-only claim).
- [ ] There is at least one runnable check, or the entry says plainly that there is not.
- [ ] Any number in the entry traces back to the linked page.
- [ ] AI generation is disclosed, if it applies.
- [ ] This is not more than my third entry in a rolling seven-day window.
- [ ] These repositories are not a batch sharing one scaffold, README template, or single-commit history — a batch counts as one submission, not several.
