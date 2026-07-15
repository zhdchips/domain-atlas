# Layered Regression Iteration Spec

## Purpose

This iteration fixes the dashboard navigation regression and establishes the first layered regression testing structure for Domain Atlas. The iteration is intentionally scoped: it protects the current guided learning flow without expanding the MVP product surface.

## User Problem

After a guided project is built, the dashboard workflow cards for Wiki, learning path, and QA appear clickable but do not navigate to the actual pages. They point at local anchors that do not exist on the dashboard.

The project also needs a repeatable regression path that catches this kind of UI/workflow breakage without relying on Exa, live URL fetching, LLM generation, embedding APIs, or provider cost.

## Functional Requirements

- The dashboard source card may continue linking to `#sources`.
- The dashboard Wiki card must link to `/domains/{project_id}/wiki`.
- The dashboard learning path card must link to `/domains/{project_id}/path`.
- The dashboard QA card must link to `/domains/{project_id}/qa`.
- The target pages must continue returning HTML responses for existing projects.

## Regression Requirements

- Add a deterministic E2E regression test for the guided domain flow.
- The E2E must not call real Exa, real URL fetch, real LLM, real embedding, or live vector storage.
- The E2E must cover:
  - creating a guided project,
  - running a deterministic guided build through the app route,
  - seeing completed dashboard state,
  - validating dashboard navigation links,
  - loading Wiki, learning path, and QA pages,
  - submitting a QA question and seeing answer, Wiki citation, and source provenance.
- Add a regression script with fast, e2e, and live layers.
- The live layer remains an explicit provider smoke check and must not be part of deterministic E2E.

## Layered Regression Strategy

- Unit: core functions and boundary rules such as candidate filtering, JSON extraction, slug behavior, and lint rules.
- Integration: repository, workflow, provider adapter, ingestion, indexing, and QA contracts.
- Deterministic E2E: key user-visible paths using fake providers and in-memory/local test data. This layer catches route, template, redirect, workflow state, and page rendering regressions.
- Live smoke: configured external provider availability for Exa, chat, and embeddings.

Future SDD iterations should update regression coverage by asking:

- Did this iteration add or alter a user-visible flow?
- Did this iteration alter a domain model, provider adapter, workflow, or persistence contract?
- Did this iteration fix a bug that needs a permanent regression test?
- Which layer should own the test: unit, integration, deterministic E2E, or live smoke?
- Do fixtures or fake providers need to change with the contract?

## Acceptance Criteria

- Dashboard Wiki, learning path, and QA workflow cards navigate to real pages.
- `uv run pytest` passes.
- `uv run pytest tests/e2e` passes.
- `uv run python scripts/regression.py --fast` passes.
- `uv run python scripts/regression.py --e2e` passes.
- If local provider configuration is available, `uv run python scripts/regression.py --live` passes.
- `/health` remains healthy while the development server is running.
- Changes are committed locally; push remains deferred by user request.
