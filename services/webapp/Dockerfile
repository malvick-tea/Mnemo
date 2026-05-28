# syntax=docker/dockerfile:1.7
#
# Build context is the repo ROOT (not services/webapp/). See
# services/workers/Dockerfile for the rationale.

FROM python:3.12-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /usr/local/bin/

WORKDIR /app
COPY services/api /api
COPY services/webapp/pyproject.toml /app/pyproject.toml
RUN uv venv /opt/venv \
 && uv pip install --python /opt/venv/bin/python -e /api \
 && uv pip install --python /opt/venv/bin/python -r <(uv pip compile /app/pyproject.toml)

FROM base AS dev
RUN uv pip install --python /opt/venv/bin/python -e "/app[dev]"
COPY services/webapp/src /app/src
EXPOSE 8080
CMD ["uvicorn", "mnemo_webapp.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]

FROM base AS prod
COPY services/webapp/src /app/src
RUN useradd --system --uid 10001 --no-create-home mnemo
USER mnemo
EXPOSE 8080
CMD ["uvicorn", "mnemo_webapp.main:app", "--host", "0.0.0.0", "--port", "8080"]
