# Provider Resilience Plan

1. Introduce a dependency-light core resilience module with retry policy, safe failure classification, jittered exponential delay, and observer events.
2. Move Exa and chat onto that module, removing duplicated retry logic and treating malformed LLM JSON as non-retryable transport output.
3. Add the policy to embedding and URL fetch construction paths, expose per-provider timeout/retry Settings, and preserve source/chunk persistence semantics.
4. Bind retry observers to background workflow runs and render their retry/recovery/failure summaries in the workflow panel.
5. Add deterministic provider, ingestion, workflow/app, and browser checks; run the established regression layers plus one narrow live provider validation.

## Design Decisions

- Retrying a single HTTP request is deliberately narrower than retrying a workflow. Database and vector writes remain outside the shared executor.
- Retry events are persisted as workflow steps so the existing polling UI needs no new server or queue infrastructure.
- Upstream error bodies are intentionally omitted from stored events and displayed errors. HTTP status and stable category are sufficient for recovery.
- Jitter is injectable in tests so deterministic tests do not sleep or depend on randomness.
