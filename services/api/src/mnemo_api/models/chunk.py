"""Chunks — one Note splits into N Chunks for embedding."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mnemo_api.models.base import Base


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("note_id", "chunk_index"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4, init=False)
    note_id: Mapped[UUID] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Mirrors a Qdrant point ID 1:1 so we can resolve chunks both ways.
    qdrant_point_id: Mapped[UUID] = mapped_column(nullable=False, default_factory=uuid4)
    token_count: Mapped[int | None] = mapped_column(Integer, default=None)
