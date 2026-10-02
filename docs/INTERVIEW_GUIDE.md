# Explain the project honestly

Implementation used AI assistance. Understanding is a separate owner task; passing tests does not prove it. Do not say you independently authored every component by hand.

1. **Reproduce a metric.** Run activation, inspect denominators, then use evals/reference.py to calculate it from user/event records. Explain cohort maturity, timestamp ordering and session matching.
2. **Explain the decline.** Derive the exact symmetric decomposition in DATA_AND_METRICS.md. Mix and within-group contributions sum to the overall change, but do not identify causes.
3. **Explain experiment refusal.** Run onboarding_srm. State the randomization unit, 50:50 expectation, SRM test/threshold and why invalid assignment blocks interpretation.
4. **Explain uncertainty.** Run onboarding_valid. Reproduce treatment-minus-control and the Wilson-based Newcombe interval. Zero inside the interval is inconclusive, not proof of no effect. Significance alone would not justify rollout.
5. **Trace the graph.** Read backend/agent.py: retrieve → decide → execute → decide → report. Identify deterministic versus optional model selection. Who owns permissions, SQL and stopping? The showcase defaults to recorded evidence and performs no model calls. Local requests are deterministic. Real-provider samples and the preserved failed paired attempt exist; describe each exact artifact and its review state.
6. **Explain retrieval.** Tokenization, attention masks, pretrained ONNX token vectors, masked mean pooling and normalization produce 384-dimensional sentence embeddings. Cosine similarity ranks contracts. These weights were not trained here. Both lexical and semantic top-3 checks passed; no superiority claim is supported.
7. **Explain evaluation.** Thirty synthetic test cases repeated three times are not ninety independent examples or LLM accuracy. Explain how independent references avoid testing SQL against itself and how a model-baseline comparison must disclose information access.
8. **Explain operations.** Default mode has no model API cost. Public live mode requires approved credentials/budget/shared quotas. Mock accounting tests do not establish a deployed Redis service. A temporary deployment is not a permanent production service.

Demonstrable scope: Python/SQL tools, Next.js/FastAPI interface, independent numerical checks, local pretrained semantic retrieval, bounded graph, mocked safety boundaries, real-provider recorded samples and transparent failure records. Use “deployed” only with a verified public URL and its actual temporary/permanent status. A recorded sample or partial attempt does not establish general LLM accuracy. No customer adoption or business savings is claimed.

9. **Explain the grounding revision.** The current schema lets the model choose verified fact IDs and write qualitative cited language; the server renders selected fact values. Contrast this with the earlier saved sample’s numeric-substitution scheme. Explain why references can pass while qualitative entailment still requires review.
10. **Explain the failure record.** Distinguish attempted failures from unattempted cases after a stop. Explain why a 6/6 development result is not equivalent to a completed frozen-test evaluation. Read [the current grounding notes](RAG_IMPLEMENTATION.md) and [evaluation protocol](EVALUATION.md).

Current model evidence boundary: the final primary v3 synthetic attempt stopped at 10/180 responses (7 automatic passes, 3 withheld, 170 unrun). This cannot be described as 70% full-protocol accuracy. Independent supplementary retail/adversarial tracks are execution-blocked with no recorded outcomes; earlier development examples do not replace them. A functional bounded RAG research demo is not a reliable general-purpose analyst.
