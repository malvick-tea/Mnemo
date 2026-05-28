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

    # Postgres
    try:
        async with session_factory()() as s:
            await s.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, f"postgres unavailable: {exc}") from exc

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
