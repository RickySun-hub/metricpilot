# Resume claims and evidence requirements

**These are future templates, not current accomplishments. Do not copy them to a resume until the corresponding work is implemented, understood and verified.** Add verified facts to the canonical master resume before using them in tailored applications.

## Suggested project heading

MetricPilot — Product Analytics Agent | Python, LangGraph, FastAPI, DuckDB, Next.js

Attach real public demo and repository links only when those deliverables exist. A repository containing plans is not a deployed application.

## Three-bullet version

- Built and deployed a product analytics agent supporting three investigation workflows across [N] synthetic events, by integrating LangGraph tool calling, validated SQL, and Python statistical analysis through FastAPI and Next.js.
- Achieved [A/B] task-level passes on a frozen [B]-case benchmark, compared with [C/B] for a single-pass LLM baseline, by grounding responses in retrieved metric definitions and validating numerical claims against tool outputs.
- Prevented unsupported experiment recommendations in [D/E] predefined invalid-data cases, by enforcing sample-ratio checks, evidence validation, and explicit abstention paths.

If repeated runs differ, specify the aggregation and range or use an exact identified run; do not cherry-pick the best run. Report the actual pass count, even when below the target.

## Optional replacement bullet

- Delivered interactive analytical reports at [P50] median and [P95] p95 end-to-end latency across [R] live runs, by bounding tool calls and query execution, at an estimated model API cost of [$X] per completed request.

Define warm/cold conditions, sample size and cost basis. Do not substitute an unloaded local timing for hosted latency or API cost for total operating cost.

## Evidence ledger to fill after implementation

| Claim | Required record | Current status |
| --- | --- | --- |
| Built and deployed | Code SHA, public URL, successful live task traces | Not implemented |
| N synthetic events | Generation command, row count, dataset hash | Not generated |
| A/B benchmark passes | Frozen split/rubric hashes and actual run summary | Not evaluated |
| Baseline comparison | Same model/config record and disclosed differences | Not evaluated |
| D/E invalid cases | Predefined cases and observed terminal statuses | Not evaluated |
| Latency and model cost | Hosted run records, timing definition and pricing basis | Not measured |

## Skills to add only after use and understanding

Applied AI: LangGraph, LLM tool calling, structured outputs, RAG, agent evaluation.

Backend & Data: FastAPI, Pydantic, DuckDB, SQL.

Engineering: Docker, GitHub Actions, API deployment.

Do not claim pgvector, unrestricted text-to-SQL, enterprise reliability, real customer adoption, analyst hours saved or business uplift unless independently supported by completed work. Synthetic scale is not production traffic.
