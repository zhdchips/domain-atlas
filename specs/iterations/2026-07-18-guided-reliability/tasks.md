# Guided Autopilot Reliability Tasks

## Phase 1: Specification

- [x] Review guided workflow, provider adapters, dashboard state, current regression layers, and recent reliability fixes.
- [x] Create an independent spec, implementation plan, and task list for this iteration.
- [x] Review the specification against the current implementation and commit Phase 1.

## Phase 2: Reliable Candidate Consumption

- [x] Add ordered candidate queue behavior with two-source build gate and queue exhaustion result.
- [x] Persist structured source attempts, failure categories, and terminal reason.
- [x] Preserve source-ranking, deduplication, and per-domain constraints.
- [x] Render learner-facing exhaustion/recovery summary and success counts.
- [x] Add deterministic workflow coverage for queue and failure cases.
- [x] Commit Phase 2 after targeted tests pass.

## Phase 3: Regression Layers

- [ ] Add recorded discovery/fetch fixtures and deterministic app E2E.
- [ ] Extend Playwright flow coverage for guided success and exhaustion states.
- [ ] Add isolated `--live-guided-e2e` and regression command wiring.
- [ ] Document regression layer responsibilities and commands.
- [ ] Commit Phase 3 after deterministic/browser checks pass.

## Phase 4: Verification And Audit

- [ ] Run fast, deterministic E2E, browser E2E, live fixed-build E2E, and live guided E2E.
- [ ] Record actual live timings and source outcome counts in this task file.
- [ ] Verify server health and a clean worktree after commits.
- [ ] Complete requirement-by-requirement audit and commit Phase 4.
- [ ] Push deferred by user request.
