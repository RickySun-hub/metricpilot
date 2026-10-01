# MetricPilot

**Investigate product metrics. Inspect the evidence. Respect uncertainty.**

MetricPilot is an implemented analytics application with a Next.js interface, FastAPI backend, DuckDB tools, local semantic retrieval, and a bounded LangGraph controller. It investigates activation changes, ordered funnels, and user-level A/B experiments on **12,000 synthetic users and 50,504 synthetic events**.

**Execution boundary:** this zero-cost release runs real SQL and statistical calculations with a deterministic controller. An optional OpenAI action selector is implemented and covered by mocked safety tests, but **no real LLM calls, model-quality benchmark, or LLM-baseline comparison have been performed**. Deterministic mode is visibly labeled; it is not presented as a live LLM agent.

[Public demo — temporary, pending owner claim](https://temporary-quick-fiddle-x0gi9g1.vercel.app) · [Build issues](https://github.com/RickySun-hub/metricpilot/issues) · [Verification scope](docs/EVALUATION.md)

The anonymous demo has been verified publicly, but expires unless the owner claims it. It is not yet a permanent resume/demo URL. No registration or API key is needed to use deterministic mode.

## What it does

| Question | Behavior | Evidence |
| --- | --- | --- |
| Why did activation change? | Compare mature signup cohorts and decompose channel/device mix versus within-group change | Counts, rates, exact decomposition, SQL and bound parameters |
| Where did the practice funnel change? | Compare signup → start → completion with ordered, session-matched events | User-level step counts and conditional rates |
| Is onboarding_srm trustworthy? | Detect sample ratio mismatch and withhold effect interpretation | Assignment counts, SRM p-value and validity status |
| Should we ship onboarding_valid? | Report a Newcombe 95% score interval and constrain the recommendation | Intent-to-treat counts, effect and uncertainty |

The demo uses fixed September 1–8 and September 8–15, 2026 signup cohorts, fully observed by September 30. “The two weeks” means these demo cohorts, not the current calendar. Unsupported metrics/windows are rejected or clarified.

On the default snapshot, activation falls from **56.2167% to 30.5%**. Inspect the exact mix/within-group contributions in the report. These are synthetic observations and an accounting identity, not real business impact or causal findings.

## Architecture

```mermaid
flowchart TD
    UI[Next.js interface] --> API[FastAPI validation]
    API --> B{Supported question?}
    B -->|No| C[Clarify or abstain]
    B -->|Yes| R[Local MiniLM semantic retrieval]
    R --> G[LangGraph controller]
    G --> S{Execution mode}
    S -->|Default: zero API cost| D[Deterministic action selection]
    S -->|Optional: disabled publicly| L[OpenAI structured action selection]
    D --> T[Validated DuckDB SQL / Python statistics]
    L --> T
    T --> E[Evidence records]
    E --> G
    G --> V[Numeric validation and templated report]
    V --> UI
```

The optional model branch chooses approved actions; it never supplies executable SQL. Application code validates arguments, budgets and termination. Numerical claims come from tool evidence and are checked against result fields. Narrative uses deterministic templates, deliberately limiting flexibility and hallucination exposure.

Semantic retrieval uses a pinned, quantized **all-MiniLM-L6-v2** model with CPU ONNX Runtime, masked mean pooling and cosine similarity. There is no paid embedding endpoint or hosted vector database. Upstream weights are attributed in [models/README.md](models/README.md).

## Measured verification

- **56 tests passed locally**: independent references for SQL, Wilson/Newcombe checks against statsmodels, SRM checks against SciPy, dataset integrity, API behavior, retrieval/tokenizer parity and mocked live safety.
- **30/30 deterministic regression cases passed in each of three repeated runs.** The 60-case manifest has 30 development/30 test cases with distinct scenario seeds. This is bounded synthetic regression, not live LLM accuracy.
- On **10 labeled development retrieval queries**, semantic and lexical retrieval both achieved **9/10 top-1 and 10/10 top-3** contract hits. This does not establish semantic superiority.
- Desktop **1440×1000** and mobile **390×844** flows checked with Playwright: four scenarios, evidence expansion, no page errors or horizontal overflow.

Measured records and omissions: [deterministic results](evals/results/deterministic.json), [retrieval comparison](evals/results/retrieval.json), [protocol](docs/EVALUATION.md). Local checks do not automatically establish GitHub CI or public deployment success.

## Run locally

Prerequisites: **Python 3.12**, **Node.js 22+**. Never put credentials in commands or tracked files.

```bash
git clone https://github.com/RickySun-hub/metricpilot.git
cd metricpilot
python -m venv .venv
```

Activate `.venv` (`.venv\Scripts\Activate.ps1` on PowerShell; `source .venv/bin/activate` on macOS/Linux), then:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
npm ci
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
```

In a second terminal set `METRICPILOT_API_URL=http://127.0.0.1:8000` and run `npm run dev`. PowerShell:

```powershell
$env:METRICPILOT_API_URL='http://127.0.0.1:8000'
npm run dev -- --hostname 127.0.0.1
```

Open `http://127.0.0.1:3000`; API docs: `http://127.0.0.1:8000/api/docs`. The repo includes the compressed synthetic snapshot and pinned local embedding assets. Reproduce inputs:

```bash
python -m backend.data
python -m backend.download_embedding_model
```

The second command downloads public pretrained assets, not paid inference. Run checks:

```bash
python -m pytest -q
python -m evals.run --mode deterministic --split test --repeats 3
python -m evals.retrieval
npm run typecheck
npm run build
```

`npm run build` exports a static frontend to `out/`. Production also needs FastAPI; serving only `out/` does not provide analytics. A backend Dockerfile is included; Docker execution has not been verified locally.

## Optional LLM integration

The default/public configuration keeps `METRICPILOT_ENABLE_LIVE=0`. Live mode is not required for the working analytics demo. Later activation requires an approved server-side key, explicit budget and the [deployment controls](docs/DEPLOYMENT.md). Public live mode additionally requires shared durable quota storage.

The code uses a fixed GPT-4.1-mini snapshot, structured actions, finite calls, duplicate-call rejection, conservative cost preflight and evidence-only reports. These have mocked tests, not real-provider verification. Hosted Redis accounting is also unverified. Live benchmark/baseline are future work; the evaluation CLI refuses to invent them.

## Repository guide

```text
app/                Next.js input, reports, charts and evidence
api/index.py        FastAPI health, analysis and evaluation
backend/            Data, SQL tools, statistics, retrieval and graph
contracts/          Versioned definitions
data/               Synthetic snapshot and checksum manifest
models/minilm/      Pinned ONNX weights, tokenizer and attribution
tests/              Numerical, API, retrieval and mocked safety checks
evals/              Independent references, case manifest and results
docs/               Architecture, deployment, demo and claims guidance
```

## Limitations / next work

- Synthetic data, fixed windows and narrow task vocabulary; not a general database copilot.
- Deterministic public execution; real LLM selection and baseline remain unverified.
- Validated SQL templates, not unrestricted text-to-SQL.
- Descriptive decomposition, not causal inference.
- One user-level binary outcome at a fixed horizon; no sequential testing or multiple-comparison adjustment.
- No measured business uplift, time savings, real adoption or enterprise-scale reliability.
- Constrained report templates; no open-ended narrative analysis.

Next: separately authorize real-model evaluation, compare a baseline with disclosed information differences, obtain independent review, then expand scope based on failures.

## Ownership

Implemented with **AI assistance at the repository owner's request**. This does not imply the owner independently hand-authored every component or has already demonstrated understanding. Before interview claims, work through [the explanation guide](docs/INTERVIEW_GUIDE.md) and reproduce the checks. Pretrained weights belong to their upstream authors; no model training/fine-tuning is claimed.
