"""Query log — every `/v1/query` is recorded for analytics + RAG eval."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from mnemo_api.models.base import Base


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text, default=None)
    cited_note_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(__import__("sqlalchemy").Uuid),
        nullable=False, default_factory=list, server_default="{}"
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    model_used: Mapped[str | None] = mapped_column(String(128), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        default_factory=lambda: datetime.now(UTC),
    )
    user_feedback: Mapped[int | None] = mapped_column(SmallInteger, default=None)
