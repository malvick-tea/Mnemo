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


class CaptureResponse(BaseModel):
    note_id: UUID
    status: Literal["pending", "processing", "ready", "failed"]
