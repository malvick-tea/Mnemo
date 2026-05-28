"""Capture endpoint DTOs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field


class CaptureTextIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=50_000)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class CaptureURLIn(BaseModel):
    url: AnyHttpUrl
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_metadata: dict[str, Any] = Field(default_factory=dict)


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


class CaptureForwardIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=50_000)
    forward: ForwardMetadata
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class CaptureResponse(BaseModel):
    note_id: UUID
    status: Literal["pending", "processing", "ready", "failed"]
