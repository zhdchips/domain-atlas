# Readable Wiki Rendering Tasks

## Design

- [x] Audit current Wiki routes, page/section/source data, Demo catalog, and templates.
- [x] Define safe Markdown, scoped link, citation, and unresolved-reference behavior.
- [x] Create this independent iteration specification, plan, and task record.
- [x] Commit the design stage.

## Implementation

- [ ] Add the direct Markdown dependency and shared presentation renderer.
- [ ] Build scoped local and Demo rendering contexts.
- [ ] Render Wiki bodies, headings, internal links, citations, and evidence panels.
- [ ] Render embedded citation labels in learning-guide and QA prose.
- [ ] Add readable Wiki CSS without changing mutable local workflows or Demo allowlists.

## Verification

- [ ] Add deterministic parser/security/scoping/application tests.
- [ ] Extend Playwright rendering, navigation, citation, and responsive-layout checks.
- [ ] Run `uv run python scripts/regression.py --golden-demo-eval`.
- [ ] Run `uv run python scripts/regression.py --fast`.
- [ ] Run `uv run python scripts/regression.py --e2e`.
- [ ] Run `uv run python scripts/regression.py --browser-e2e`.
- [ ] Verify default local mode and public Demo routes at runtime without providers.
- [ ] Commit implementation and verification stages.
- [ ] Push deferred by user request.
