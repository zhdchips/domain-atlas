# Source Selection Quality Tasks

## Phase 1: Specification

- [x] Audit candidate discovery, Autopilot, ingestion, templates, and current regressions.
- [x] Define source roles, official-first policy, source-family behavior, and quality gates.
- [x] Commit the specification phase.

## Phase 2: Candidate And Workflow Policy

- [x] Add pure candidate assessment and explainable metadata.
- [x] Add source-family grouping, fork/mirror handling, and official-first selection plans.
- [x] Require independent source families in Guided Autopilot and persist structured outcomes.
- [x] Preserve Expert manual confirmation with supplemental-source warnings.
- [x] Update candidate and workflow-status UI.
- [x] Commit policy implementation after targeted tests.

## Phase 3: Ingestion Quality

- [x] Exclude HTML chrome from normalized text.
- [x] Record local URL quality signals and preserve excluded raw artifacts.
- [x] Reject exact/obvious near-duplicate source text before chunk/vector persistence.
- [x] Commit ingestion implementation after targeted tests.

## Phase 4: Regression And Audit

- [x] Add deterministic source-policy, ingestion-quality, app, and E2E fixtures.
- [x] Extend Playwright checks for candidate explanations and evidence-insufficient state.
- [x] Run golden Demo, fast, E2E, browser E2E, and isolated live-guided checks.
- [ ] Start local server and validate the default workflow surface.
- [ ] Complete a requirement-by-requirement audit and commit verification.
- [ ] Push deferred by user request.

## Verification Record

- `uv run python scripts/regression.py --golden-demo-eval`: passed, 25/25.
- `uv run python scripts/regression.py --fast`: passed, 128 pytest cases plus the 13-case offline intake evaluation.
- `uv run python scripts/regression.py --e2e`: passed, 2 deterministic Guided-flow cases.
- `uv run python scripts/regression.py --browser-e2e`: passed, including source-role, official-first evidence-gap, manual-confirmation, Wiki, learning-route, and public-Demo checks.
- `uv run python scripts/regression.py --live-guided-e2e`: completed in an isolated temporary data directory with exit status 0. The desktop runner did not relay the child process's final stdout; the script removed its temporary directory, which occurs only on its success path. No normal `data/` project was used.
