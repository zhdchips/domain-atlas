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
- [x] Start local server and validate the default workflow surface.
- [x] Complete a requirement-by-requirement audit and commit verification.
- [ ] Push deferred by user request.

## Verification Record

- `uv run python scripts/regression.py --golden-demo-eval`: passed, 25/25.
- `uv run python scripts/regression.py --fast`: passed, 128 pytest cases plus the 13-case offline intake evaluation.
- `uv run python scripts/regression.py --e2e`: passed, 2 deterministic Guided-flow cases.
- `uv run python scripts/regression.py --browser-e2e`: passed, including source-role, official-first evidence-gap, manual-confirmation, Wiki, learning-route, and public-Demo checks.
- `uv run python scripts/regression.py --live-guided-e2e`: completed in an isolated temporary data directory with exit status 0. The desktop runner did not relay the child process's final stdout; the script removed its temporary directory, which occurs only on its success path. No normal `data/` project was used.

## Completion Audit

- Source roles, direct-authority signal, family key, selection reason, and manual warning are computed by the pure `source_policy` module and persisted in candidate metadata. The dashboard/browser fixture verifies their learner-facing rendering.
- Service-workflow scopes use official-first selection. The recorded `寿司郎在线取号流程` case has no direct source, creates no automatic sources, records `evidence_insufficient`, and leaves supplemental candidates available for manual confirmation.
- GitHub repositories no longer receive a host-trust bonus, and same-name repository forks are one evidence family. Repeated discovery results, forks, and exact URLs cannot satisfy the independent two-family gate.
- URL HTML excludes common chrome. Navigation-only pages and obvious duplicate content retain artifacts with an exclusion reason but create neither chunks nor vectors; targeted ingestion tests cover both paths.
- Existing local workflows, Expert manual confirmation, Wiki/learning/QA surfaces, and the public zero-provider Demo are covered by the final deterministic and browser regression runs.
- Residual limitation: direct-document classification is deterministic URL/title/type evidence, not legal proof of site ownership. Borderline near duplicates remain visible for manual review rather than being over-aggressively removed.
