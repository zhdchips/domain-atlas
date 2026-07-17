# Plan

1. Define a JSON case-set schema and initial gold cases spanning clear, broad, ambiguous, conflicting, and boundary requests.
2. Build a reusable evaluator that consumes either a recorded provider or a live provider and emits normalized, non-sensitive case results and metrics.
3. Add command-line scripts for deterministic offline evaluation and opt-in live evaluation, including report persistence and explicit configuration failures.
4. Extend the regression dispatcher and README, then test degraded provider, decision, candidate, topic, and report behavior.

## Boundaries

Offline evaluation uses recorded payloads and never reads real provider credentials. Live evaluation is explicit and can fail its quality gate without changing production data or blocking deterministic fast regression.
