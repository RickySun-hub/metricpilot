# Implementation and evidence status

The owner requested AI-assisted implementation after the original design-only stage, then explicitly selected zero API fees. That scope change is reflected in the application and README.

| Milestone | Implemented and verified | Remaining |
| --- | --- | --- |
| M1 data/contracts | Seeded 12,000 users / 50,504 events, integrity and reference checks | Owner learning |
| M2 deterministic tools | SQL, ordered funnel, exact decomposition, SRM/Newcombe checks | Wider data/task scope |
| M3 graph | Bounded deterministic graph; mocked model-action safety tests | Real LLM calls/quality, owner explanation |
| M4 retrieval | CPU MiniLM embeddings, ten contracts; measured lexical comparison | Larger held-out retrieval study |
| M5 UI/evidence | Desktop/mobile, charts, SQL/results, validated numerical fields | Independent narrative/user review |
| M6 evaluation | 60-case manifest, 3×30/30 deterministic checks, library references | Real-model baseline/repeats; full original release gate |
| M7 deployment | Verified temporary public Vercel application; live LLM off | Owner claim and persistent URL; load/restart tests |
| M8 delivery | Runnable documentation, source, actual results, recorded public walkthrough and explanation guide | Owner interview readiness |

Completing code does not automatically complete the owner's understanding or the original live-model release gate. Keep partially satisfied original issues open with exact evidence and remaining items.
