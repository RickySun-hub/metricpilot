# Data and metric contracts

Status: specification only. No dataset has been generated.

## Synthetic data model

Use fixed seeds and a declared UTC cutoff. Public dates and events are synthetic. Maintain one channel and one device classification per user; define acquisition channel at signup to avoid retroactive reclassification.

| Table | Key | Required fields |
| --- | --- | --- |
| users | user_id | signup_at, acquisition_channel, signup_device |
| events | event_id | user_id, event_at, event_type, practice_session_id when applicable |
| experiment_assignments | experiment_id + user_id | variant, assigned_at, expected allocation |
| metric_daily | date + metric_id + segment | numerator, denominator, contract_version |

Store numerator and denominator in aggregate tables; never average daily percentages to obtain a pooled rate. Detect duplicate events and enforce referential integrity in validation even if the analytical store does not enforce it.

## Activation

Activation = unique users who complete their first practice within seven days of signup / eligible signed-up users in the cohort. Include only users with seven fully observable days by the data cutoff. The cohort period refers to signup date, not completion date. Use half-open timestamp intervals consistently and document exact day-boundary semantics.

## Funnel

Signup → practice start → practice completion, using unique users and the same mature signup cohort. Require timestamps in order and completion within the defined seven-day horizon. Define and display both signup-to-step conversion and conditional step conversion. A completion from a different session must not be mistaken for completing the selected session.

## Rate change decomposition

For segments g, define r_t = sum(w_tg * r_tg), with weights based on eligible users and rates based on the same metric contract.

Use an explicitly documented exact symmetric decomposition when all segment rates are defined:

- Mix contribution: sum((w_1g - w_0g) * (r_1g + r_0g) / 2).
- Within-segment contribution: sum((r_1g - r_0g) * (w_1g + w_0g) / 2).

Their sum equals r_1 - r_0. Report contributions in percentage points. If a segment has no denominator in one period, do not impute a rate silently; return an incomplete-comparison warning and abstain from this decomposition or apply a separately specified regrouping rule.

This is an accounting decomposition, not evidence that channel or device caused a change. Do not search many segments and then present the largest change as a confirmed discovery.

## Experiment contract

One experiment, user-level randomization, one predeclared binary outcome: practice completion within seven days of assignment. Assignment precedes eligible outcome events; use intent-to-treat denominators and a fixed mature observation horizon. Enforce one assignment per user and no cross-variant contamination.

Before analysis, define allocation, outcome, practical effect threshold, sample-size assumptions and analysis end time. Check observed assignment counts against expected allocation with a declared SRM test and threshold. SRM failure or invalid assignments blocks an experiment recommendation; it does not prove which logging mechanism failed.

Report variant counts, rates, absolute effect in percentage points and a 95% interval for the difference. Prefer a documented score-based/Newcombe interval; compare against a trusted implementation and hand-check fixtures. Avoid an unqualified Wald interval for small/sparse groups. If implementation supports only sufficiently populated groups, encode and disclose that eligibility rule.

An interval crossing zero means the result does not resolve the effect under this analysis; it is not proof of no effect. An interval excluding zero does not itself establish business value or resolve unmeasured guardrails. Do not use event counts as independent observations when randomization is at the user level.

## Reference scenarios

1. Channel mix changes while within-channel conversion is stable or improves.
2. Assignment proportions violate the declared randomization expectation.
3. Valid assignment with an inconclusive effect interval.

Use separate tiny hand-calculable fixtures and larger generated scenarios. Keep intended scenario labels separate from the actual calculated answers. A public synthetic dataset establishes analytical behavior on that dataset, not real product impact.
