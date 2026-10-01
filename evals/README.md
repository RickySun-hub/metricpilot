# Evaluation evidence

`python -m evals.run --mode deterministic --split test` runs three repeats of
30 frozen synthetic cases. The full manifest contains 30 development and 30
test cases; fixture seeds are disjoint, not just question paraphrases. The
committed SHA-256 file detects accidental manifest changes. Numeric references
use plain Python records independently of DuckDB SQL and the analytics tools.
Confidence intervals are also checked against statsmodels in the test suite.

The runner checks required numerical fields, terminal status, execution audit
records, evidence IDs and a maximum of five tool calls. It reports all failures,
data and source hashes, elapsed time, code SHA and working-tree dirtiness.

## Interpretation

These are deterministic controller and numerical regression checks. They do
**not** measure LLM quality, autonomous planning, live-model nondeterminism,
user impact, or superiority over a model baseline. Three deterministic repeats
are reproducibility checks, not 90 independent test cases. The synthetic test
set is small and is exposed when it informs fixes; it must not be marketed as
fresh held-out generalization after tuning against it.

No paid model requests are made. `--mode live` deliberately exits until a
separately budgeted live benchmark and single-pass baseline are implemented.
The original full release gate also needs live-model and deployment checks;
passing this regression does not satisfy that full gate.

All fixture dates, people and behavioral events are synthetic.

## Protocol clarification before first execution

Before the first agent benchmark run, expected terminal states were aligned
with the implemented contract: SRM failure retains diagnostic evidence and
returns `invalid_data`; an unnamed nonexistent experiment requires
`needs_clarification`, whereas an explicitly unknown `onboarding_*` identifier
is rejected. Questions, seeds and split were unchanged. These are transparent
interface clarifications, not post-result removal of failing cases.
The initial preflight also caught Windows CRLF conversion after hashing;
the manifest writer now saves exact UTF-8 LF bytes before calculating its hash.
Case content was unchanged and no benchmark case had executed before that fix.
