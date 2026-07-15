# Domain Atlas MVP Implementation Plan

## Architecture

Domain Atlas will start as a Python monolith:

- `domain_atlas.web`: FastAPI routes, Jinja templates, HTMX partials.
- `domain_atlas.core`: settings, paths, database initialization, shared errors.
- `domain_atlas.domain`: project, source, chunk, artifact, and QA persistence.
- `domain_atlas.providers`: Exa search, OpenAI-compatible chat, and OpenAI-compatible embeddings.
- `domain_atlas.ingestion`: URL, Markdown, PDF normalization, chunking, checksum, provenance.
- `domain_atlas.workflow`: lightweight ordered build steps, guided autopilot, and stored run state.
- `domain_atlas.wiki`: Wiki section indexing, lint, links, and backlinks.
- `domain_atlas.qa`: Wiki-first retrieval, answer generation, citation enforcement.

SQLite stores business state. Chroma stores vectors. Local files under `data/` store uploads, raw source snapshots, normalized text, and generated Markdown artifacts when useful.

## SDD Phases

1. MVP specification and project skeleton.
2. Configuration, SQLite schema, repositories, and base UI.
3. Exa source discovery and candidate confirmation.
4. URL/Markdown/PDF ingestion, chunking, provenance, and Chroma indexing.
5. LLM workflow for source profiles, concepts, Wiki, graph edges, and learning path.
6. Retrieval QA with citations and insufficiency behavior.
7. Hardening: README, smoke tests, regression tests, and final local verification.
8. LLM Wiki upgrade: Wiki sections, links, backlinks, Wiki indexing, and lint.
9. Wiki-first QA.
10. Interaction modes and guided autopilot.

Each phase updates this specification set if implementation evidence reveals a better decision. Each completed phase must pass relevant tests, then be committed locally. Push is deferred by user decision for this iteration.

## Key Design Decisions

- Use `uv` for development commands when available, while keeping standard `python -m` commands documented.
- Use a small custom workflow runner because the MVP pipeline is ordered and inspectable.
- Keep Domain Atlas data models independent from LlamaIndex, Chroma, Exa, or any model provider.
- Use provider adapters with explicit configuration and safe error messages.
- Treat citations as first-class data attached to chunks and generated artifacts.
- Treat Wiki sections as the primary retrievable knowledge layer; source chunks are the provenance layer.
- Guided mode is transparent autopilot, not hidden ingestion: selected candidates and workflow steps remain inspectable.

## Data Model Overview

Initial core tables:

- `domain_projects`
- `sources`
- `source_candidates`
- `chunks`
- `workflow_runs`
- `workflow_steps`
- `concepts`
- `concept_edges`
- `wiki_pages`
- `wiki_sections`
- `wiki_links`
- `learning_modules`
- `qa_records`

Early phases may introduce tables incrementally, but final MVP must cover the full model.

## Verification Strategy

- Unit tests for settings, adapters, ingestion, chunking, citations, workflow steps, and repositories.
- Integration tests for create project, discover candidates, ingest fixture sources, build artifacts, and QA.
- Wiki-first tests for section persistence, links/backlinks, lint, and QA retrieval order.
- Guided mode tests for interaction mode persistence, source filtering, autopilot source creation, ingestion, and build handoff.
- Optional live smoke tests for Exa, chat, and embedding using `.env`, excluded from default pytest.
- Manual UI verification before final completion.
