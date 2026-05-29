"""Capture endpoint DTOs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from mnemo_api.schemas.limits import bounded_mapping


class _WithSourceMetadata(BaseModel):
    """Mixin: a bounded free-form ``source_metadata`` blob."""

    source_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_metadata")
    @classmethod
    def _bound_source_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return bounded_mapping(value, what="source_metadata")


class CaptureTextIn(_WithSourceMetadata):
    content: str = Field(..., min_length=1, max_length=50_000)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CaptureURLIn(_WithSourceMetadata):
    url: AnyHttpUrl
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ForwardMetadata(BaseModel):
    """Provenance of a forwarded Telegram message.

    All fields optional because Telegram sometimes strips author info (e.g.
    forwards from channels with hidden senders).
    """

    origin_type: Literal["user", "chat", "channel", "hidden_user"] | None = None
    from_user_id: int | None = None
    from_user_name: str | None = None
    from_chat_id: int | None = None
    from_chat_title: str | None = None
    from_chat_username: str | None = None
    forward_date: datetime | None = None
    message_id: int | None = None


class CaptureForwardIn(_WithSourceMetadata):
    content: str = Field(..., min_length=1, max_length=50_000)
    forward: ForwardMetadata
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CaptureResponse(BaseModel):
    note_id: UUID
    status: Literal["pending", "processing", "ready", "failed"]
