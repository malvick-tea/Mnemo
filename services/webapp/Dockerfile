# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /usr/local/bin/

WORKDIR /app
# Re-use shared API package (config + models + crypto).
COPY ../api /app/api
COPY pyproject.toml ./
RUN uv venv /opt/venv \
 && uv pip install --python /opt/venv/bin/python -e /app/api \
 && uv pip install --python /opt/venv/bin/python -r <(uv pip compile pyproject.toml)

FROM base AS dev
RUN uv pip install --python /opt/venv/bin/python ".[dev]"
COPY src ./src
EXPOSE 8080
CMD ["uvicorn", "mnemo_webapp.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]

FROM base AS prod
COPY src ./src
RUN useradd --system --uid 10001 --no-create-home mnemo
USER mnemo
EXPOSE 8080
CMD ["uvicorn", "mnemo_webapp.main:app", "--host", "0.0.0.0", "--port", "8080"]
