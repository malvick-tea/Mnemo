"""Per-user settings (JSONB blob on `users.settings`)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from mnemo_api.deps import CurrentUser, SessionDep
from mnemo_api.schemas.limits import MAX_CONFIG_BYTES, MAX_CONFIG_KEYS, bounded_mapping

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class SettingsOut(BaseModel):
    settings: dict[str, Any]


class SettingsPatch(BaseModel):
    settings: dict[str, Any]

    @field_validator("settings")
    @classmethod
    def _bound_settings(cls, value: dict[str, Any]) -> dict[str, Any]:
        return bounded_mapping(
            value, what="settings", max_keys=MAX_CONFIG_KEYS, max_bytes=MAX_CONFIG_BYTES
        )


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
