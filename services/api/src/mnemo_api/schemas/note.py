"""Note read/update DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TagOut(BaseModel):
    id: UUID
    name: str
    color: str | None = None
    count: int | None = None


class NoteOut(BaseModel):
    id: UUID
    source_type: Literal["text", "voice", "photo", "document", "url", "forward"]
    title: str | None
    summary: str | None
    raw_content: str | None
    processed_content: str | None
    source_url: str | None
    tags: list[TagOut] = Field(default_factory=list)
    status: str
    captured_at: datetime
    created_at: datetime
    processed_at: datetime | None
    source_metadata: dict[str, Any]


class NotePatch(BaseModel):
    title: str | None = None
    summary: str | None = None
    processed_content: str | None = None
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)


class AnkiCardOut(BaseModel):
    type: Literal["basic", "cloze"]
    front: str | None = None
    back: str | None = None
    text: str | None = None


class AnkiCardsOut(BaseModel):
    note_id: UUID
    cards: list[AnkiCardOut]
    model_used: str
