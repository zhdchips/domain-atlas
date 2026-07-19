FROM python:3.13-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

RUN pip install --no-cache-dir "uv>=0.7,<1"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/app/data \
    PORT=8000

RUN groupadd --system domainatlas && useradd --system --gid domainatlas --home-dir /app domainatlas

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src ./src
RUN mkdir -p /app/data && chown -R domainatlas:domainatlas /app

USER domainatlas
VOLUME ["/app/data"]
EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn domain_atlas.web.app:create_app --factory --host 0.0.0.0 --port \"$PORT\""]
