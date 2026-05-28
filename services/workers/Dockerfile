# syntax=docker/dockerfile:1.7
#
# Build context is the repo ROOT (not services/workers/) so we can COPY
# both the workers source AND the shared mnemo-api package. The matching
# compose entry:
#
#   workers:
#     build:
#       context: .
#       dockerfile: services/workers/Dockerfile
#
# Layout inside the image:
#   /api/        — shared mnemo-api source (referenced via uv.sources)
#   /app/        — workers project root (pyproject.toml + src/)

FROM python:3.12-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH

# ffmpeg: audio decoding for faster-whisper
# libgomp1: OpenMP runtime needed by ctranslate2 (faster-whisper backend)
# libpq5: asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl libpq5 ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /usr/local/bin/

WORKDIR /app
COPY services/api /api
COPY services/workers/pyproject.toml /app/pyproject.toml
RUN uv venv /opt/venv \
 && uv pip install --python /opt/venv/bin/python -e /api \
 && uv pip install --python /opt/venv/bin/python -r <(uv pip compile /app/pyproject.toml)

FROM base AS dev
RUN uv pip install --python /opt/venv/bin/python -e "/app[dev]"
COPY services/workers/src /app/src
CMD ["dramatiq", "mnemo_workers.tasks", "--processes", "2", "--threads", "4", "--watch", "/app/src"]

FROM base AS prod
COPY services/workers/src /app/src
RUN useradd --system --uid 10001 --no-create-home mnemo
USER mnemo
CMD ["dramatiq", "mnemo_workers.tasks", "--processes", "2", "--threads", "4"]
