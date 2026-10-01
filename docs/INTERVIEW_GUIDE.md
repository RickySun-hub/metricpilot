# Explain the project honestly

Implementation used AI assistance. Understanding is a separate owner task; passing tests does not prove it. Do not say you independently authored every component by hand.

1. **Reproduce a metric.** Run activation, inspect denominators, then use evals/reference.py to calculate it from user/event records. Explain cohort maturity, timestamp ordering and session matching.
2. **Explain the decline.** Derive the exact symmetric decomposition in DATA_AND_METRICS.md. Mix and within-group contributions sum to the overall change, but do not identify causes.
3. **Explain experiment refusal.** Run onboarding_srm. State the randomization unit, 50:50 expectation, SRM test/threshold and why invalid assignment blocks interpretation.
4. **Explain uncertainty.** Run onboarding_valid. Reproduce treatment-minus-control and the Wilson-based Newcombe interval. Zero inside the interval is inconclusive, not proof of no effect. Significance alone would not justify rollout.
5. **Trace the graph.** Read backend/agent.py: retrieve → decide → execute → decide → report. Identify deterministic versus optional model selection. Who owns permissions, SQL and stopping? Public execution is deterministic; mocked live tests do not establish real-model quality.
6. **Explain retrieval.** Tokenization, attention masks, pretrained ONNX token vectors, masked mean pooling and normalization produce 384-dimensional sentence embeddings. Cosine similarity ranks contracts. These weights were not trained here. Both lexical and semantic top-3 checks passed; no superiority claim is supported.
7. **Explain evaluation.** Thirty synthetic test cases repeated three times are not ninety independent examples or LLM accuracy. Explain how independent references avoid testing SQL against itself and how a model-baseline comparison must disclose information access.
8. **Explain operations.** Default mode has no model API cost. Public live mode requires approved credentials/budget/shared quotas. Mock accounting tests do not establish a deployed Redis service. A temporary deployment is not a permanent production service.

Demonstrable scope: Python/SQL tools, Next.js/FastAPI interface, independent numerical checks, local pretrained semantic retrieval, bounded graph, mocked live safety. Use “deployed” only with a verified public URL and its actual temporary/permanent status. No real LLM performance, customer adoption or business savings is claimed.
