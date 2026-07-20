# LLM-Assisted Source Selection Tasks

## Phase 1: Specification

- [x] Audit current discovery, policy, Autopilot, and regression contracts.
- [x] Record the two-layer policy, LLM boundary, fallback, and test cases.
- [x] Commit the specification.

## Phase 2: Candidate Assessment

- [x] Add bounded candidate assessment domain types and strict response validation.
- [x] Add OpenAI-compatible batch assessor and configuration.
- [x] Add deterministic ranking fallback with explicit status.
- [x] Add focused tests for valid, invalid, unavailable, and low-confidence results.

## Phase 3: Workflow And UX

- [x] Limit legal queues to six candidates while retaining usable fallbacks.
- [x] Add one validated supplemental search round for normal learning scopes.
- [x] Preserve direct-authority gate for service workflows.
- [x] Persist assessment/supplemental-search state and render distinct recovery copy.
- [x] Commit implementation after targeted tests.

## Phase 4: Regression And Audit

- [x] Add recorded self-media, travel-agent, and service-workflow cases.
- [x] Extend deterministic E2E and Playwright coverage.
- [x] Run fast, E2E, browser, golden Demo, and isolated live checks.
- [x] Complete the requirement-by-requirement audit and commit verification.

## Verification Record

- `uv run python scripts/regression.py --fast`: passed, 184 pytest cases and the
  13-case offline Intake evaluation.
- `uv run python scripts/regression.py --e2e`: passed, 3 deterministic guided
  workflow cases.
- `uv run python scripts/regression.py --browser-e2e`: passed, including the
  LLM-ranked candidate and one-round supplemental-search workflow states.
- `uv run python scripts/regression.py --golden-demo-eval`: passed, 25 / 25.
- `uv run python scripts/regression.py --live-guided-e2e`: isolated live search
  and ingestion reached 2 / 2 independent sources. Candidate assessment safely
  fell back after a strict-schema invalid response. The later Wiki build failed
  because the configured chat model returned invalid JSON; the temporary workdir
  was preserved and no normal project or Demo data was written.
