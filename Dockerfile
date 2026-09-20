FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY services ./services
COPY scripts ./scripts

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn services.http.app:app --host 0.0.0.0 --port 8000"]
