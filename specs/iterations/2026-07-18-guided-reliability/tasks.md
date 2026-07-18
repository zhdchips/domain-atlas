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

- [x] Add recorded discovery/fetch fixtures and deterministic app E2E.
- [x] Extend Playwright flow coverage for guided success and exhaustion states.
- [x] Add isolated `--live-guided-e2e` and regression command wiring.
- [x] Document regression layer responsibilities and commands.
- [x] Commit Phase 3 after deterministic/browser checks pass.

## Phase 4: Verification And Audit

- [x] Run fast, deterministic E2E, browser E2E, live fixed-build E2E, and live guided E2E.
- [x] Record actual live timings and source outcome counts in this task file.
- [ ] Verify server health and a clean worktree after commits.
- [x] Complete requirement-by-requirement audit and commit Phase 4.
- [ ] Push deferred by user request.

## Verification Record

- `uv run python scripts/regression.py --fast`: passed, 94 pytest cases plus 13/13 offline intake evaluation cases.
- `uv run python scripts/regression.py --e2e`: passed, 2 deterministic app E2E cases.
- `uv run python scripts/regression.py --browser-e2e`: passed, including guided active, success, and exhaustion UI states.
- `uv run python scripts/regression.py --live-e2e`: passed in 71.6s; 3 fixture chunks, 19 Wiki pages, 23 Wiki sections, 5 lesson modules, and cited QA.
- `uv run python scripts/regression.py --live-guided-e2e`: passed in 99.2s; 12 real candidates discovered, 2 attempted/2 ingested, 18 Wiki pages, and cited QA. Query: `OpenAI Agents SDK official documentation`.

## Completion Audit

- Candidate queue, ranking, URL deduplication, and two-source gate: verified by `tests/test_autopilot.py` and recorded guided E2E.
- Structured attempts, failure categories, exhaustion reason, and recovery guidance: verified by unit tests, dashboard test, and browser exhaustion fixture.
- No-network replay: verified by `tests/e2e/test_guided_reliability_flow.py`; its fixture includes two `403` encyclopedia candidates followed by two ingestible fallback pages.
- Browser workflow behavior: verified by `scripts/browser_e2e_wiki_layout.py` using a deterministic fixture app.
- Provider-facing behavior: verified by both opt-in live commands in isolated temporary data directories.
- Residual risk: public search ranking and anti-bot behavior can still change at runtime. The workflow now continues through its ranked queue and reports recovery guidance when no two-source path exists; it does not bypass site access controls.
