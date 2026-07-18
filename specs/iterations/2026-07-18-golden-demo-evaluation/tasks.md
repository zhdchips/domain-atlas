# Golden Demo and Evaluation Tasks

## Design

- [x] Audit the existing public catalog, routes, templates, and regression layers.
- [x] Verify the four selected first-party sources and define the 25-case scoring contract.
- [x] Create the independent iteration specification, plan, and task record.
- [x] Commit the design stage.

## Golden Catalog

- [x] Add source metadata and citation-link mapping.
- [x] Enrich the Wiki, ten-question overview, learning modules, and cited QA examples.
- [x] Add a read-only evaluation summary route and improve evidence links in public views.
- [x] Document the Demo walkthrough and evaluation limitations in README.

## Evaluation

- [x] Add the versioned evaluation manifest, rubric, manual review, and baseline result artifacts.
- [x] Implement deterministic scoring and JSON/Markdown report generation.
- [x] Add evaluator tests including a deliberately broken catalog case.

## Verification

- [ ] Extend deterministic public Demo checks and Playwright navigation assertions.
- [ ] Run the golden evaluator and record its baseline result.
- [ ] Run `uv run python scripts/regression.py --fast`.
- [ ] Run `uv run python scripts/regression.py --e2e`.
- [ ] Run `uv run python scripts/regression.py --browser-e2e`.
- [ ] Run one isolated `uv run python scripts/regression.py --live-e2e` and report it separately.
- [ ] Verify public Demo mode remains zero-provider and default local mode still works.
- [ ] Commit implementation and verification stages.
- [ ] Push deferred by user request.
