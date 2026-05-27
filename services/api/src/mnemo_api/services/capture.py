"""Capture flow: creating note rows and enqueueing follow-up work."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.logging import get_logger
from mnemo_api.models import Note, NoteStatus, SourceType, User

log = get_logger(__name__)

# Redis stream / list used by Dramatiq-broker-equivalent producers
_TASK_QUEUE = "mnemo:tasks"


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
    await _enqueue(redis, "process_text_note", {"note_id": str(note.id)})
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
    await _trigger_n8n(redis, "001-url-ingest", note_id=note.id, url=url)
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
    await _trigger_n8n(redis, "002-voice-transcribe", note_id=note.id, blob_key=blob_key)
    log.info("capture.voice.created", note_id=str(note.id), blob_key=blob_key)
    return note


# ─── helpers ────────────────────────────────────────────────────────────────


def _derive_title(content: str, max_chars: int = 80) -> str:
    first_line = next((ln.strip() for ln in content.splitlines() if ln.strip()), "")
    return first_line[:max_chars] or "(untitled)"


async def _enqueue(redis: Redis, task: str, payload: dict[str, Any]) -> None:
    """Hand off to the Dramatiq worker. We push a lightweight marker so the
    API can also work without Dramatiq running (tests with eager workers)."""
    await redis.lpush(
        _TASK_QUEUE,
        json.dumps(
            {
                "task": task,
                "payload": payload,
                "enqueued_at": datetime.now(UTC).isoformat(),
            }
        ),
    )


async def _trigger_n8n(redis: Redis, workflow: str, **payload: Any) -> None:
    """Marker enqueue for n8n trigger. The actual HTTP call happens in a
    worker so we don't block the capture endpoint on n8n latency."""
    payload_safe = {k: (str(v) if isinstance(v, UUID) else v) for k, v in payload.items()}
    await redis.lpush(
        _TASK_QUEUE,
        json.dumps(
            {
                "task": "trigger_n8n_workflow",
                "payload": {"workflow": workflow, **payload_safe},
                "enqueued_at": datetime.now(UTC).isoformat(),
            }
        ),
    )
