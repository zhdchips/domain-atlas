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

- [ ] Add deterministic source-policy, ingestion-quality, app, and E2E fixtures.
- [ ] Extend Playwright checks for candidate explanations and evidence-insufficient state.
- [ ] Run golden Demo, fast, E2E, browser E2E, and isolated live-guided checks.
- [ ] Start local server and validate the default workflow surface.
- [ ] Complete a requirement-by-requirement audit and commit verification.
- [ ] Push deferred by user request.
