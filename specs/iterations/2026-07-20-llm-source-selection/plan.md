# LLM-Assisted Source Selection Plan

## Architecture

`source_policy` becomes the pure deterministic hard-gate module. It derives
roles/families and produces a legal candidate pool, but it no longer treats the
heuristic authority score as a broad-domain admission gate.

A new candidate-assessment module owns the LLM request contract, validation,
and fallback-safe result. It is injected into `AutopilotWorkflow` through a
small protocol, like the existing intake assessment provider. The workflow
persists an assessment step, builds a bounded queue, and makes at most one
supplemental discovery round.

The existing ingestion loop remains the sole owner of actual reachability and
content validation. It consumes the ranked queue until two independent source
families succeed or candidates are exhausted.

## Phases

1. Add this independent specification and audit the existing policy/workflow
   contracts.
2. Add candidate-assessment models, strict validator, prompt, provider adapter,
   settings, and deterministic fallback ranking.
3. Refactor source policy and Autopilot integration for bounded queues and one
   supplemental search round; record precise workflow state.
4. Update dashboard status rendering and recovery copy.
5. Add deterministic unit/E2E/browser coverage, run regression layers, execute
   one isolated real provider check, and complete the requirement audit.

## Design Decisions

- The LLM sees discovery metadata only: candidate ID, title, URL host/path,
  source type, publisher, snippet, and deterministic role. It never sees or
  returns secrets, arbitrary code, or a final direct-authority decision.
- A single batch response reduces cost and avoids per-candidate prompt drift.
- Supplemental search is only for normal learning scopes. Direct-authority
  scopes retain the existing official/regional discovery behavior and fail
  closed when direct evidence is absent.
- The fallback ranking is intentionally simple: deterministic role, heuristic
  score, discovery order, and title. It records that semantic assessment was
  unavailable instead of pretending to be authoritative.

