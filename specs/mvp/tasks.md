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
