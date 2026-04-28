# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DDM_API_HOST=0.0.0.0 \
    DDM_API_PORT=8000 \
    DDM_API_RELOAD=false \
    DDM_ENVIRONMENT=container \
    DDM_DATABASE_URL=sqlite:////app/data/metadata.sqlite3 \
    DDM_OBJECT_STORE_BACKEND=local \
    DDM_OBJECT_STORE_ROOT=/app/data/objects \
    DDM_QUEUE_BROKER_URL=redis://localhost:6379/0 \
    DDM_QUEUE_RESULT_BACKEND=redis://localhost:6379/1 \
    DDM_QUEUE_NAME=ddm \
    DDM_WORKER_POOL=solo \
    DDM_DATA_ROOT=/app/data

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY frontend ./frontend
RUN uv sync --frozen --no-dev

RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.getenv('DDM_API_PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=2).read()"

CMD ["/app/.venv/bin/ddm-api"]
