"""Integration credential management. All payloads stored AES-GCM encrypted."""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from mnemo_api.crypto import decrypt, encrypt
from mnemo_api.deps import CurrentUser, SessionDep
from mnemo_api.models import Integration

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])

Kind = Literal["notion", "obsidian", "anki", "calendar"]


class IntegrationIn(BaseModel):
    kind: Kind
    config: dict[str, Any]
    is_active: bool = True


class IntegrationOut(BaseModel):
    kind: Kind
    is_active: bool
    has_credentials: bool
    last_synced_at: str | None


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(user: CurrentUser, session: SessionDep) -> list[IntegrationOut]:
    res = await session.execute(select(Integration).where(Integration.user_id == user.id))
    out: list[IntegrationOut] = []
    for i in res.scalars():
        out.append(
            IntegrationOut(
                kind=i.kind,  # type: ignore[arg-type]
                is_active=i.is_active,
                has_credentials=bool(i.config_encrypted),
                last_synced_at=i.last_synced_at.isoformat() if i.last_synced_at else None,
            )
        )
    return out


@router.post("", response_model=IntegrationOut)
async def upsert_integration(
    payload: IntegrationIn, user: CurrentUser, session: SessionDep
) -> IntegrationOut:
    blob = encrypt(json.dumps(payload.config).encode("utf-8"))
    res = await session.execute(
        select(Integration).where(
            Integration.user_id == user.id, Integration.kind == payload.kind
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        existing.config_encrypted = blob
        existing.is_active = payload.is_active
    else:
        session.add(
            Integration(
                user_id=user.id, kind=payload.kind,
                config_encrypted=blob, is_active=payload.is_active,
            )
        )
    await session.commit()
    return IntegrationOut(
        kind=payload.kind, is_active=payload.is_active,
        has_credentials=True, last_synced_at=None,
    )


@router.delete("/{kind}", status_code=204)
async def disable_integration(
    kind: Kind, user: CurrentUser, session: SessionDep
) -> None:
    res = await session.execute(
        select(Integration).where(Integration.user_id == user.id, Integration.kind == kind)
    )
    integ = res.scalar_one_or_none()
    if integ is None:
        raise HTTPException(404, "Integration not configured")
    integ.is_active = False
    await session.commit()


def _maybe_decrypt(integ: Integration) -> dict[str, Any]:
    """Internal helper for other services that need plaintext config."""
    return json.loads(decrypt(integ.config_encrypted).decode("utf-8"))


# Re-exported for use by the worker layer.
__all__ = ["router", "_maybe_decrypt"]
