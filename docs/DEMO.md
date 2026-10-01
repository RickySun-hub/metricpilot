# 60-second demo script

Status: storyboard only. No demo/video exists yet. Use actual measured outputs when implemented; do not invent numbers for screenshots.

| Time | Visible action | Evidence |
| --- | --- | --- |
| 0–8 s | Open public page, see synthetic-data label, click “Why did activation fall last week?” | No registration; precise dataset description |
| 8–20 s | Show retrieved activation definition and actual tool execution status | Versioned contract and mature cohort window |
| 20–35 s | Show overall change and channel decomposition | Numerators, denominators, percentage-point contributions; descriptive wording |
| 35–45 s | Expand Evidence | Actual SQL template/parameters, tool results and data version |
| 45–55 s | Open invalid-assignment experiment scenario | SRM result; refusal to make a rollout recommendation |
| 55–60 s | Open evaluation summary and repository link | Actual results and failures, cost/latency scope |

If live calls exceed one minute, clearly label edited waiting time in the video. On the website, distinguish saved evidence from fresh execution and retain real timestamps. Do not use fabricated progress, pretend streaming or unmeasured instant responses.

## Interview pitch

After completion and verification:

> I built and deployed an analytical agent that investigates product metrics, runs validated SQL and statistical tools, and distinguishes supported conclusions from insufficient evidence.

Until then:

> I am building a product analytics agent with explicit metric contracts, bounded analytical tools, and a held-out evaluation protocol.

## Interview questions to answer without notes

1. Which action does the LLM decide, and which action is hard-coded? Why?
2. Why does this need tool selection rather than a fixed dashboard?
3. How can the overall rate decline while within-group rates improve?
4. What invalidates an experiment result before effect estimation?
5. What does a confidence interval crossing zero allow you to conclude?
6. How do report claims map to evidence, and what remains manually reviewed?
7. What does the baseline comparison establish, and what does it not establish?
8. How do limits survive backend restarts and multiple workers?
