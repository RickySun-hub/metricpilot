# Deployment checklist

Status: a temporary anonymous Vercel deployment has been published and verified from the public URL in desktop/mobile browsers. It expires unless the owner claims it; it is not a permanent production URL. No paid model calls or paid hosting subscription were created. Current zero-cost execution is deterministic SQL/statistics plus local CPU embeddings, with live LLM disabled.

Verified temporary URL: https://temporary-quick-fiddle-x0gi9g1.vercel.app

Verified deployment ID: `dpl_6Qnp6eZQ9B1fy1Q5WdFm7HEoDy8N`. Implementation source: `a1aab33054717033ddfc6df3a05bccea5960efec`. Anonymous expiry: **2026-10-01 02:00:24 UTC** (September 30, 19:00:24 America/Los_Angeles), unless claimed. [Browser record](assets/public-qa.json) and [recorded walkthrough](assets/demo.webm) retain the observed behavior.

The private claim link is delivered in chat and must never be committed here. Record the permanent project/domain after the owner claims it. Do not use this temporary URL as a long-term resume link until ownership/persistence is confirmed.

Deployment configuration: static Next.js export plus same-origin Python function api/index.py. Python 3.12, NumPy 2.2.6 and uv.lock keep cross-platform packaging within the anonymous function limit. The initial Windows builder needed static export to avoid a symlink limitation. The embedding tokenizer is a small Python implementation validated against the upstream Rust tokenizer; no remote Hugging Face client is needed during inference.

Browser verification: public health returned live_enabled=false; activation, funnel, SRM refusal and valid experiment uncertainty all rendered; SQL evidence expanded; 1440×1000 and 390×844 viewports had no page errors or horizontal overflow. A few manual requests do not prove restart durability or load capacity. Real-provider/Redis controls and Docker execution remain unverified.

## Target

Proposed: a hosted Next.js frontend and a Dockerized FastAPI backend serving a bundled read-only synthetic DuckDB snapshot. Keep this separate from ProofRound production. Verify current platform capabilities, cold starts and costs when choosing the backend host. Do not promise a permanent free tier.

## Before provisioning

- Confirm the target account/project, model and allowed data scope.
- Choose the monthly hosting cap, development/evaluation API cap and daily public-demo cap. The earlier $30 suggestion concerns development/evaluation model calls, not a guaranteed total project cost.
- Define how execution stops when the cap is reached; include provider-side controls where available and application-side durable accounting.
- Store credentials server-side through the selected platform's secret store. Documentation uses placeholders only, such as `<SECRET_FROM_APPROVED_STORE>`.

## Public endpoint requirements

- No registration needed for preset synthetic scenarios.
- Validate size, task, dates and enums on the server; use an exact frontend origin allowlist.
- Enforce per-client throttling, shared daily budget, concurrency limits, model/tool limits and deadlines.
- Store shared accounting durably across workers/restarts; a per-process Python dictionary does not enforce a global spending cap.
- Mount/bundle only the intended read-only data; prohibit arbitrary SQL/file/network operations.
- Return useful error/abstention states without stack traces, secrets or raw internal configuration.
- Use clear LIVE / SAVED RUN labels with source run time and version for saved results.

## Verification record

Record the actual deployed commit, frontend URL, API environment, dataset hash, model identifier and settings. Test all three workflows from an incognito browser on the public URL. Check a restart, provider failure, timeout, exhausted quota, unsupported input and invalid dataset. Confirm no provider keys appear in source maps, frontend bundles or network responses.

Measure real latency and cold-start behavior. If a request times out, report it; a staged saved result is not a live success. Do not claim production-scale reliability from a few manual requests.

## Stop and recovery

Keep a verified previous deployment/version available for rollback. Disable public live calls when budgets are exhausted or a critical error appears. A clearly labeled saved-run mode can remain available while live calls are disabled. Do not allocate extra resources or raise limits silently.
