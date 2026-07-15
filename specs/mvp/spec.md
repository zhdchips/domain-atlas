# Domain Atlas MVP Specification

## Product Intent

Domain Atlas is a local-first agentic domain learning system. It helps a user learn a new field by ingesting trusted sources, compiling those sources into an encyclopedia-style LLM Wiki, deriving concept dependencies, generating a staged learning path, and answering questions with citation-backed provenance.

The MVP optimizes for a complete personal learning loop rather than multi-user scale, complex visual polish, or autonomous open-ended research.

## Users And Core Workflow

The MVP serves one local user.

Primary workflow:

1. Create a domain project with a Chinese-first default language.
2. Discover candidate authoritative sources with Exa, or add URL, Markdown, and PDF sources manually.
3. Confirm search candidates before ingestion.
4. Ingest accepted sources into normalized text, chunks, metadata, checksums, and Chroma embeddings.
5. Build a persistent LLM Wiki: source profiles, concepts, sectioned Wiki pages, concept graph edges, and a five-stage learning path.
6. Ask questions against the Wiki-first knowledge layer, with source chunk provenance retained for citations.

## Functional Requirements

### Domain Projects

- The app must support creating and listing domain projects.
- A project must store name, optional goal, level, language, status, timestamps, and build state.
- A project must store an `interaction_mode` value. Supported values are `expert` and `guided`.
- The default language must be Chinese, while `language` remains explicit for future switching.
- A project dashboard must expose source management, Wiki, learning path, and QA entry points.
- Expert mode must preserve manual search, confirmation, ingestion, and build controls.
- Guided mode must offer one-click autopilot discovery, filtering, ingestion, and knowledge build.

### Source Discovery

- The app must use Exa for automatic web source discovery.
- The default search request must collect 12 candidates and display the top 8.
- Candidate ingestion must require user confirmation.
- Candidates must include title, URL, summary/snippet, source type, available author/publisher/date metadata, and an authority reason or score.

### Source Ingestion

- The MVP must support URL, Markdown, and PDF sources.
- Each source must persist raw content when available, normalized text, metadata, checksum, status, and provenance.
- Chunking must create stable chunk IDs and citation metadata.
- Chunk embeddings must be written to local Chroma using the configured Qwen/DashScope embedding model.

### LLM Wiki Knowledge Build

- The build workflow must be a lightweight in-process pipeline, not LangGraph.
- The build workflow must compile source chunks into a persistent LLM Wiki, not just one-off generated artifacts.
- Wiki pages must contain stable slugs, topic paths, and sectioned encyclopedia content.
- Wiki sections must preserve section-level citations and source chunk provenance.
- Wiki pages and sections should include structured wiki links/backlinks where the model can infer related pages.
- Wiki pages must use an encyclopedia-entry style, not a tutorial tone.
- The learning path must have five default stages: introductory orientation, core concepts, key methods, practical applications, and advanced topics.
- Generated artifacts must preserve citation/provenance links wherever evidence is available.

### Retrieval QA

- QA must retrieve from Wiki sections first.
- Source chunks remain the evidence/provenance layer and may be consulted after Wiki retrieval.
- Answers must include Wiki section citations and retain source chunk provenance.
- If retrieved evidence is insufficient, the app must clearly state that the current knowledge base is insufficient and suggest missing source types.
- QA records must be persisted.

### Wiki Health

- The app must provide basic Wiki lint/health checks.
- Lint must detect Wiki sections without citations.
- Lint must detect duplicate page slugs or topic paths.
- Lint must detect orphan Wiki pages with no inbound backlinks, excluding the first/root page when appropriate.
- Lint output must be readable in tests and available to the UI.

### Guided Autopilot

- Guided mode must automatically search Exa candidates, filter authoritative sources, create URL sources, ingest them, and run the knowledge build.
- Autopilot must select at most five sources by default.
- Autopilot must require `authority_score >= 0.65`.
- Autopilot must prioritize `official_docs`, `paper`, `institution`, `repository`, and `encyclopedia` source types.
- Autopilot must accept at most two sources from the same domain.
- If no candidates pass filtering, autopilot must stop without ingestion and record a recoverable workflow failure.
- Autopilot must persist discovered candidates and mark auto-accepted candidates transparently.

### UI

- The UI must use FastAPI, Jinja, and HTMX.
- The MVP UI must prioritize clarity and repeated-use workflow over brand-heavy presentation.
- Required pages: project list/create, project dashboard, search candidate confirmation, source list, Wiki, Wiki lint, learning path, and QA.

## Non-Functional Requirements

- The app must run locally from a fresh checkout using README instructions.
- Secrets must stay in ignored `.env` files and must never be committed.
- Runtime data, uploads, Chroma collections, and SQLite databases must live under `data/` by default and must not be committed.
- Search, chat, and embedding clients must use OpenAI-compatible or provider-isolated adapters.
- Critical flows must have pytest coverage.

## Out Of Scope For MVP

- User accounts and authentication.
- Multi-user SaaS tenancy.
- Recursive crawling.
- OCR for scanned PDFs.
- Complex interactive graph visualization.
- LangGraph, Celery, Redis, or distributed task orchestration.
- Automatic ingestion of web search results without user confirmation.

## Acceptance Criteria

- A user can start the app locally and create a domain project.
- A user can search Exa candidates and choose which ones to ingest.
- A user can ingest URL, Markdown, and PDF sources.
- The system can build encyclopedia-style Wiki pages and a five-stage learning path.
- The system can store sectioned Wiki pages with slugs, links, backlinks, section citations, and source provenance.
- The system can answer Wiki-first questions with citations and persist QA records.
- The system can run guided autopilot from search through ingestion and build.
- Tests cover configuration, project creation, source discovery normalization, chunk/provenance behavior, Wiki section contracts, Wiki-first QA, guided/autopilot filtering, and QA insufficiency behavior.
- Smoke commands can verify Exa search, DeepSeek chat, and Qwen/DashScope embeddings from the local `.env`.
