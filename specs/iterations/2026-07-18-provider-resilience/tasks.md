# Provider Resilience Tasks

## Design

- [x] Audit existing Exa, chat, embedding, URL ingestion, workflow persistence, and status UI.
- [x] Define retry eligibility, configuration, observability, and idempotency boundaries.
- [ ] Commit design stage.

## Implementation

- [ ] Add shared resilience policy, events, safe failure categories, exponential backoff, and jitter.
- [ ] Migrate Exa and chat to the shared policy.
- [ ] Add embedding and URL-fetch retry configuration and integration.
- [ ] Persist retry/recovered/failure events and render them in workflow status.
- [ ] Verify write boundaries remain outside request retry behavior.

## Verification

- [ ] Add deterministic tests for all four provider boundaries and safe error output.
- [ ] Add idempotent ingestion and workflow-status coverage.
- [ ] Run `uv run python scripts/regression.py --fast`.
- [ ] Run `uv run python scripts/regression.py --e2e`.
- [ ] Run `uv run python scripts/regression.py --browser-e2e`.
- [ ] Run a narrow live provider check and document cost/result.
- [ ] Start the service and verify `/health`.
- [ ] Commit implementation and verification stages.
- [ ] Push deferred by user request.
