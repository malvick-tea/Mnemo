"""Query / RAG DTOs."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class QueryIn(BaseModel):
    query: str = Field(..., min_length=1, max_length=2_000)
    conversation_id: UUID | None = None
    top_k: int = Field(default=8, ge=1, le=20)


class Citation(BaseModel):
    note_id: UUID
    short_id: str           # first 8 chars of the UUID, used in the prompt
    title: str | None
    excerpt: str            # ≤300 chars
    captured_at: str
    source_type: str
    source_url: str | None = None


class QueryOut(BaseModel):
    query_id: UUID
    answer: str
    citations: list[Citation]
    latency_ms: int
    model_used: str


class QueryFeedbackIn(BaseModel):
    rating: Literal[-1, 0, 1]
