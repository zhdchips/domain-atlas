# Plan

1. Replace the suggestion-overlay protocol with an injectable structured intake-assessment provider and a normalized assessment model that can still read legacy metadata.
2. Implement strict JSON validation for decision, confidence, text limits, options, recommendation/default consistency, and sensitive-content filtering. Use a direct-create fallback assessment for unavailable or rejected results.
3. Wire one configured OpenAI-compatible completion into every new-project intake request, with retries disabled and a configurable confidence threshold. Persist only normalized provenance and fallback status.
4. Update clarification provenance wording and browser fixtures to represent LLM-owned decisioning rather than local-rule-owned options.
5. Replace rule-centric tests with deterministic provider tests for clear, clarify, invalid/low-confidence/failure, confirmation, legacy compatibility, and mobile browser behavior.

## Fallback Policy

The fallback is always a confirmed project whose scope equals the submitted domain name. It records `assessment_source: fallback` and one of `unconfigured`, `failed`, `invalid`, or `low_confidence`; no raw error is stored or rendered.
