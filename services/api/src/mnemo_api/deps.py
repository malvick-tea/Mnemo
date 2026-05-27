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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.auth import verify_service_token
from mnemo_api.db import get_session
from mnemo_api.exceptions import AuthError, ForbiddenError
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


def get_qdrant(request: Request) -> object:
    return request.app.state.qdrant


def get_redis(request: Request) -> object:
    return request.app.state.redis


def get_minio(request: Request) -> object:
    return request.app.state.minio


def get_llm(request: Request) -> object:
    return request.app.state.llm


def get_embedder(request: Request) -> object:
    return request.app.state.embedder
