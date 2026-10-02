# Implementation and evidence status

MetricPilot is a functional bounded RAG research demo, not a reliable general-purpose
analyst. The owner requested AI-assisted implementation, later authorized real
model work within a $5 total API ceiling, and approved an MIT-licensed recorded
showcase. Owner understanding and interview readiness are separate claims.

| Milestone | Implemented and verified | Remaining / limit |
| --- | --- | --- |
| Data/contracts | 12,000 synthetic users / 50,504 events; UCI public-retail aggregates and attribution | Fixed windows and narrow supported scope |
| Analytical tools | Parameterized SQL, ordered funnel, exact decomposition, SRM and Newcombe checks | No arbitrary SQL or general database access |
| Graph/generation | Actual model tool selection, retrieved definitions, cited qualitative generation, verified fact rendering | Conservative guards can withhold useful answers; no semantic entailment proof |
| Retrieval | CPU MiniLM embeddings; measured lexical comparison | Small exposed retrieval evaluation |
| UI/evidence | Recorded dashboard, charts, SQL/results, citations, visible failure and mode labels | Fresh browser interaction remains unverified; localhost was blocked |
| Evaluation | Deterministic 3×30/30 checks; actual development and partial paired model runs | Final full release gate not passed |
| Deployment | Historical temporary Vercel demonstration, expired recorded claim window | No new public paid-API deployment or verified permanent URL |
| Delivery | Runnable source, evidence, honest failure history, MIT first-party licensing | Third-party data/model licenses remain separate |

## Real-provider results

The first full paired attempt stopped after 9/180 planned responses, with three
automatic passes. Schema development was recorded rather than silently replacing
failures. The later six-response schema-3.1 development run passed 6/6 automatic
checks across activation, valid-experiment uncertainty and actual retail data.
Independent AI review checked those six narratives and 94 finding mappings; this
was not human review.

The final schema-3.2 synthetic run stopped after **10/180 planned responses**:
**7 automatic passes, 3 withheld, 170 unrun**. Agent: 3/5 attempted; baseline:
4/5. These are small early-stopped counts, not a completed full benchmark or
proof of baseline superiority. The final retail and adversarial supplements
were execution-blocked with **zero recorded responses** against eight and twelve
planned. The successful retail development sample is not substituted for them.

Withheld model narratives are not shown as verified conclusions; their executed
SQL evidence remains inspectable. Deterministic mode still computes the approved
analytics without API calls. The public showcase has three recorded scenarios
over two workflow families; local deterministic input supports the four
synthetic presets plus the separate retail workflow.

## Cost and stop state

Paid work is stopped. Returned-token usage estimates **$0.1386484** at pinned
uncached prices. Conservative recorded unknown-usage allowances and two admitted
requests without surviving responses bring the estimate to **$0.1836196**.
The unchanged persistent ledger reserved **$1.88** of the $5 authorization.
Reservations are not the provider invoice; exact billed spending was not fetched.

## Verification

The final backend test suite passed **336 tests**; final dashboard checks are
recorded with its build artifacts. Deterministic synthetic checks
passed 30/30 in three repetitions; the public-data numerical check passed 39/39.
TypeScript and production build checks passed. Cloud-browser localhost navigation
was denied, so offline React/state/source-link checks are not described as browser
verification. Hosted Redis remains mock-tested; public live mode requires it.

## Historical public-data extension

The October 1 extension audited 541,909 licensed UCI invoice lines and bundles
only month-country aggregates. It retains documented duplicate rows and missing
customer IDs for this non-customer-level metric, compares complete October and
November 2011 gross positive sales, and reconciles 29 country deltas with separate
Python/Decimal source-row references. It does not infer visits, activation,
randomized assignments or causal effects from invoices.

See [evaluation protocol and terminal results](EVALUATION.md),
[grounding and budget design](RAG_IMPLEMENTATION.md), [public-data details](REAL_DATA.md),
and [deduplicated accounting](../evals/results/cost-accounting-20261002.json).
