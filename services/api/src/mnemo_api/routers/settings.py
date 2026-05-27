"""Per-user settings (JSONB blob on `users.settings`)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from mnemo_api.deps import CurrentUser, SessionDep

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class SettingsOut(BaseModel):
    settings: dict[str, Any]


class SettingsPatch(BaseModel):
    settings: dict[str, Any]


@router.get("", response_model=SettingsOut)
async def get_settings_endpoint(user: CurrentUser) -> SettingsOut:
    return SettingsOut(settings=user.settings or {})


@router.patch("", response_model=SettingsOut)
async def patch_settings(
    payload: SettingsPatch, user: CurrentUser, session: SessionDep
) -> SettingsOut:
    merged = dict(user.settings or {})
    merged.update(payload.settings)
    user.settings = merged
    await session.commit()
    return SettingsOut(settings=merged)
