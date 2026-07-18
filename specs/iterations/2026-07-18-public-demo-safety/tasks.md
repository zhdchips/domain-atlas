# Public Read-Only Demo Safety Tasks

## Design

- [x] Audit normal routes, template action surfaces, provider factories, and persistence initialization.
- [x] Define an in-memory catalog and allowlist-first public-mode boundary.
- [x] Commit design stage.

## Implementation

- [x] Add public-demo Settings and route allowlist middleware.
- [x] Add the version-controlled in-memory demo catalog.
- [x] Add demo overview, Wiki, learning-path, and pre-generated QA routes/templates.
- [x] Ensure public mode skips local persistence initialization and denies all mutation endpoints.
- [x] Keep local-first routes and controls unchanged when public mode is off.

## Verification

- [x] Add deterministic public-mode isolation, provider non-use, and local-mode compatibility tests.
- [x] Add Playwright Demo navigation and mutation-block checks.
- [x] Run `uv run python scripts/regression.py --fast`.
- [x] Run `uv run python scripts/regression.py --e2e`.
- [x] Run `uv run python scripts/regression.py --browser-e2e`.
- [x] Verify default local and public Demo mode health/routes without live providers.
- [x] Commit implementation and verification stages.
- [ ] Push deferred by user request.
