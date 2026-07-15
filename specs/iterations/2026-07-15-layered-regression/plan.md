# Layered Regression Iteration Plan

## Scope

This iteration adds one narrow product fix and one regression testing skeleton. It does not change the core Domain Atlas architecture, LLM Wiki model, or provider configuration.

## Implementation Plan

1. Document the iteration in `specs/iterations/2026-07-15-layered-regression/`.
2. Add a Phase 14 index entry to `specs/mvp/tasks.md`.
3. Fix dashboard workflow card links for Wiki, learning path, and QA.
4. Add a deterministic autopilot injection point to the FastAPI app factory, keeping production defaults unchanged.
5. Add `tests/e2e/test_guided_domain_flow.py`.
6. Add pytest marker metadata for `e2e`.
7. Add `scripts/regression.py` with `--fast`, `--e2e`, and `--live`.
8. Add a short README pointer to the layered regression strategy.
9. Run the required regression gates and commit locally.

## Deterministic E2E Design

The E2E test will use FastAPI `TestClient` against the real app routes and templates. It will inject:

- a fake autopilot runner that writes deterministic sources, chunks, artifacts, and workflow status to the test database;
- a fake embedding provider;
- a fake vector index that returns deterministic Wiki section retrieval;
- a fake QA chat provider that returns deterministic cited answers.

This keeps the route/dashboard/page/QA behavior real while removing network, live model, embedding, and vector-store nondeterminism.

## Non-Goals

- No Playwright/browser automation in this iteration.
- No real Exa/LLM/embedding calls in deterministic E2E.
- No broad test framework rewrite.
- No push.
