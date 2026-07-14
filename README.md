# Domain Atlas

Domain Atlas is a local-first agentic domain learning system. It ingests trusted sources, builds an encyclopedia-style LLM Wiki, generates concept dependencies and learning paths, and answers questions with citations.

This repository is being built with Spec-Driven Development. See `specs/mvp/` for the active MVP specification, plan, and tasks.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run uvicorn domain_atlas.web.app:create_app --factory --reload
```

If PyPI is slow from the current network, use:

```bash
uv sync --extra dev --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

Secrets belong in an ignored `.env` file. Runtime data belongs under `data/`.
