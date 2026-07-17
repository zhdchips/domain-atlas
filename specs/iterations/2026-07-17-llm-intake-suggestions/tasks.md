# Tasks

- [x] Add configuration and injectable LLM suggestion provider.
- [x] Define strict suggestion contract, validation, and one-call failure fallback.
- [x] Apply suggestions only after deterministic clarification decisions.
- [x] Persist provenance and show it in the clarification UI.
- [x] Add deterministic unit, application, and browser regression coverage.
- [x] Run fast/browser regression and commit without pushing.

## Verification

- `uv run python scripts/regression.py --fast` - 71 passed.
- `uv run python scripts/regression.py --browser-e2e` - passed; covers enhanced LLM provenance, rule fallback, and mobile clarification layout.
- Live E2E intentionally not run: the feature defaults to disabled and does not alter the live search/build/QA path.
