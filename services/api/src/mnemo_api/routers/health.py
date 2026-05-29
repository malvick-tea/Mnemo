"""Liveness + readiness."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from mnemo_api.db import session_factory

router = APIRouter(tags=["health"])


@router.get("/v1/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/v1/readyz")
async def readyz(request: Request) -> dict[str, str]:
    state = request.app.state

    # Postgres — connectivity *and* schema. A bare `SELECT 1` succeeds against
    # an empty database, so an install on a fresh volume would report ready
    # while every application table is missing (migrations not yet applied).
    # Touching a core table makes readiness fail until `alembic upgrade head`
    # has run.
    try:
        async with session_factory()() as s:
            await s.execute(text("SELECT 1"))
            await s.execute(text("SELECT 1 FROM users LIMIT 1"))
    except Exception as exc:
        raise HTTPException(503, f"postgres not ready or schema not migrated: {exc}") from exc

    # Redis
    try:
        pong = await state.redis.ping()
        if not pong:
            raise HTTPException(503, "redis ping returned falsy")
    except Exception as exc:
        raise HTTPException(503, f"redis unavailable: {exc}") from exc

    # Qdrant — read collection list (lightweight)
    try:
        await state.qdrant.get_collections()
    except Exception as exc:
        raise HTTPException(503, f"qdrant unavailable: {exc}") from exc

    return {"status": "ready"}
