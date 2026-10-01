# 60-second demo script

Status: the public application and desktop/mobile walkthrough have been verified. [Watch the actual public recording](assets/demo.webm). It shows fresh activation analysis, executed SQL, SRM rejection and an inconclusive valid experiment; waiting time is retained. Current execution uses real deterministic SQL/statistics and explicitly says no live LLM is active. The public URL is temporary until claimed by the owner.

The table below is a suggested narrated 60-second interview flow, not a timestamp transcript of the silent recording.

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

Current scope, after the owner can explain and reproduce the implementation:

> I implemented an AI-assisted product analytics application with bounded LangGraph workflows, local semantic retrieval and validated SQL/statistical tools. The public demo runs deterministic analysis on synthetic data. The optional LLM action selector is implemented but has not been verified against a real provider.

Do not describe the temporary deployment as permanent, or deterministic regression scores as LLM accuracy. Implementation assistance does not establish independent hand-authorship or interview readiness.

## Interview questions to answer without notes

1. Which action does the LLM decide, and which action is hard-coded? Why?
2. Why does this need tool selection rather than a fixed dashboard?
3. How can the overall rate decline while within-group rates improve?
4. What invalidates an experiment result before effect estimation?
5. What does a confidence interval crossing zero allow you to conclude?
6. How do report claims map to evidence, and what remains manually reviewed?
7. What does the baseline comparison establish, and what does it not establish?
8. How do limits survive backend restarts and multiple workers?
