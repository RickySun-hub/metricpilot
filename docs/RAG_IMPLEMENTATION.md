# Grounded generation and bounded spending

## What now runs

Synthetic live mode performs semantic retrieval, model-selected allowlisted tools,
then a separate real LLM answer call. Retail live mode uses a fixed SQL workflow
and the same answer call. Model inputs contain retrieved contract text, source
IDs, executed SQL and actual structured results, and a fact catalog checked
against those results. No model-generated SQL is ever executed.

The model writes short qualitative claims with contract IDs, evidence IDs and
selected fact IDs. Strict output schemas constrain source identifiers and prose.
The server renders each selected fact with its checked label, value and unit,
and derives that fact's source citation from immutable evidence metadata. The
model never supplies displayed numerical values. Unknown citations, literal or
unsupported worded quantities, altered facts and malformed output fail closed.
The UI exposes source links, exact SQL and retrieved definitions.

The current generation schema is 3.2. The earlier inline-placeholder format proved
brittle in actual model runs; the preserved first benchmark stopped after
systemic rejections. Its failures were not relabeled as successful abstentions.

An explicit abstention returns no claims. Failed validation withholds the model's
text and values. Invalid experiment assignments never expose an estimated effect
in the fact catalog. Common causal/rollout overclaims are rejected. These bounded
checks are **not a semantic entailment proof**: all generated interpretation
still requires separate semantic review. The numeric-validation guarantee
applies to server-rendered fact values and explicit quantity checks, not every
possible mathematical implication of natural language.

Deterministic mode uses no paid calls and preserves its labeled templates.

## Cost controls

- Model pinned to `gpt-4.1-mini-2025-04-14`; no fallback, retries or paid embeddings.
- Standard prices checked October 2, 2026: $0.40/M input tokens and $1.60/M output
  tokens, without relying on cached-input discounts. [Official model pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
- Each whole investigation reserves $0.02 before provider access. No refunds.
- Each prospective call bounds input by complete request UTF-8 bytes plus framing
  overhead and uses a fixed maximum completion length. Cumulative measured cost
  plus the next call's upper bound must fit $0.015. At most six model calls.
- A failed call, missing usage or transport uncertainty retains its conservative
  upper-bound charge. Returned token usage is accounted before output parsing.
- Lifetime default and hard maximum are $5, daily default $1. Lower configured
  caps are honored. Invalid configurations fail closed.
- Local default ledger is the ignored `artifacts/local/metricpilot-budget-v1.sqlite`.
  Keep this same persistent file for all runs. Prior temporary history migrates
  without resetting spend; ambiguous histories stop further calls.
- Local runs leave both Redis variables unset. If either is configured, local
  and public callers use shared Redis; partial/empty configuration fails closed.
- Public mode requires durable shared Redis admission. Independent machines or
  independently chosen stores cannot collectively enforce one budget.

Reservation totals bound admission; they are not provider invoices. Response and
evaluation metadata separately report observed tokens, estimated token charges,
unknown-usage calls and reserved allowances. Reconcile with the provider billing
record before claiming exact money spent.

## Verification boundaries

Offline tests exercise actual SQL/retrieval and mocked model responses, including
invented citations, invented/raw numbers, altered or nonfinite facts, failed/late
calls, rate/cost limits, invalid experiments and explicit abstention. Mock calls
are never described as a real model benchmark. The paired evaluator compares
this analytical system with one report-generation call on fixed precomputed SQL
summaries; any information/computation advantage must be disclosed.

Actual provider runs require secure approved credentials, the explicit paid CLI
gate and an enabled live configuration. A complete real-provider funnel smoke
and the later six-response schema-3.1 development smoke have now been recorded.
The latter passed all automatic checks for paired activation, valid-experiment
and real-retail answers; it is a small exposed development check, not a full
benchmark or fresh held-out result. See [development record](../evals/results/live-development-v3_1-20261002.json) and [preserved failed initial benchmark](../evals/results/live-synthetic-20261002.json).
Qualitative narrative scoring, cloud browser interaction and public deployment
must be reported separately from automated numerical/reference checks.

## Final measured outcome

The final stable synthetic run stopped after three consecutive narrative-guard
rejections: **7 automatic passes among 10 attempted responses, 170 unrun of 180
planned**. The agent passed 3/5 attempted responses; the baseline passed 4/5.
These small, early-stopped counts do not establish model accuracy or baseline
superiority. The public-retail and adversarial supplements were execution-blocked
with **zero recorded responses** against eight and twelve planned, respectively.
The earlier successful development examples remain separately labeled.

Withholding means no generated conclusion or finding cards are presented as
verified; the executed SQL evidence remains available for inspection. The
deterministic mode still computes approved analytics without model calls.
Conservative prose checks can reject otherwise useful answers, and passed fact
checks do not prove every interpretation. This is a functional bounded RAG
research demo, **not a reliable general-purpose analyst**.

Cumulative returned-token usage estimates $0.1386484 at pinned uncached prices.
Recorded unknown-usage allowances and two interrupted admissions raise the
conservative estimate to $0.1836196. The persistent ledger reserved **$1.88** of
$5; that is an admission allowance, not the provider bill. Exact invoiced cost
was not fetched. All paid work is stopped.

See [final synthetic result](../evals/results/live-synthetic-v3-20261002.json),
[blocked retail record](../evals/results/live-retail-v3-20261002.json),
[blocked adversarial record](../evals/results/live-adversarial-v3-20261002.json),
and [deduplicated cost accounting](../evals/results/cost-accounting-20261002.json).
