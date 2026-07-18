# Public Read-Only Demo Safety Tasks

## Design

- [x] Audit normal routes, template action surfaces, provider factories, and persistence initialization.
- [x] Define an in-memory catalog and allowlist-first public-mode boundary.
- [ ] Commit design stage.

## Implementation

- [ ] Add public-demo Settings and route allowlist middleware.
- [ ] Add the version-controlled in-memory demo catalog.
- [ ] Add demo overview, Wiki, learning-path, and pre-generated QA routes/templates.
- [ ] Ensure public mode skips local persistence initialization and denies all mutation endpoints.
- [ ] Keep local-first routes and controls unchanged when public mode is off.

## Verification

- [ ] Add deterministic public-mode isolation, provider non-use, and local-mode compatibility tests.
- [ ] Add Playwright Demo navigation and mutation-block checks.
- [ ] Run `uv run python scripts/regression.py --fast`.
- [ ] Run `uv run python scripts/regression.py --e2e`.
- [ ] Run `uv run python scripts/regression.py --browser-e2e`.
- [ ] Verify default local and public Demo mode health/routes without live providers.
- [ ] Commit implementation and verification stages.
- [ ] Push deferred by user request.
