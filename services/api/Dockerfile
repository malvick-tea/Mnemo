# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /uvx /usr/local/bin/

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH"

# ── deps layer (cacheable) ──────────────────────────────────────────────────
COPY pyproject.toml ./
COPY README.md ./
COPY src ./src
COPY alembic.ini ./
RUN uv venv /opt/venv \
 && uv pip compile pyproject.toml -o /tmp/requirements.txt \
 && uv pip install --python /opt/venv/bin/python -r /tmp/requirements.txt \
 && uv pip install --python /opt/venv/bin/python -e . --no-deps \
 && rm /tmp/requirements.txt

# ── dev image ───────────────────────────────────────────────────────────────
FROM base AS dev
RUN uv pip install --python /opt/venv/bin/python ".[dev]"
COPY tests ./tests
EXPOSE 8000 9100
CMD ["uvicorn", "mnemo_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── prod image ──────────────────────────────────────────────────────────────
FROM base AS prod
RUN useradd --system --uid 10001 --no-create-home mnemo
USER mnemo
EXPOSE 8000 9100
CMD ["uvicorn", "mnemo_api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
