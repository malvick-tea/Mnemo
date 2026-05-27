"""Initial schema (users, notes, tags, chunks, queries, integrations, idempotency).

Revision ID: 0001
Revises:
Create Date: 2026-02-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("tg_username", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "notes",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("processed_content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("blob_keys", postgresql.ARRAY(sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "content_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', coalesce(title,'') || ' ' || "
                "coalesce(processed_content,'') || ' ' || coalesce(summary,''))",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.CheckConstraint(
            "source_type IN ('text','voice','photo','document','url','forward')",
            name="ck_notes_source_type_enum",
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','ready','failed')",
            name="ck_notes_status_enum",
        ),
    )
    op.create_index("notes_user_created_idx", "notes", ["user_id", "created_at"])
    op.create_index(
        "notes_status_idx",
        "notes",
        ["status"],
        postgresql_where=sa.text("status != 'ready'"),
    )
    op.create_index(
        "notes_tsv_idx", "notes", ["content_tsv"], postgresql_using="gin"
    )
    op.create_index(
        "notes_trgm_idx",
        "notes",
        ["processed_content"],
        postgresql_using="gin",
        postgresql_ops={"processed_content": "gin_trgm_ops"},
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "name", name="uq_tags_user_id"),
    )

    op.create_table(
        "note_tags",
        sa.Column("note_id", sa.Uuid(),
                  sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Uuid(),
                  sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("source", sa.String(8), nullable=False, server_default="ai"),
        sa.CheckConstraint("source IN ('ai','user')", name="ck_note_tags_source_enum"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("note_id", sa.Uuid(),
                  sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("qdrant_point_id", sa.Uuid(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.UniqueConstraint("note_id", "chunk_index", name="uq_chunks_note_id"),
    )

    op.create_table(
        "queries",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("cited_note_ids", postgresql.ARRAY(sa.Uuid()),
                  nullable=False, server_default=sa.text("'{}'::uuid[]")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("user_feedback", sa.SmallInteger(), nullable=True),
    )

    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("config_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("user_id", "kind", name="uq_integrations_user_id"),
        sa.CheckConstraint(
            "kind IN ('notion','obsidian','anki','calendar')",
            name="ck_integrations_kind_enum",
        ),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("idempotency_created_idx", "idempotency_keys", ["created_at"])


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("integrations")
    op.drop_table("queries")
    op.drop_table("chunks")
    op.drop_table("note_tags")
    op.drop_table("tags")
    op.drop_table("notes")
    op.drop_table("users")
