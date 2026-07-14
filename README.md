# Domain Atlas

Domain Atlas is a local-first agentic domain learning system. It ingests trusted sources, builds an encyclopedia-style LLM Wiki, generates concept dependencies and learning paths, and answers questions with citations.

This repository is built with Spec-Driven Development. See `specs/mvp/` for the active MVP specification, plan, and tasks.

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

## MVP Flow

1. Create a domain project.
2. Search Exa candidates or add URL/Markdown/PDF sources manually.
3. Confirm candidates and ingest sources.
4. Build the knowledge artifacts.
5. Read the generated Wiki and learning path.
6. Ask citation-grounded questions.
