"""Webhook payload DTOs (signed by HMAC at the transport layer)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class N8NNoteReadyIn(BaseModel):
    note_id: UUID
    title: str | None = None
    summary: str | None = None
    processed_content: str | None = None
    extracted_metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class N8NNoteFailedIn(BaseModel):
    note_id: UUID
    error_message: str
    retry_count: int = 0
