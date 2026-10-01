# Evaluation protocol

Status: deterministic regression and development retrieval comparison executed. The 60-case manifest has 30 development/30 test scenarios; three test repetitions passed 30/30. This is not a live-model score or the full original release gate. 149 local tests pass. On ten development retrieval queries, semantic and lexical both achieved 9/10 top-1 and 10/10 top-3. Records: evals/results/.

## Public-data and reliability update (October 1, 2026)

The separate UCI Online Retail track processes 541,909 source invoice lines into
302 month-country aggregates. `python -m evals.retail` passes 39 numerical checks:
eight October/November measures, 29 country deltas and two total-delta
reconciliations against separate Python/Decimal source-row references. This is
an exposed fixed-data engineering check, not a new frozen model benchmark.
Source, licensing, missingness, duplicate policy and limitations are documented
in [REAL_DATA.md](REAL_DATA.md). Synthetic benchmark inputs remain unchanged.

Regression tests now cover safe dataset-loading JSON 503 responses, stopping
after expired model/retrieval/tool boundaries, non-finite budget input rejection,
SQLite quota persistence across separate processes, atomic concurrent quota
reservations, and mocked shared-quota outages. No paid provider or real Redis
service was used. Deadlines are cooperative: an in-flight model request, local
embedding call or SQL query is not forcibly interrupted, but the graph does not
start a later stage or return a verified success after expiration.

Additional local smoke checks exercised 40 mixed synthetic/retail API requests
with eight client threads and verified identical retail results after restarting
the API process. All 40 requests matched their expected terminal statuses and
had distinct request IDs; model calls and API cost were zero. These checks
cover one local process and do not establish public deployment/load capacity.

The new retail route passes frontend typecheck and production build. Browser
interaction verification was blocked by the cloud browser's local-URL access;
the earlier synthetic browser record does not validate the new page. Public
deployment, real-model action selection and baseline comparison remain omitted.

The protocol below preserves the original live benchmark goal. Real model/baseline runs remain unperformed under the zero-fee instruction. The CLI refuses live evaluation instead of fabricating a result.

## Cases and split

Create 60 cases: 30 development and 30 frozen test cases. Include all three supported tasks plus ambiguity, unsupported tasks, empty/immature data, invalid assignment and malicious retrieved text. Split by scenario/data fixture, not merely by paraphrased question, to reduce leakage. Reserve at least two independently constructed fixtures per scenario family where feasible.

Define critical cases before tuning: invalid assignment accepted as valid; invented numeric evidence; tool permissions expanded by prompt injection; budget bypass; false successful execution after tool failure. Critical cases may include non-LLM integration checks outside the 30-case task benchmark; report their separate denominator.

Freeze test inputs, expected outputs and rubric before final tuning. If test results inform a subsequent change, mark the test set as exposed and create a new held-out set before making fresh generalization claims. Do not silently delete failed cases.

## Case record

Required fields: case ID, scenario family, split, question, fixture/data hash, eligible task, expected metric contract, reference numeric fields/tolerances, required checks, expected terminal status, allowed conclusions and forbidden conclusions.

Compute references independently from the implementation under test. Do not obtain expected values by running the same SQL templates the agent uses. Synthetic generator intent is not the numeric ground truth.

## Baseline and comparison

Primary baseline: the same model, metric contracts and relevant frozen summary data, one structured answer, no dynamic tools. Document differences in information access, computation, calls and token budgets. This compares a complete analytical system with a single-pass summarizer; do not attribute any gain solely to LangGraph or autonomous planning.

Optional later ablation: fixed deterministic tool sequence with the same evidence and report model. Only this kind of more controlled comparison can help isolate the contribution of dynamic tool selection. Do not add it at the cost of deployment or the primary benchmark.

## Scoring

A whole-task pass requires correct metric/window/unit, numeric fields within declared tolerance, required validity checks, correct completion/clarification/abstention status, supported evidence references, and no prohibited causal or numerical claim. Correct-looking prose alone does not pass. A technical error or timeout counts as failure, not a removed sample.

Track separately:

- Numeric correctness and whole-task pass counts.
- Correct clarification/abstention among cases requiring it.
- Unnecessary abstention among answerable cases.
- Unsupported numerical and causal claims.
- Retrieval top-k contract hits on labeled retrieval queries.
- End-to-end latency, model-call/tool-call counts, tokens and estimated model cost.

Use deterministic scoring for numerical fields and evidence references. Manually review narrative/causal claims against a rubric, preferably with a second reviewer. If an LLM judge is used for readability, label that result separately and do not make it the authority for statistical correctness.

## Repeated runs and release gate

After selecting a spend cap, plan three repeated runs of the same frozen 30-case set to observe nondeterminism. Record per-run scores and per-case instability; repeated runs of one case are not independent new cases. Keep model identifier, prompt/configuration, temperature where supported, code SHA and data hashes fixed.

Proposed gate: >=24/30 whole-task passes in each repeated run; zero predefined critical failures; successful deployment checks. This is a release target, not a promised result. A failed gate means report what failed and continue bounded diagnosis; it does not justify falsifying or weakening the published criterion.

Small denominators limit confidence. Report counts and uncertainty, and do not describe the benchmark as enterprise or universal validation.

## Reporting artifact

Publish a small aggregate summary plus redacted/synthetic traces and representative failures. Include run date, code SHA, model, data/contracts/split hashes, rubric, baseline conditions, repeated-run results, estimated cost basis and omitted checks. Treat mock runs as plumbing checks, never as measured live-model performance.
