# Architecture specification

Status: implemented with a default static recorded-results showcase and optional local deterministic execution. Real-provider samples and development evaluations are recorded; the final primary paired frozen-test attempt stopped after 10 of 180 planned responses, with 7 automatic passes, 3 withheld and 170 unrun. Previous failed attempts remain separate historical records. Consult [the current RAG implementation](RAG_IMPLEMENTATION.md) and exact [evaluation artifacts](../evals/results/) for measured scope. Public paid execution, shared hosted quotas and permanent deployment are separate unverified concerns.

## Responsibilities

| Component | Owns | Must not do |
| --- | --- | --- |
| Frontend | Input, execution status, charts, evidence and failure UI | Hold provider keys or enforce the only budget control |
| FastAPI | Validation, request identity, concurrency, limits, deadlines | Trust browser-supplied run costs or permissions |
| Retriever | Select versioned metric contracts and return document IDs | Treat retrieved instructions as executable policy |
| Agent | Choose approved tools using the question and existing results | Execute arbitrary SQL, Python or shell commands |
| Analytical tools | Deterministic SQL/statistics and typed evidence | Guess unsupported metric definitions |
| Report validator | Check references, numeric values, direction and units | Assert that all semantic/causal claims are automatically verified |

## Agent state

State fields include: request ID, normalized question, selected metric ID/version, data version, task type, validated time windows, optional segment, retrieved document IDs, tool results, error records, remaining model/tool budgets, and terminal status.

Terminal statuses: completed, needs_clarification, unsupported, invalid_data, verification_failed, budget_exceeded, timed_out, provider_error. A terminal error must not be shown as an analytical success.

## Approved analytical tools

- `compare_metric`: allowlisted metric ID and two complete non-overlapping windows.
- `analyze_funnel`: allowlisted funnel ID and mature signup cohorts.
- `decompose_change`: metric ID, two windows and channel OR device.
- `check_experiment`: known experiment ID and the predeclared outcome/horizon.

Tool inputs are validated enums, IDs, dates and bounded parameters. SQL is compiled from maintained templates; show the template and bound parameters in the evidence drawer. Database files are immutable/read-only at runtime. No external files, extension installation, network reads, user-supplied table names or arbitrary SQL are allowed.

## Evidence record

Each tool invocation should return: evidence ID, tool/version, normalized arguments, dataset hash, contract version, SQL template/bound parameters where relevant, result fields with units, warnings, start/end timestamps and validation status.

Reports represent numerical claims as structured records with evidence ID, field path, displayed value, unit and rounding rule. Application code checks those fields before display. Only selected aggregates and synthetic reference documents should be sent to the model; raw event rows are unnecessary.

## Agent versus fixed workflow

Use deterministic entry validation and final claim validation. Between them, permit the model to select analytical tools based on observed evidence: investigate segments after a change, inspect the funnel after a completion decline, or stop when assignment validity fails. If every run follows the same fixed sequence, document it as a workflow rather than exaggerating autonomy.

## Resource controls

Implemented limits: five analytical tool calls, six model invocations, no automatic retries, bounded context and a 45-second graph deadline checked between actions. Provider timeout: 12 seconds. A synchronous tool is not forcibly cancelled by the graph deadline; the hosting function timeout is a separate limit. Default selection is deterministic and visibly labeled.

Enforce an estimated per-request token budget and a shared durable daily spending counter before admitting work. API provider billing may lag; do not present estimated costs as exact invoices. Implement the counter and concurrency handling before exposing unrestricted public model calls. No external analytical writes are part of the MVP.

## Deployment choices still separate

- Python and JavaScript dependencies are pinned; verify the target host against the repository toolchain.
- Current live records use a pinned model identifier and recorded pricing basis. Any model change needs a new evaluation.
- Start with local development storage; choose durable hosted accounting for the public demo before launch.
- Keep agent code separate from existing ProofRound production code. Reuse knowledge and suitable patterns, not private configuration or user data.

Official references: [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents).

## Recorded dashboard

The Next.js pages share a question/results/evidence layout. The default is a checked-in projection of actual recorded reports, with no API requests on load. Source records retain their date, execution mode, dataset, model, citations, exact SQL and limitations. A separate evaluation view keeps numerical, retrieval, development and frozen-test evidence distinct and does not label unattempted cases as failures.

`app/data/showcase.json` is generated by `scripts/build-showcase-data.py`, which reads only existing artifact JSON and strips operational budget/provider fields. Static export can serve the showcase without FastAPI. The explicit localhost-only workspace retains deterministic requests; public hosting does not enable paid calls.

Current live generation uses model-selected verified facts and server-rendered numerical values. Earlier saved reports preserve their original schema and provenance. Numeric/citation checks never claim complete semantic entailment.
