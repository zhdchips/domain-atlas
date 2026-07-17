# Tasks

- [x] Define the versioned case format, metrics, quality gate, and case-maintenance guidance.
- [x] Add a representative Chinese intake case set with recorded deterministic responses.
- [x] Implement reusable evaluator, normalized report, and offline runner with unit coverage.
- [x] Implement live runner with configured-provider checks and non-sensitive persisted reports.
- [x] Extend regression commands and README documentation.
- [x] Run fast regression, offline eval, browser E2E, and one live eval; record outcomes and commit without pushing.

## Verification

- `uv run python scripts/regression.py --fast` - 85 pytest cases passed, then the 13-case offline intake evaluation passed its quality gate.
- `uv run python scripts/regression.py --intake-eval` - passed deterministically without network or provider credentials.
- `uv run python scripts/regression.py --browser-e2e` - passed.
- `uv run python scripts/regression.py --live-intake-eval` - executed once with the configured LLM and wrote `reports/intake/2026-07-17-intake-zh-v1.json`. The live gate intentionally failed and is preserved as the baseline: decision accuracy 84.62%, false-interrupt rate 66.67%, structure rate 100%, and topic coverage 30%. No gold case was changed to conceal those results.
