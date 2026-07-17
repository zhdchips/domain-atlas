# Tasks

- [x] Persist observable task state and stale-task recovery.
- [x] Move build, autopilot, and source ingestion behind a local background runner.
- [x] Record granular task steps and enforce conflict protection.
- [x] Add pending form behavior, dashboard polling, friendly errors, and responsive styling.
- [x] Add deterministic and Playwright regression coverage.
- [x] Run fast, browser, and live E2E regression; rebuild the local Dataphin project.
- [x] Commit the focused implementation without pushing.

## Verification

- `uv run python scripts/regression.py --fast` - 55 passed.
- `uv run python scripts/regression.py --browser-e2e` - passed, including dashboard pending state and mobile overflow check.
- `uv run python scripts/regression.py --live-e2e` - passed with configured live providers.
- Local project 2 (`瓴羊Dataphin`) rebuilt through the new background build route; run 28 completed after lesson-structure repair and indexing.
