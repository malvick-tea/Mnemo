"""Note read/update DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
    error_message: str | None = None
    captured_at: datetime
    created_at: datetime
    processed_at: datetime | None
    source_metadata: dict[str, Any]


class NotePatch(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    summary: str | None = Field(default=None, max_length=10_000)
    processed_content: str | None = Field(default=None, max_length=200_000)
    add_tags: list[str] = Field(default_factory=list, max_length=50)
    remove_tags: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("add_tags", "remove_tags")
    @classmethod
    def _bound_tag_names(cls, value: list[str]) -> list[str]:
        for tag in value:
            if not tag.strip():
                raise ValueError("tag names must be non-empty")
            if len(tag) > 64:
                raise ValueError("tag name too long (max 64 chars)")
        return value


class AnkiCardOut(BaseModel):
    type: Literal["basic", "cloze"]
    front: str | None = None
    back: str | None = None
    text: str | None = None


class AnkiCardsOut(BaseModel):
    note_id: UUID
    cards: list[AnkiCardOut]
    model_used: str
