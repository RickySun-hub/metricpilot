# Evaluation protocol

Status: planned. Cases, runs and numerical results do not yet exist.

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
