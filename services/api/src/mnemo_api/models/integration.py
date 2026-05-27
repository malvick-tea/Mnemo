"""Per-user external-service integrations (Notion, Obsidian, etc.).

`config_encrypted` is the AES-GCM ciphertext of the credentials blob; key
material lives only in `MNEMO_ENCRYPTION_KEY`. See `mnemo_api.crypto`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from mnemo_api.models.base import Base


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("user_id", "kind"),
        CheckConstraint(
            "kind IN ('notion','obsidian','anki','calendar')", name="kind_enum"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    config_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
