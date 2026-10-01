# Working agreement

## Current scope

This is an implemented portfolio project. The owner subsequently authorized AI-assisted implementation, replacing the original hand-built plan. Planning, mocks, deterministic benchmarks, real-model runs and deployment are different evidence levels.

For AI assistance: explain concepts and review bounded changes when requested. Do not turn a request for planning, hints, or a review into an unrequested complete implementation. Never describe generated code as personally authored by the owner without a truthful account of its use.

## Implementation workflow

1. Pick one milestone and identify its acceptance criteria.
2. Implement the smallest component that satisfies those criteria.
3. Verify the original analytical case and meaningful failure boundaries.
4. Record the actual command, result, commit, and remaining limitation in the issue.
5. Close the issue only after its acceptance criteria have been met.

Preserve unrelated work. Do not commit credentials, private user records, browser state, generated bulk datasets, or machine-local artifacts. Use synthetic data for the public demo. Paid model calls or cloud provisioning need a chosen budget and stop condition before execution.

## Evidence

- Mark future functionality as planned until verified.
- Do not invent accuracy, users, savings, latency, business uplift, or deployment status.
- Keep development and frozen benchmark cases separate; a failed frozen test is not permission to tune against it silently.
- Mock tests establish plumbing only; they do not establish live model performance.
- Attach task-specific checks rather than adding tests that only mirror implementation.
- Report numerical effect changes in percentage points where appropriate.

## Repository layout to add during implementation

The following directories are implemented:

```text
backend/           FastAPI, schemas, agent graph, retrieval and analytical tools
frontend/          Next.js demo
data/              generator and small reference fixtures; bulk output ignored
contracts/         versioned metric and experiment definitions
tests/             independent checks for analytical and agent behavior
evals/             case manifests, runners, rubric and measured summaries
docs/              specifications, build plan and evidence requirements
```

Do not add a dependency or service solely to list it on a resume. Lock dependencies when a working environment exists, and document commands only after running them.
