# Readable Wiki Rendering Tasks

## Design

- [x] Audit current Wiki routes, page/section/source data, Demo catalog, and templates.
- [x] Define safe Markdown, scoped link, citation, and unresolved-reference behavior.
- [x] Create this independent iteration specification, plan, and task record.
- [x] Commit the design stage.

## Implementation

- [x] Add the direct Markdown dependency and shared presentation renderer.
- [x] Build scoped local and Demo rendering contexts.
- [x] Render Wiki bodies, headings, internal links, citations, and evidence panels.
- [x] Render embedded citation labels in learning-guide and QA prose.
- [x] Add readable Wiki CSS without changing mutable local workflows or Demo allowlists.

## Verification

- [x] Add deterministic parser/security/scoping/application tests.
- [x] Extend Playwright rendering, navigation, citation, and responsive-layout checks.
- [x] Run `uv run python scripts/regression.py --golden-demo-eval`.
- [x] Run `uv run python scripts/regression.py --fast`.
- [x] Run `uv run python scripts/regression.py --e2e`.
- [x] Run `uv run python scripts/regression.py --browser-e2e`.
- [x] Verify default local mode and public Demo routes at runtime without providers.
- [x] Commit implementation and verification stages.
- [ ] Push deferred by user request.
