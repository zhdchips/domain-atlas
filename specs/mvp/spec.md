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
5. Build domain artifacts: source profiles, concepts, encyclopedia-style Wiki pages, concept graph edges, and a five-stage learning path.
6. Ask questions and receive answers grounded in retrieved chunks with citations.

## Functional Requirements

### Domain Projects

- The app must support creating and listing domain projects.
- A project must store name, optional goal, level, language, status, timestamps, and build state.
- The default language must be Chinese, while `language` remains explicit for future switching.
- A project dashboard must expose source management, Wiki, learning path, and QA entry points.

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

### Knowledge Build

- The build workflow must be a lightweight in-process pipeline, not LangGraph.
- The build workflow must produce source profiles, concepts, Wiki pages, concept graph edges, and learning modules.
- Wiki pages must use an encyclopedia-entry style, not a tutorial tone.
- The learning path must have five default stages: introductory orientation, core concepts, key methods, practical applications, and advanced topics.
- Generated artifacts must preserve citation/provenance links wherever evidence is available.

### Retrieval QA

- QA must retrieve project chunks from Chroma.
- Answers must include citations to source chunks.
- If retrieved evidence is insufficient, the app must clearly state that the current knowledge base is insufficient and suggest missing source types.
- QA records must be persisted.

### UI

- The UI must use FastAPI, Jinja, and HTMX.
- The MVP UI must prioritize clarity and repeated-use workflow over brand-heavy presentation.
- Required pages: project list/create, project dashboard, search candidate confirmation, source list, Wiki, learning path, and QA.

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
- The system can answer questions with citations and persist QA records.
- Tests cover configuration, project creation, source discovery normalization, chunk/provenance behavior, artifact generation contracts, and QA insufficiency behavior.
- Smoke commands can verify Exa search, DeepSeek chat, and Qwen/DashScope embeddings from the local `.env`.
