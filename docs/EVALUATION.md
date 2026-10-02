# Evaluation protocol

Prior recorded status (October 1, 2026): deterministic regression and development retrieval comparison executed. The 60-case manifest has 30 development/30 test scenarios; three test repetitions passed 30/30. This is not a live-model score or the full original release gate. 149 local tests pass. On ten development retrieval queries, semantic and lexical both achieved 9/10 top-1 and 10/10 top-3. Records: evals/results/.

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

The protocol below preserves the original live benchmark goal. The earlier zero-fee phase did not execute a real model/baseline benchmark. The October 2 implementation below enables explicitly authorized paid evaluation under the newer $5 total ceiling; implementation or mocked tests alone do not establish a live-model result.

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


## Paired live evaluator implementation (October 2, 2026)

`python -m evals.run --mode live --allow-paid --split test --repeats 3`
implements the original 30-case, three-repeat paired protocol without changing
`cases.json` or its frozen SHA-256. Execution requires `--allow-paid`, working
provider/live configuration, and a readable persistent budget ledger. The runner
never enables live mode, supplies credentials, changes caps, or resets ledgers.
The hard lifetime reservation ceiling is $5, shared with smoke and supplemental
runs. Every answerable system request reserves $0.02 before provider access;
the gateway bounds one request to $0.015 using pinned token rates and accounts
uncertain failed-call usage conservatively. The full paired protocol plans at
most 180 request reservations ($3.60), before zero-call boundary savings. These
are conservative reservation bounds, not a promise of actual billed cost.

Development smoke example:

```
python -m evals.run --mode live --allow-paid --split dev --family metric --limit 1 --repeats 1
```

Family/limit filters and fewer repeats are labeled `partial_smoke`; they cannot
satisfy the full benchmark gate. `--family` is repeatable. New live reports use
timestamped files under `evals/results/`; `--output` selects another unused
path. Existing live result and review-template files are not overwritten.
Deterministic smoke runs support the same synthetic family/limit filters and
remain zero-call regression checks.

### Baseline and paired execution

Each case uses the same generated dataset, pinned model, retrieved contracts,
and numerical-report verifier in both arms. The baseline executes a fixed
rule-based selection of approved analytical tools, then makes exactly one
structured answer call with the resulting SQL evidence and verified facts. It
performs no model-directed action selection. It receives precomputed arithmetic
and correct tool selection as an information/computation advantage. This is a
complete-system versus fixed-preprocessing summarizer comparison, not evidence
isolating the benefit of LangGraph, RAG, or autonomous planning. Both arms retain
the same explicit deterministic zero-call clarification/unsupported boundary
policy. Retail uses the same full fact vocabulary in the two arms. Agent/baseline
request order alternates by case/repeat. Both arms apply the same end-to-end
forty-five-second cooperative deadline; in-flight calls cannot be forcibly
interrupted.

### Evidence and scoring

Every system response is checkpointed immediately, preserving the complete
backend-returned structured response, observed claims/citations, SQL/tool
records, dataset hash, source/contract/protocol hashes, revision, working-tree
dirtiness, latency, model calls, token usage, estimated cost, and conservative
budget snapshots. Credential-shaped fields are redacted; HTTP headers,
credentials and environment dumps are never collected. Provider payloads are
retained only where exposed by the backend. Failed calls without reliable usage
are identified separately and retain conservative accounting. If a budget
boundary is hit, later planned entries are marked `not_run_budget_stop`; they
remain failures in the original denominator instead of being silently removed.
A provider error, or recorded HTTP 401/403/429, also stops every later request
without automatic retry; those entries are `not_run_provider_stop`, with the
triggering safe status, case and system recorded in `stop_reason`. Both stop
types are excluded from attempted-request and latency/usage summaries, while
remaining in planned pass-rate denominators. Three consecutive generated
`verification_failed` responses also halt the batch with
`stop_reason.kind = systemic_grounding_failure`; a completed/invalid-data answer
with generated claims resets that streak, while zero-call boundary responses do
not. This guardrail avoids spending the full suite on a systemic schema or
grounding problem.

Automated scoring checks independent numerical references, terminal status,
actual evidence/citation resolution, fact-to-evidence links, and rendered
numeric values. A rejected generated answer is a quality failure; it is not
reported as an accepted safety bypass. Unsupported accepted claims, invalid
assignment accepted as valid, disallowed tools, and analytical execution on
unsupported boundaries are reported as distinct critical checks.

A passing automatic result leaves `whole_task_pass` unset pending semantic
review. A separate `.review.json` template identifies each generated answer by
case/repeat/system and response SHA-256, with five rubric items for human review:
metric/window/unit, supported numerical claims, validity/uncertainty, causal
restraint, and answering the actual question. A second reviewer is preferable.
The runner never labels mechanical checks as a full release gate, and does not
claim that three repeats yield independent samples. The synthetic cases are
explicitly marked exposed because they have already informed engineering work.

### Separate public-data and adversarial tracks

```
python -m evals.run --mode live --allow-paid --track retail --repeats 1
python -m evals.run --mode live --allow-paid --track adversarial --repeats 1
```

The retail supplement pairs three fixed public-data questions (sales change,
country contributions, and data-quality exclusions) and one unsupported
conversion prompt. Numerical checks use the existing separate Python/Decimal
source-row reference; this is an exposed fixed-data supplement, not part of the
frozen 30-case denominator. The baseline includes the same relevant retail
facts as the agent.

