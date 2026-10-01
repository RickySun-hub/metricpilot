# Build plan

**Original learning roadmap, followed by AI-assisted implementation at the owner's request.** The zero-cost scope implements data, tools, graph, local semantic retrieval, reports, evaluation and UI. Real LLM calls/baseline and owner interview-readiness remain unverified. Deployment status is in DEPLOYMENT.md. The original day estimates below are learning estimates, not actual implementation time or evidence of work done by hand.

## M1 — Data and metric contracts (3 days)

**Build:** one fixed-seed synthetic SaaS dataset targeting roughly 50,000 events; four tables; data dictionary; activation/funnel/experiment definitions; three scenario fixtures. Include a channel-mix change, invalid experiment assignment proportions, and a valid experiment with an interval crossing zero. Label all data synthetic.

**Understand:** analysis unit, numerator, denominator, cohort maturity, observation window, and timestamp semantics. Event rate and user conversion rate answer different questions.

**Verify:** hand-check a tiny fixture with independently calculated expected results. Check unique users, event references, valid chronology, complete windows, and assignment consistency. The generator's intended scenario does not replace a reference calculation on the generated data.

**Done when:** data can be reproduced; contracts and independently computed fixture answers agree; generation command and data hash are recorded. No real user data is accessed.

## M2 — Deterministic analytical tools (3 days)

**Build:** parameterized SQL and Python functions for metric comparison, ordered funnel counts, channel/device decomposition, and a fixed-horizon user-level experiment check. Start without an LLM.

**Understand:** tool correctness is the foundation of agent correctness. A mix shift can change an overall rate without a within-group decline. A confidence interval describes uncertainty under assumptions; descriptive decomposition does not establish a cause.

**Verify:** compare outputs against independent calculations. Cover empty windows, zero denominators, duplicate identities, invalid assignments, immature cohorts, and overlapping comparison periods. SRM or contaminated assignment must prevent a rollout recommendation.

**Done when:** supported tools return structured results and evidence records; invalid inputs return typed errors; meaningful reference checks pass.

## M3 — Tool calling and bounded agent (3 days)

**Build:** a minimal explicit model/tool/result loop, then the equivalent LangGraph. Define typed state, argument validation, tool history, error routing, and terminal statuses. Use a maximum of five analytical tool calls per request and finite model-call/retry limits.

**Understand:** a tool call is a proposed action, not automatic authority. The agent chooses from permitted tools; application code validates and executes. State is an ordinary structured record.

**Verify:** the three scenarios follow appropriate different paths. Invalid arguments do not execute. Tool failures do not become success reports. Exhausted budgets terminate cleanly. Use mocks first; run bounded live model checks only after selecting a spend budget.

**Done when:** the graph, tool permissions, and stopping behavior can be explained without reading framework code; mock and live evidence are distinguished.

## M4 — Retrieval and clarification (2 days)

**Build:** 10–15 short versioned metric/data/experiment contracts, embedding retrieval with document IDs, and handling for ambiguous or unsupported questions. Start with in-memory similarity search; compare with keyword retrieval.

**Understand:** semantic similarity is not semantic correctness. Retrieved content is reference material, not an instruction source. RAG supplies definitions while analytical tools supply numbers.

**Verify:** expected contracts appear in top-k for a set of labeled queries and synonyms. Undefined “engagement” triggers clarification. A malicious instruction embedded in a retrieved document cannot expand permissions.

**Done when:** retrieval results are versioned and auditable; ambiguity handling is visible; retrieval quality is measured on actual labeled queries.

## M5 — Evidence reports and UI (3 days)

**Build:** Next.js input and sample questions, charts, metric definitions, evidence drawer, generated structured report, and numerical-claim validation. Each numerical claim has a result ID and field path.

**Understand:** correct calculations can still be summarized incorrectly. A citation must support the statement, not merely exist. Show tool execution records rather than private model reasoning.

**Verify:** report values, signs, units and references match tool results. Contradictory values fail validation. Manually inspect causal wording and narrow-screen usability. Errors and insufficient evidence have honest UI states.

**Done when:** all three supported workflows can be inspected locally from question through evidence; invalid reports are not presented as verified answers.

## M6 — Evaluation and baseline (4 days)

**Build:** 60 cases, split into 30 development and 30 frozen test cases by underlying scenario; independent reference calculations; single-pass baseline; numerical/task rubric; latency/token/cost logging.

**Understand:** evaluate completed analytical tasks, not whether prose sounds good. Small benchmarks have substantial uncertainty. A comparison with a baseline measures a specific intervention, not universal superiority.

**Verify:** freeze splits before final tuning. Run the protocol in EVALUATION.md and publish failures as well as successes. Suggested release gate: at least 24/30 full-task passes per planned repeated test run and no predefined critical failures; record actual results even if the gate is missed.

**Done when:** results are reproducible from pinned inputs/configuration and include real run records; no invented metrics or silently revised test cases.

## M7 — Public deployment (3 days)

**Build:** hosted Next.js frontend and containerized FastAPI backend with a bundled read-only data snapshot; server-side credentials, validation, per-client limits, global daily budget, concurrency limit, deadlines and explicit saved-run mode.

**Understand:** frontend controls cannot enforce backend safety or spending limits. Read-only analytics still requires input and resource boundaries. A saved response is not a live model run.

**Verify:** complete all three tasks from a public URL in an incognito browser. Verify restart behavior, timeouts, exhausted budgets and empty results. Inspect frontend assets/network responses for credential leakage. Record the exact deployed commit and environment.

**Done when:** a hiring manager can use the live demo without registration and see accurate execution-mode labels; the hosting cost and stop conditions are configured and documented.

## M8 — Delivery and interview readiness (2 days)

**Build:** final README with verified startup commands, a public evaluation summary, a 60-second video, an architecture explanation and a failure walkthrough. Replace “planned” only for verified functionality.

**Understand:** explain why a graph is useful, where deterministic logic belongs, how data errors affect conclusions, and why uncertainty limits recommendations.

**Verify:** explain without notes why this needs an agent; why arbitrary SQL is excluded; how mix shifts affect rates; why experiment significance is insufficient for shipping; and how unsupported conclusions are detected. Independently walk through one successful and one failed trace.

**Done when:** actual demo/repository/video links work; documentation matches the deployed commit; all resume claims have an evidence record. The owner can explain and reproduce every retained component.

## Scope control

Cut extra charts, UI polish and optional dimensions before cutting analytical validation, evaluation or public deployment. Do not add autonomous database writes, arbitrary code execution, multi-agent orchestration, private-data uploads, fine-tuning or paid cloud resources as an unreviewed scope expansion.
