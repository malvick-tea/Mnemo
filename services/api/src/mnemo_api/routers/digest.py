"""Digest endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from mnemo_api.config import get_settings
from mnemo_api.deps import CurrentUser, SessionDep
from mnemo_api.services.digest import daily_digest, weekly_review
from mnemo_api.services.usage import assert_budget

router = APIRouter(prefix="/v1/digest", tags=["digest"])


class DigestIn(BaseModel):
    mode: Literal["preview", "send"] = "preview"


class DigestOut(BaseModel):
    text: str


@router.post("/today", response_model=DigestOut)
async def today_digest(
    payload: DigestIn,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> DigestOut:
    await assert_budget(request.app.state.redis, user.id, get_settings().user_daily_token_cap)
    text = await daily_digest(session, request.app.state.llm, user_id=user.id)
    # TODO(milestone-3): when mode=="send" enqueue Telegram delivery via Redis pubsub.
    return DigestOut(text=text)


@router.get("/weekly", response_model=DigestOut)
async def weekly(
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> DigestOut:
    await assert_budget(request.app.state.redis, user.id, get_settings().user_daily_token_cap)
    text = await weekly_review(session, request.app.state.llm, user_id=user.id)
    return DigestOut(text=text)
