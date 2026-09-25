# How the harness is put together

One page on the parts that are easy to get wrong. The README says what is measured;
this says how, and which invariants the code refuses to break.

## The canonical record

`jevbench/tasks.py` holds one dataclass. A task is an `id`, a `family`, the `state`
the model reads, a typed `question` (`noul` | `choice` | `score`), the exact ordered
`labels` the model may answer with, the `expected` label, a `split`, an optional
paraphrase `group`, and `provenance`.

`validate()` refuses a record whose expected value is not in its own label set, and
refuses a structured state carrying a key called `expected`, `label`, `ground_truth`
or `answer_key`. That is a cheap guard against the classic accident of shipping the
answer inside the question.

`dataset_hash()` hashes canonical records order-independently, so a reordered file is
the same dataset and an edited one is not. `datasets/manifest.json` pins one hash per
split, frozen before any model saw any item.

## Adapters

An adapter takes a task and returns a `DecisionResult`: a probability map over the
exact label set, the resolved model identity, HTTP status, latency, token usage and the
raw body. It never retries, never falls back to another model, and never repairs a bad
answer.

Mapping to exact labels, per question type:

- `noul` - the model returns P(yes) as a single number; we store `{"yes": p, "no": 1-p}`.
  A boolean is rejected: `True` is not a probability.
- `choice` - the model's own distribution over the option keys, used as it comes. If the
  chosen option is not in the label set, the answer is invalid.
- `score` - the model's distribution over level indices. Accuracy uses **argmax**;
  the probability-weighted expected level is reported separately as MAE. Those are two
  different predictions and `[0.4, 0.2, 0.4]` is exactly where they disagree.

`gradio_space` and `local_openjev` talk to interfaces whose option field carries no
description, so the rubric is appended to the instruction text. Every adapter therefore
sends the same rubric; a test asserts it for all four native flavours. `gradio_space`
refuses a label containing the demo form's comma delimiter rather than quietly rewriting
the label set.

`openai_compat` asks for `{"probabilities": {...}}` under a strict JSON schema and marks
the result `verbalized`. Providers disagree about which request knobs exist, so
`--request-options` can add a field or, with a `null` value, remove one - and whatever it
did is written into the run manifest, so a published number names its settings.

`needle_local` (v1.1) runs Cactus Needle 3 in-process. Needle is a function-calling
model: it returns a tool call, not a distribution, so the result carries **no**
probability map (`probs_source` says why) and no Brier or ECE is computed for it. We
never turn its single confidence scalar into a distribution. Default mode: one tool whose
one argument is the typed answer (enum / boolean / integer enum). A suppressed call is
an abstention and scores as wrong. With `--request-options '{"choice_mode": "tools"}'`
every option of a choice question becomes its own tool and the called tool is the
answer; that mode was added after the frozen easy-tier run and is always reported beside
the default mode, never instead of it.

## The budget

`jevbench/budget.py` is a `flock`-serialized append-only ledger. `reserve()` writes the
worst-case cost before the request leaves; `settle()` writes the real one after.

The properties worth knowing:

- The cap is read from the ledger's own first `cap` row, so a later run cannot raise it
  by passing a bigger `--cap-usd`.
- An unsettled reservation stays charged. If a process dies mid-request, the next run
  sees the money as spent rather than as never having happened.
- A settlement larger than its reservation raises instead of being recorded - if that
  happens, an assumption is wrong and stopping is the correct behaviour.
- Non-finite or negative amounts are rejected, not coerced.

## The runner

Serial by construction. For each task: reserve, call, write the raw request/response to
its own file created exclusively, settle the real or unknown cost, score, append the
record and `fsync` it. A completed paid call is on disk before the next one starts.

`--delay-s` paces requests, which is how we behave on somebody else's free demo.

The run stops on HTTP 401, 403 or 429, or after three consecutive infrastructure
errors. The remaining tasks stay unattempted. They are never scored as wrong: a model
that was rate-limited did not get the answers wrong, it did not get asked.

The raw directory and the results file must live outside the repository; the runner
raises if either would land inside it. That is the guard that keeps private items out
of a public commit even when someone passes the wrong flag in a hurry.

## Cost

`cost_usd` is `null` unless both tariffs are known and the provider returned usage, in
which case it is `derived_usage_times_tariff`. A route with no billable account carries
an explicit basis (`no_billable_account_public_endpoint`, `local_cpu_no_provider_tariff`,
`flat_rate_subscription_no_per_token_tariff`) and still reports `null`. The reservation
that was held for an unknown cost is recorded separately as `reserved_usd` and is never
published as a price.

## Aggregation

`jevbench/summarize.py` recomputes every published field from the per-item records
through an allowlist. `public_export()` deliberately ignores the caller's summary and
re-derives everything, so an injected key cannot ride out with it; a test proves that a
private item's text cannot appear in an export.

Empty samples return `null` with `n = 0`. A metric with nothing behind it is not a zero,
and a model with a partial run is marked incomplete and must not share a rank with a
complete one.

## Tests

`python -m unittest discover -s tests -v` covers: interrupted-reservation replay and the
non-finite guard; the distribution validator; argmax-versus-expected-value on ordinal
questions; the private-export guard; Brier/ECE and the failure denominator; agreement
versus both-correct; the rubric reaching every adapter; the Gradio delimiter refusal;
the list-flavour answer-shape checks; the local adapter having no tariff; the
rate-limit stop preserving the partial run; and the public suite's paraphrase pairs
agreeing on their label.
