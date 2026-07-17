# Plan

1. Add a cautious `INTAKE_LLM_SUGGESTIONS_ENABLED` setting, disabled by default.
2. Evolve the provider protocol into a suggestion overlay and implement the OpenAI-compatible provider with one request and no retry.
3. Validate and normalize output against the deterministic assessment allowlist; invalid data returns no suggestion.
4. Wire suggestion application into only the `needs_clarification` create path and persist `rule` / `llm` / `fallback` source metadata.
5. Show suggestion provenance in the clarification page and extend deterministic app/browser checks.

## Fallback policy

Disabled or unconfigured: `not_requested`, `rule`. Provider exception or invalid output: `fallback`, `fallback`. Valid output: `applied`, `llm`. No provider failure detail is shown to the learner.
