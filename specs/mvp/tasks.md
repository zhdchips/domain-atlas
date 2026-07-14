# Domain Atlas MVP Tasks

## Phase 1: MVP Specification And Project Skeleton

- [x] Create SDD spec, plan, and task documents.
- [x] Add repository ignore rules for secrets and runtime artifacts.
- [x] Create Python package skeleton.
- [x] Add FastAPI app factory with health and home routes.
- [x] Add settings loader for local paths and provider env names.
- [x] Add basic pytest coverage.
- [x] Commit phase result.
- [ ] Push phase result. Blocked by missing GitHub credentials in this environment.

## Phase 2: Configuration, SQLite, And Base UI

- [x] Add SQLite connection and schema initialization.
- [x] Implement domain project repository.
- [x] Add create/list project routes and templates.
- [x] Add tests for project persistence and dashboard rendering.
- [ ] Commit and push phase result.

## Phase 3: Exa Source Discovery

- [ ] Implement Exa provider adapter.
- [ ] Add candidate normalization and authority scoring.
- [ ] Add search and confirmation UI.
- [ ] Persist source candidates.
- [ ] Add mocked provider tests.
- [ ] Commit and push phase result.

## Phase 4: Ingestion And Indexing

- [ ] Implement URL, Markdown, and PDF loaders.
- [ ] Add checksum and raw/normalized storage.
- [ ] Implement chunking with stable IDs and citation metadata.
- [ ] Implement embedding adapter and Chroma indexing.
- [ ] Add fixture ingestion tests.
- [ ] Commit and push phase result.

## Phase 5: Knowledge Build

- [ ] Implement lightweight workflow runner.
- [ ] Add source profile generation.
- [ ] Add concept extraction and concept edges.
- [ ] Add encyclopedia-style Wiki generation.
- [ ] Add five-stage learning path generation.
- [ ] Add artifact contract tests with mocked LLM.
- [ ] Commit and push phase result.

## Phase 6: Retrieval QA

- [ ] Implement Chroma retrieval for project chunks.
- [ ] Add citation-grounded answer generation.
- [ ] Add insufficient-evidence behavior.
- [ ] Persist QA records and render QA UI.
- [ ] Add QA integration tests.
- [ ] Commit and push phase result.

## Phase 7: Hardening

- [ ] Add README quickstart and architecture notes.
- [ ] Add live smoke command for configured providers.
- [ ] Run full tests and manual app smoke.
- [ ] Verify ignored secret/runtime files.
- [ ] Commit and push final MVP result.
