# Domain Atlas

Domain Atlas is a local-first agentic domain learning system. It ingests trusted sources, builds an encyclopedia-style LLM Wiki, generates concept dependencies and learning paths, and answers questions with citations.

This repository is built with Spec-Driven Development. See `specs/mvp/` for the active MVP specification, plan, and tasks.

## Architecture

Domain Atlas treats the generated Wiki as the primary knowledge layer:

- Sources and chunks are the evidence layer. They preserve raw provenance, citation labels, and embeddings for source-level fallback.
- Wiki pages and Wiki sections are the learning layer. They keep stable slugs, topic paths, section citations, source chunk provenance, and Wiki links.
- Wiki workspace pages add Karpathy-style organization with typed paths such as `wiki/index`, `wiki/log`, `wiki/sources/...`, `wiki/concepts/...`, `wiki/synthesis/...`, and `wiki/templates/...`.
- QA searches Wiki sections first, then falls back to source chunks only when Wiki evidence is missing.
- Wiki lint checks missing section citations, duplicate slugs/topic paths, and orphaned pages.

The MVP supports two interaction modes:

- Guided mode: start from a domain name, automatically search Exa, select authoritative sources, ingest them, and build the LLM Wiki and learning path.
- Expert mode: keep manual control over search, candidate confirmation, source ingestion, and knowledge build.

## Quickstart

```bash
uv sync --extra dev
uv run pytest
uv run uvicorn domain_atlas.web.app:create_app --factory --reload
```

If PyPI is slow from the current network, use:

```bash
uv sync --extra dev --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

Then open `http://127.0.0.1:8000`.

## Configuration

Copy `.env.example` to `.env` and fill local secrets:

- `EXA_API_KEY` for Exa search.
- `LLM_BASE_URL`, `LLM_API_KEY`, and `CHAT_MODEL` for the OpenAI-compatible chat provider.
- `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, and `EMBEDDING_DIMENSIONS` for the OpenAI-compatible embedding provider.

Secrets belong in an ignored `.env` file. Runtime data belongs under `data/`.

## Provider Smoke Test

```bash
uv run python scripts/smoke_providers.py
```

The smoke test verifies Exa search, chat completion, and embedding generation without printing secrets.

## Layered Regression

Domain Atlas uses layered regression checks:

```bash
uv run python scripts/regression.py --fast
uv run python scripts/regression.py --e2e
uv run python scripts/regression.py --browser-e2e
uv run python scripts/regression.py --intake-eval
uv run python scripts/regression.py --live
uv run python scripts/regression.py --live-intake-eval
uv run python scripts/regression.py --live-e2e
uv run python scripts/regression.py --live-guided-e2e
```

Fast and E2E checks are deterministic and do not call live providers. Fast regression also replays the versioned intake evaluation set. Browser E2E uses Playwright against deterministic Wiki and guided-workflow fixtures, catching real interaction, status, and layout regressions. `--live-intake-eval` calls the chat model once for each intake case and writes a normalized report under `reports/intake/`; it creates no project or knowledge artifacts. Live checks verify configured external provider availability, `--live-e2e` runs the fixed Markdown-to-Wiki build, and `--live-guided-e2e` runs an isolated real search, URL-ingestion, build, and QA flow in a temporary data directory.

Before the first browser E2E run:

```bash
uv sync --extra dev
uv run python -m playwright install chromium
```

At the end of an SDD iteration, run at least `--fast` and `--browser-e2e`; run `--live-e2e` for build/embedding/QA changes and `--live-guided-e2e` for discovery, URL ingestion, candidate ranking, or provider-facing guided-workflow changes. See the latest iteration spec for the SDD maintenance checklist.

## Wiki Workspace

The Wiki UI follows the Karpathy-style LLM Wiki pattern as a Web workspace over SQLite. It groups pages by type, shows `index` first, keeps a build `log`, and exposes source, concept, synthesis, and template pages with stable `wiki/...` paths. Markdown vault export is intentionally deferred; see `specs/iterations/2026-07-15-wiki-workspace/`.

## MVP Flow

1. Create a domain project.
2. Choose guided mode for one-click setup or expert mode for manual control.
3. In guided mode, run autopilot to search, filter, ingest, and build.
4. In expert mode, search Exa candidates or add URL/Markdown/PDF sources manually.
5. Read the generated Wiki and learning path.
6. Ask Wiki-first, citation-grounded questions.

Autopilot keeps the process transparent by saving discovered candidates, marking auto-accepted candidates, creating URL sources, recording workflow steps, and showing recent workflow logs on the project dashboard.
