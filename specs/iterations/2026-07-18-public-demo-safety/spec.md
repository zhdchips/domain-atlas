# Public Read-Only Demo Safety Spec

## Purpose

Make Domain Atlas safe to deploy as an anonymous portfolio demo without exposing the local-first application's mutable workflows, provider credentials, project data, or API budget.

## User Problem

The normal application is intentionally a writable local tool. It can create projects, fetch arbitrary URLs, accept uploads, run background workflows, and call Exa, LLM, and embedding providers. Serving that surface anonymously would permit unbounded costs and could expose local data.

## Public Demo Model

- `PUBLIC_DEMO_MODE=true` enables a distinct, read-only surface rooted at `/demo`.
- `/demo` reads a version-controlled in-memory catalog. It does not initialize, open, read, or write the configured SQLite, Chroma, upload, or source-artifact paths.
- The catalog contains one curated `Agent Harness Engineering` project with source/provenance summaries, Wiki pages, a concept-oriented learning path, and pre-generated cited QA records.
- `/demo`, `/demo/wiki`, `/demo/wiki/{page_path}`, `/demo/path`, and `/demo/qa` are the only user-facing application routes in public mode. `/health` and `/static/...` remain available for operations and assets.
- `/` redirects to `/demo`; all `/domains/...`, `/docs`, `/openapi.json`, and unknown application routes return `404` before endpoint processing.
- The Demo has no POST routes. A POST to `/demo` or to any normal mutation endpoint returns `404` and cannot call a provider or persist data.

## Safety Boundary

- The public-mode middleware is the first application gate. It prevents FastAPI endpoint code, form parsing, workflow submission, repository access, and provider factories from being reached for disallowed paths.
- Public mode skips normal database initialization and interruption recovery. It must remain operable with a nonexistent `DATA_DIR`.
- The seed contains no credentials, user data, local paths, or runtime-derived values. Its sources are public references only.
- Default `PUBLIC_DEMO_MODE=false` keeps the existing local-first app unchanged, including project creation and mutable workflows.
- Anonymous writable trial is explicitly out of scope. It requires a future independent design for SSRF controls, file limits, rate limits, quotas, concurrency limits, authentication, and tenant isolation.

## UI Requirements

- Demo navigation exposes Overview, Wiki, Learning Path, and Cited QA.
- The overview presents the selected domain, architecture-level metrics, and source provenance without actions that mutate state.
- The QA page contains pre-generated question/answer examples and has no form, text input, or submit control.
- Existing local templates retain their current writable controls in local-first mode.

## Acceptance Criteria

- Deterministic app tests prove public routes render their catalog content, ordinary local project content cannot be retrieved, and mutation POST paths all return `404` with zero provider calls.
- A test starts public mode with a nonexistent data directory and proves no SQLite database is created.
- Local-mode tests continue proving project creation, source ingestion, and build routing work.
- Browser E2E loads `/demo`, navigates its core pages, finds no forms or submit buttons, and confirms representative write paths are rejected.
- `--fast`, `--e2e`, and `--browser-e2e` pass without a live provider check. Public Demo mode deliberately makes zero provider calls.
