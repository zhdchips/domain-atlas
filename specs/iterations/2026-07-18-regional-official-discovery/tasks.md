# Regional Official Discovery Tasks

## Phase 1: Specification

- [x] Audit existing selection policy, Guided workflow, persistence, dashboard, and browser checks.
- [x] Define regional query, official-entry provenance, region boundary, and recovery-state behavior.
- [x] Commit specification phase.

## Phase 2: Discovery And Selection

- [x] Add regional/brand assessment and bounded official-entry inspection.
- [x] Integrate one regional query and structured workflow outcomes.
- [x] Persist provenance and protect automatic ingestion boundaries.
- [x] Commit implementation phase.

## Phase 3: UX And Regression

- [x] Render provenance and distinct recovery feedback without duplicate errors.
- [x] Add deterministic unit/E2E/browser coverage for all required scenarios.
- [x] Run regression suite and isolated live compatibility check.
- [x] Commit verification phase.

## Verification Record

- `uv run python scripts/regression.py --fast`: passed, 136 pytest cases plus the 13-case offline intake evaluation.
- `uv run python scripts/regression.py --e2e`: passed, including the mainland official-entry confirmation flow.
- `uv run python scripts/regression.py --golden-demo-eval`: passed, 25/25.
- `uv run python scripts/regression.py --browser-e2e`: passed, including official-entry provenance and single-error rendering.
- `uv run python scripts/regression.py --live-guided-e2e`: isolated provider run exited and removed its temporary directory through the script's success path. The desktop runner did not relay the final summary line, so no exact cost/time/candidate count is recorded.
- Read-only live `寿司郎在线取号流程` discovery diagnosis: the bounded regional query returned the operator's Simplified-Chinese site and its Guangzhou WeChat entry; the final policy had 37 candidates, 1 official entry, an empty automatic queue, and `official_entry_requires_confirmation`.
