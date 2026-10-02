# Deployment checklist

Historical deployment record: an earlier temporary anonymous Vercel build was verified in desktop/mobile browsers. Its recorded expiry was October 1, 2026 unless claimed; current ownership and availability are unverified. This is not the deployment status of the October 2 grounded-generation/dashboard changes. That historical build used deterministic SQL/statistics plus local CPU embeddings and made no paid model calls. No new public paid-API deployment is authorized.

Historically verified temporary URL: https://temporary-quick-fiddle-x0gi9g1.vercel.app

Verified deployment ID: `dpl_6Qnp6eZQ9B1fy1Q5WdFm7HEoDy8N`. Implementation source: `a1aab33054717033ddfc6df3a05bccea5960efec`. Anonymous expiry: **2026-10-01 02:00:24 UTC** (September 30, 19:00:24 America/Los_Angeles), unless claimed. [Browser record](assets/public-qa.json) and [recorded walkthrough](assets/demo.webm) retain the observed behavior.

The private claim link is delivered in chat and must never be committed here. Record the permanent project/domain after the owner claims it. Do not use this temporary URL as a long-term resume link until ownership/persistence is confirmed.

Deployment configuration: static Next.js export plus same-origin Python function api/index.py. Python 3.12, NumPy 2.2.6 and uv.lock keep cross-platform packaging within the anonymous function limit. The initial Windows builder needed static export to avoid a symlink limitation. The embedding tokenizer is a small Python implementation validated against the upstream Rust tokenizer; no remote Hugging Face client is needed during inference.

Browser verification: public health returned live_enabled=false; activation, funnel, SRM refusal and valid experiment uncertainty all rendered; SQL evidence expanded; 1440×1000 and 390×844 viewports had no page errors or horizontal overflow. Those historical manual requests do not prove restart durability or load capacity. Current local real-provider runs are documented separately in RAG_IMPLEMENTATION.md; hosted Redis controls and Docker execution remain unverified.

## Target

Proposed: a hosted Next.js frontend and a Dockerized FastAPI backend serving a bundled read-only synthetic DuckDB snapshot. Keep this separate from ProofRound production. Verify current platform capabilities, cold starts and costs when choosing the backend host. Do not promise a permanent free tier.

## Before provisioning

- Confirm the target account/project, model and allowed data scope.
- Choose the hosting cap separately. The current authorized development/evaluation API ceiling is $5 total, enforced as a hard lifetime application cap. Daily default is $1 and cannot exceed that lifetime ceiling. Keep the same durable ledger for all calls; separate quota stores cannot enforce one shared allowance.
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
