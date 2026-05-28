"""Capture flow: creating note rows and enqueueing follow-up work."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.logging import get_logger
from mnemo_api.models import Note, NoteStatus, SourceType, User
from mnemo_api.services.queue import enqueue

log = get_logger(__name__)


async def create_text_note(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    content: str,
    captured_at: datetime,
    source_metadata: dict[str, Any] | None = None,
) -> Note:
    note = Note(
        user_id=user.id,
        source_type=SourceType.text.value,
        raw_content=content,
        processed_content=content,
        captured_at=captured_at,
        source_metadata=source_metadata or {},
        status=NoteStatus.pending.value,
        title=_derive_title(content),
    )
    session.add(note)
    await session.flush()
    await enqueue(redis, "process_text_note", {"note_id": str(note.id)})
    log.info("capture.text.created", note_id=str(note.id), len=len(content))
    return note


async def create_url_note(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    url: str,
    captured_at: datetime,
    source_metadata: dict[str, Any] | None = None,
) -> Note:
    note = Note(
        user_id=user.id,
        source_type=SourceType.url.value,
        source_url=url,
        captured_at=captured_at,
        source_metadata=source_metadata or {},
        status=NoteStatus.pending.value,
    )
    session.add(note)
    await session.flush()
    await enqueue(
        redis,
        "trigger_n8n_workflow",
        {"workflow": "001-url-ingest", "note_id": str(note.id), "url": url},
    )
    log.info("capture.url.created", note_id=str(note.id), url=url)
    return note


async def create_voice_note(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    blob_key: str,
    captured_at: datetime,
    source_metadata: dict[str, Any] | None = None,
) -> Note:
    note = Note(
        user_id=user.id,
        source_type=SourceType.voice.value,
        blob_keys=[blob_key],
        captured_at=captured_at,
        source_metadata=source_metadata or {},
        status=NoteStatus.pending.value,
    )
    session.add(note)
    await session.flush()
    # Per ADR-003, voice transcription stays in a local Dramatiq actor for
    # v1 (low-latency path; n8n 002 stub kept as alternative for milestone-3).
    await enqueue(
        redis,
        "process_voice_note",
        {"note_id": str(note.id), "blob_key": blob_key},
    )
    log.info("capture.voice.created", note_id=str(note.id), blob_key=blob_key)
    return note


async def create_photo_note(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    blob_key: str,
    caption: str | None,
    captured_at: datetime,
    source_metadata: dict[str, Any] | None = None,
) -> Note:
    meta = dict(source_metadata or {})
    if caption:
        meta["caption"] = caption
    note = Note(
        user_id=user.id,
        source_type=SourceType.photo.value,
        blob_keys=[blob_key],
        raw_content=caption,
        captured_at=captured_at,
        source_metadata=meta,
        status=NoteStatus.pending.value,
        title=_derive_title(caption) if caption else None,
    )
    session.add(note)
    await session.flush()
    await enqueue(
        redis,
        "process_photo_note",
        {"note_id": str(note.id), "blob_key": blob_key},
    )
    log.info("capture.photo.created", note_id=str(note.id), blob_key=blob_key)
    return note


async def create_document_note(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    blob_key: str,
    filename: str,
    mime: str | None,
    captured_at: datetime,
    source_metadata: dict[str, Any] | None = None,
) -> Note:
    meta = dict(source_metadata or {})
    meta.setdefault("filename", filename)
    if mime:
        meta.setdefault("mime", mime)
    note = Note(
        user_id=user.id,
        source_type=SourceType.document.value,
        blob_keys=[blob_key],
        captured_at=captured_at,
        source_metadata=meta,
        status=NoteStatus.pending.value,
        title=filename or None,
    )
    session.add(note)
    await session.flush()
    await enqueue(
        redis,
        "process_document_note",
        {"note_id": str(note.id), "blob_key": blob_key, "filename": filename},
    )
    log.info(
        "capture.document.created",
        note_id=str(note.id), blob_key=blob_key, filename=filename,
    )
    return note


async def create_forward_note(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    content: str,
    forward_metadata: dict[str, Any],
    captured_at: datetime,
    source_metadata: dict[str, Any] | None = None,
) -> Note:
    meta = dict(source_metadata or {})
    meta["forward"] = forward_metadata
    note = Note(
        user_id=user.id,
        source_type=SourceType.forward.value,
        raw_content=content,
        processed_content=content,
        captured_at=captured_at,
        source_metadata=meta,
        status=NoteStatus.pending.value,
        title=_derive_forward_title(forward_metadata, content),
    )
    session.add(note)
    await session.flush()
    # Forwards are effectively text + provenance — reuse the text pipeline.
    await enqueue(redis, "process_text_note", {"note_id": str(note.id)})
    log.info(
        "capture.forward.created",
        note_id=str(note.id), len=len(content),
        origin=forward_metadata.get("origin_type"),
    )
    return note


# ─── helpers ────────────────────────────────────────────────────────────────


def _derive_title(content: str | None, max_chars: int = 80) -> str:
    if not content:
        return "(untitled)"
    first_line = next((ln.strip() for ln in content.splitlines() if ln.strip()), "")
    return first_line[:max_chars] or "(untitled)"


def _derive_forward_title(forward_metadata: dict[str, Any], content: str) -> str:
    src = (
        forward_metadata.get("from_chat_title")
        or forward_metadata.get("from_user_name")
        or forward_metadata.get("origin_type")
        or "forward"
    )
    return f"↪ {src}: {_derive_title(content, max_chars=60)}"
