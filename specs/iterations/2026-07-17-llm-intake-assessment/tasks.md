# Tasks

- [x] Define the new assessment contract and legacy metadata compatibility.
- [x] Implement one-call LLM assessment and validation/fallback behavior.
- [x] Wire application creation/confirmation persistence and update clarification copy.
- [x] Add deterministic unit and application coverage for clear, clarify, fallback, and custom confirmation.
- [x] Update Playwright fixture and browser flow for model-led clarification and mobile layout.
- [x] Run fast and browser regression layers, complete documentation, and commit without pushing.

## Verification

- `uv run python scripts/regression.py --fast` - 77 passed.
- `uv run python scripts/regression.py --browser-e2e` - passed; covers persisted model-led clarification, direct creation, confirmation, and mobile no-overflow.
- Live E2E intentionally not run: this iteration does not change the real search, ingestion, build, or QA pipelines. The fixed live build script disables intake assessment so that its existing build assertions remain deterministic.
