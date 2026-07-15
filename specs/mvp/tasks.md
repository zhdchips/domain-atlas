# Domain Atlas MVP Tasks

## Phase 1: MVP Specification And Project Skeleton

- [x] Create SDD spec, plan, and task documents.
- [x] Add repository ignore rules for secrets and runtime artifacts.
- [x] Create Python package skeleton.
- [x] Add FastAPI app factory with health and home routes.
- [x] Add settings loader for local paths and provider env names.
- [x] Add basic pytest coverage.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 2: Configuration, SQLite, And Base UI

- [x] Add SQLite connection and schema initialization.
- [x] Implement domain project repository.
- [x] Add create/list project routes and templates.
- [x] Add tests for project persistence and dashboard rendering.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 3: Exa Source Discovery

- [x] Implement Exa provider adapter.
- [x] Add candidate normalization and authority scoring.
- [x] Add search and confirmation UI.
- [x] Persist source candidates.
- [x] Add mocked provider tests.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 4: Ingestion And Indexing

- [x] Implement URL, Markdown, and PDF loaders.
- [x] Add checksum and raw/normalized storage.
- [x] Implement chunking with stable IDs and citation metadata.
- [x] Implement embedding adapter and Chroma indexing.
- [x] Add fixture ingestion tests.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 5: Knowledge Build

- [x] Implement lightweight workflow runner.
- [x] Add source profile generation.
- [x] Add concept extraction and concept edges.
- [x] Add encyclopedia-style Wiki generation.
- [x] Add five-stage learning path generation.
- [x] Add artifact contract tests with mocked LLM.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 6: Retrieval QA

- [x] Implement Chroma retrieval for project chunks.
- [x] Add citation-grounded answer generation.
- [x] Add insufficient-evidence behavior.
- [x] Persist QA records and render QA UI.
- [x] Add QA integration tests.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 7: Hardening

- [x] Add README quickstart and architecture notes.
- [x] Add live smoke command for configured providers.
- [x] Run full tests and manual app smoke.
- [x] Verify ignored secret/runtime files.
- [x] Commit final MVP result.
- [x] Push deferred by user for now.

## Phase 8: LLM Wiki Upgrade SDD

- [x] Update spec for Wiki-first architecture and guided/expert interaction modes.
- [x] Update plan for Wiki sections, Wiki-first QA, lint, and autopilot phases.
- [x] Add implementation tasks for this iteration.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 9: Wiki Sections, Links, Index, And Lint

- [x] Add SQLite schema for wiki sections and wiki links.
- [x] Extend artifact repository to persist sections, slugs, links, backlinks, and source provenance.
- [x] Update knowledge build workflow to accept sectioned Wiki payloads.
- [x] Add Wiki section vector indexing and retrieval helpers.
- [x] Add Wiki lint service for missing citations, orphan pages, and duplicate slugs/topic paths.
- [x] Add tests for section persistence, links/backlinks, indexing, and lint.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 10: Wiki-First QA

- [x] Update QA service to retrieve Wiki sections first.
- [x] Preserve source chunk provenance in QA records.
- [x] Add insufficient-evidence behavior for missing Wiki evidence.
- [x] Update QA UI to show Wiki citations and source provenance.
- [x] Add tests proving QA uses Wiki sections before source chunks.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 11: Interaction Modes

- [x] Add `interaction_mode` to DomainProject schema and model.
- [x] Add expert/guided mode selector in project creation UI.
- [x] Preserve expert mode manual flows.
- [x] Add tests for interaction mode defaults and persistence.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 12: Guided Autopilot

- [x] Add candidate filtering policy for guided mode.
- [x] Implement autopilot workflow for search, filtering, source creation, ingestion, and build.
- [x] Persist transparent workflow steps and auto-accepted candidates.
- [x] Add guided mode UI action and result status.
- [x] Add tests for filtering and mocked autopilot execution.
- [x] Commit phase result.
- [x] Push deferred by user for now.

## Phase 13: Final Hardening

- [x] Update README with LLM Wiki architecture and interaction modes.
- [x] Run full pytest suite.
- [x] Run provider smoke if `.env` is configured.
- [x] Verify ignored secret/runtime files.
- [x] Commit final iteration result.
- [x] Push deferred by user for now.

## Phase 14: Navigation And Layered Regression

- [x] Track detailed SDD in `specs/iterations/2026-07-15-layered-regression/`.
- [x] Fix dashboard Wiki, learning path, and QA navigation cards.
- [x] Add deterministic E2E regression coverage for guided domain flow.
- [x] Add layered regression runner for fast, e2e, and live checks.
- [x] Commit phase result.
- [x] Push deferred by user for now.
