"""FastAPI app factory + lifespan.

Heavy clients (Qdrant, Redis, MinIO, LLM, Embedder) are created once per
process at startup and attached to `app.state` so request handlers can grab
them via the deps in `mnemo_api.deps`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from minio import Minio
from prometheus_client import REGISTRY, make_asgi_app
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from mnemo_api import __version__
from mnemo_api.config import get_settings
from mnemo_api.exceptions import MnemoError
from mnemo_api.llm import make_embedder, make_llm
from mnemo_api.logging import configure_logging, get_logger
from mnemo_api.middlewares import (
    AccessLogMiddleware,
    CorrelationIdMiddleware,
    RateLimitMiddleware,
)
from mnemo_api.qdrant_setup import ensure_collection
from mnemo_api.routers import (
    capture,
    digest,
    health,
    integrations,
    notes,
    query,
    webhooks_n8n,
)
from mnemo_api.routers import (
    settings as settings_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("startup")

    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=(settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None),
    )
    await ensure_collection(qdrant, settings)

    redis: Redis = Redis.from_url(settings.redis_url, decode_responses=False)
    await redis.ping()

    minio = Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key.get_secret_value(),
        secure=settings.minio_use_tls,
    )
    if not minio.bucket_exists(settings.minio_bucket):
        minio.make_bucket(settings.minio_bucket)
        log.info("minio.bucket.created", bucket=settings.minio_bucket)

    llm = make_llm(settings)
    embedder = make_embedder(settings)

    app.state.qdrant = qdrant
    app.state.redis = redis
    app.state.minio = minio
    app.state.llm = llm
    app.state.embedder = embedder
    log.info("startup.complete", version=__version__, env=settings.env)

    try:
        yield
    finally:
        log.info("shutdown.begin")
        await qdrant.close()
        await redis.close()
        # OpenRouter / Ollama clients have aclose; embedders too.
        for component in (llm, embedder):
            close = getattr(component, "aclose", None)
            if callable(close):
                await close()
        log.info("shutdown.complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Mnemo Core API",
        version=__version__,
        docs_url="/docs" if settings.env == "development" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.env == "development" else None,
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RateLimitMiddleware)

    @app.exception_handler(MnemoError)
    async def _mnemo_error_handler(_request: object, exc: MnemoError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.error_code, "detail": str(exc)},
        )

    app.include_router(health.router)
    app.include_router(capture.router)
    app.include_router(query.router)
    app.include_router(notes.router)
    app.include_router(digest.router)
    app.include_router(settings_router.router)
    app.include_router(integrations.router)
    app.include_router(webhooks_n8n.router)

    if settings.metrics_enabled:
        app.mount("/metrics", make_asgi_app(registry=REGISTRY))

    return app


app = create_app()