The adversarial supplement pairs three malicious-retrieval probes (credential
exfiltration instructions, fabricated numbers/causality/citations, and tool or
budget expansion instructions), plus unsupported SQL/metric and ambiguous
engagement prompts. The injection hook appends adversarial text to an otherwise
retrieved contract for the individual sequential request and restores retrieval
afterward, including on failure. Its cases and hashes are separate from the
frozen manifest. The suite checks resulting tool permissions, numerical evidence,
and generated citations; qualitative prompt-injection resistance still requires
review. These tests do not exhaust adversarial attacks.

The supplemental evaluator plumbing is covered by offline mocked providers.
Successful retail and retrieved-instruction development examples are separate
from the final supplements, which were execution-blocked with no recorded
responses. Keep those omissions, deployment limits and semantic-review scope explicit.


### Pre-rerun evidence and local configuration (October 2, 2026)

The first measured live attempt stopped after nine arm responses, with three
automatic passes. These failed results are retained; they are not a completed
three-repeat benchmark. Subsequent answer-schema development reached version
3.1, followed by a six-response development smoke that passed all six automatic
checks. These observations have informed changes, so they remain exposed
development evidence. At that historical source freeze the full version-two rerun was pending; its
later stop and the final version-three outcome are recorded below. No fresh
held-out or whole-task semantic claim follows from the smoke.
Reports now record the answer schema version and explicit standard
`service_tier: default` alongside model and pricing metadata.

For parity with the local API setup, the live CLI reads an existing `.env.local`
only after the explicit `--allow-paid` flag gate. Existing process environment
values take precedence (`override=False`). The loader does not create or edit
credentials, enable live mode by default, change budget caps, or reset accounting.
Deterministic runs and live attempts without opt-in do not invoke this loader.

### Final bounded schema-3.2 run

The schema-3.1 full-v2 run retained an interrupted 30-response checkpoint and
resumed with unchanged analytic/evaluator/input hashes. It later stopped on
systemic SRM-language guard rejections after **45/180 planned responses**, with
**39 automatic passes** and **135 unrun responses**. The terminal resumed
artifact preserves the original response hashes and latencies; the incomplete
intermediate checkpoint is local-only, not a second benchmark result.

A captured model answer correctly described a significant assignment imbalance
from a failed SRM test, but the blanket significance guard rejected it. Schema
3.2 permits only narrow SRM allocation-significance phrasing when a selected,
unscaled p-value is below the predefined threshold, the cited experiment is
invalid, and the SRM contract is cited. Negation, treatment-effect significance,
missing references, and scaled-probability loopholes remain blocked. Independent
AI code review and offline replay approved this correction; this is not human
semantic review or a new held-out claim.

The final planned protocol kept every frozen case and repeat. Its admission bound is
150 paid synthetic requests plus six public-retail and six adversarial requests;
38 remaining responses are deterministic zero-call boundaries. At $0.02 per
admission, the added maximum is **$3.24**, bringing existing lifetime reservations
of **$1.66** to at most **$4.90** under the absolute $5 cap. There will be no further
full restarts to pursue perfect scores. Failures and any stop condition will be
retained and reported. Terminal outcomes are recorded in the next section; no additional paid calls or restarts remain active.


### Terminal results and stop decision (October 2, 2026)

- Final schema-3.2 synthetic run: **10/180 responses attempted, 7 automatic
  passes, 3 withheld and 170 unrun**. Agent: 3/5 attempted; baseline: 4/5.
  Three consecutive narrative guard failures stopped the run. Source hashes
  remained unchanged. This is not a completed three-repeat benchmark, a 70%
  general accuracy result, or evidence of baseline superiority.
- Independent retail supplement: **0 recorded outputs / 8 planned**. A first
  admission reserved $0.02, but no response or provider usage record survived
  the execution interruption. Actual provider-call count/cost is unknown.
- Independent adversarial supplement: **0 recorded outputs / 12 planned**;
  it did not start. Neither blocked supplement has a passing model result.
- Earlier six-response schema-3.1 development check: 6/6 automatic passes.
  Independent AI review verified all six narratives, 94 finding mappings and
  17 claim-source mappings. This is explicitly not human review and cannot
  replace unrun final benchmark cases.

The final run retains every failure and original planned denominator. Refusals
on answerable questions count as quality failures, even when the safety guard
correctly prevents unverified prose from being shown. The predefined full release
gate has **not passed**. No more paid tuning or full restarts were undertaken.

Final artifacts: [synthetic](../evals/results/live-synthetic-v3-20261002.json),
[retail execution-blocked](../evals/results/live-retail-v3-20261002.json),
[adversarial execution-blocked](../evals/results/live-adversarial-v3-20261002.json).
The terminal resumed-v2 failure remains published for transparency; its incomplete
intermediate checkpoint is retained locally only and is not another scored run.

Cumulative accounting deduplicates copied and restored request IDs: 92 recorded
admitted requests, 205 recorded model attempts, 263,117 returned input tokens
and 20,876 returned output tokens. Returned-usage estimate: **$0.1386484**.
Including recorded uncertain usage: **$0.1436196**. Including both unrecorded
admissions at their full reserved allowances: **$0.1836196**. The persistent
ledger has **94 admissions / $1.88 reserved**, with $3.12 remaining under the
absolute $5 authorization. Reserved allowance is not actual invoiced spend;
provider invoices and cached-token discounts were not retrieved.
[Full reconciliation](../evals/results/cost-accounting-20261002.json).
