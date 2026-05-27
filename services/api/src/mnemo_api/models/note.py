"""Notes — the canonical unit of capture — plus tags."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from mnemo_api.models.base import Base


class SourceType(str, enum.Enum):
    text = "text"
    voice = "voice"
    photo = "photo"
    document = "document"
    url = "url"
    forward = "forward"


class NoteStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('text','voice','photo','document','url','forward')",
            name="source_type_enum",
        ),
        CheckConstraint(
            "status IN ('pending','processing','ready','failed')",
            name="status_enum",
        ),
        Index("notes_user_created_idx", "user_id", "created_at"),
        Index("notes_status_idx", "status", postgresql_where="status != 'ready'"),
        Index("notes_tsv_idx", "content_tsv", postgresql_using="gin"),
        Index(
            "notes_trgm_idx",
            "processed_content",
            postgresql_using="gin",
            postgresql_ops={"processed_content": "gin_trgm_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)

    raw_content: Mapped[str | None] = mapped_column(Text, default=None)
    processed_content: Mapped[str | None] = mapped_column(Text, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    title: Mapped[str | None] = mapped_column(Text, default=None)
    source_url: Mapped[str | None] = mapped_column(Text, default=None)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default_factory=dict, server_default="{}"
    )
    blob_keys: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default_factory=list, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        default_factory=lambda: datetime.now(UTC),
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default_factory=lambda: datetime.now(UTC),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    # Generated column: search uses `to_tsvector('simple', ...)` over title +
    # processed_content + summary. We declare it as a Computed column so
    # Postgres maintains it transactionally.
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(title,'') || ' ' || "
            "coalesce(processed_content,'') || ' ' || coalesce(summary,''))",
            persisted=True,
        ),
        default=None,
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        default_factory=lambda: datetime.now(UTC),
    )


class NoteTag(Base):
    __tablename__ = "note_tags"
    __table_args__ = (
        CheckConstraint("source IN ('ai','user')", name="source_enum"),
    )

    note_id: Mapped[UUID] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(String(8), nullable=False, default="ai")
