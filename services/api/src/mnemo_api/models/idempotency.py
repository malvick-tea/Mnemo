"""Idempotency-key table for webhook replay protection.

Rows older than 24h are purged by a Dramatiq cron actor; the timestamp window
on incoming webhooks (5 minutes) makes the table small enough that a single
sweep is cheap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mnemo_api.models.base import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (Index("idempotency_created_idx", "created_at"),)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        default_factory=lambda: datetime.now(UTC),
    )
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
