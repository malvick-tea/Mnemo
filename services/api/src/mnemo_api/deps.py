"""FastAPI dependencies (DI).

Kept small: get a session, get the current user, get long-lived clients
(Qdrant, Redis, MinIO, LLM, embedder). Long-lived clients are constructed
lazily and cached on `app.state` in `main.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from minio import Minio
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.auth import verify_service_token
from mnemo_api.db import get_session
from mnemo_api.exceptions import AuthError, ForbiddenError
from mnemo_api.llm.base import Embedder, LLMClient
from mnemo_api.models import User


async def session_dep() -> AsyncIterator[AsyncSession]:
    async for s in get_session():
        yield s


SessionDep = Annotated[AsyncSession, Depends(session_dep)]


async def current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing Bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        tg_user_id = verify_service_token(token)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc

    result = await session.execute(
        select(User).where(User.tg_user_id == tg_user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        # Auto-provision on first contact (single-user, whitelist already
        # enforced at the bot edge).
        user = User(tg_user_id=tg_user_id)
        session.add(user)
        await session.flush()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def user_or_id(user: CurrentUser, note_user_id: UUID) -> User:
    if user.id != note_user_id:
        raise ForbiddenError("This note belongs to another user")
    return user


def get_qdrant(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant  # type: ignore[no-any-return]


def get_redis(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]


def get_minio(request: Request) -> Minio:
    return request.app.state.minio  # type: ignore[no-any-return]


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm  # type: ignore[no-any-return]


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder  # type: ignore[no-any-return]


RedisDep = Annotated[Redis, Depends(get_redis)]
MinioDep = Annotated[Minio, Depends(get_minio)]
QdrantDep = Annotated[AsyncQdrantClient, Depends(get_qdrant)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
