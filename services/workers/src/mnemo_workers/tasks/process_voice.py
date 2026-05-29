"""Voice capture pipeline.

Triggered by the API after a multipart upload lands in MinIO:
1. Download the audio blob.
2. Run faster-whisper transcription (CPU by default; controllable via env).
3. Persist transcript as `processed_content` + transcription metadata.
4. Hand off to `process_text_note` for summarize/tag/chunk/embed/publish.

We keep faster-whisper instantiated per call (cheap re-init once the model
is cached on disk) so the worker can free memory between voice notes.
"""

from __future__ import annotations

import io
import os
import tempfile
from uuid import UUID

import dramatiq
from mnemo_api.db import session_factory
from mnemo_api.logging import get_logger
from mnemo_api.models import Note, NoteStatus, User
from mnemo_api.services.queue import enqueue
from redis.asyncio import Redis
from sqlalchemy import select

from mnemo_workers.minio_io import download_blob
from mnemo_workers.redis_io import get_redis, publish_note_ready
from mnemo_workers.runner import run

log = get_logger(__name__)

_WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
_WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
_WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


@dramatiq.actor(queue_name="default", max_retries=3, time_limit=600_000)
def process_voice_note(note_id: str, blob_key: str) -> None:
    run(_process_voice_note, UUID(note_id), blob_key)


async def _process_voice_note(note_id: UUID, blob_key: str) -> None:
    redis = get_redis()
    try:
        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None:
                log.warning("voice.missing", note_id=str(note_id))
                return
            note.status = NoteStatus.processing.value
            await session.commit()

        try:
            audio_bytes = download_blob(blob_key)
        except Exception as exc:
            log.exception("voice.download.failed", note_id=str(note_id))
            await _fail(redis, note_id, f"download: {exc}")
            return

        try:
            transcript, language, duration = _transcribe(audio_bytes)
        except Exception as exc:
            log.exception("voice.transcribe.failed", note_id=str(note_id))
            await _fail(redis, note_id, f"transcribe: {exc}")
            return

        if not transcript.strip():
            await _fail(redis, note_id, "Empty transcription (silent or unintelligible audio)")
            return

        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None:
                return
            note.processed_content = transcript
            meta = dict(note.source_metadata or {})
            meta["transcription"] = {
                "model": _WHISPER_MODEL,
                "language": language,
                "duration_sec": duration,
            }
            note.source_metadata = meta
            # Leave at `processing`; downstream actor flips to `ready`.
            await session.commit()

        await enqueue(redis, "process_text_note", {"note_id": str(note_id)})
        log.info(
            "voice.transcribed",
            note_id=str(note_id),
            language=language,
            duration_sec=duration,
            chars=len(transcript),
        )
    finally:
        await redis.aclose()


def _transcribe(audio: bytes) -> tuple[str, str | None, float | None]:
    """Run faster-whisper on the bytes. Returns (text, language, seconds)."""
    from faster_whisper import WhisperModel  # heavy import, do it lazily

    model = WhisperModel(
        _WHISPER_MODEL,
        device=_WHISPER_DEVICE,
        compute_type=_WHISPER_COMPUTE,
    )

    # faster-whisper accepts paths, file-like, or numpy. BytesIO works on
    # most builds; fall back to a temp file for codec quirks.
    try:
        segments, info = model.transcribe(io.BytesIO(audio), beam_size=5)
    except Exception:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as tmp:
            tmp.write(audio)
            tmp_path = tmp.name
        try:
            segments, info = model.transcribe(tmp_path, beam_size=5)
        finally:
            os.unlink(tmp_path)

    text = " ".join(seg.text.strip() for seg in segments).strip()
    language = getattr(info, "language", None)
    duration = getattr(info, "duration", None)
    return text, language, duration


async def _fail(redis: Redis, note_id: UUID, message: str) -> None:
    """Mark the note failed *and* notify the bot so the placeholder updates."""
    user_id: UUID | None = None
    tg_user_id: int | None = None
    async with session_factory()() as session:
        note = (await session.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
        if note is None:
            return
        note.status = NoteStatus.failed.value
        note.error_message = message[:2_000]
        user_id = note.user_id
        user = await session.get(User, note.user_id)
        tg_user_id = user.tg_user_id if user is not None else None
        await session.commit()
    if user_id is not None and tg_user_id is not None:
        try:
            await publish_note_ready(redis, user_id=user_id, tg_user_id=tg_user_id, note_id=note_id)
        except Exception:
            log.exception("voice.fail_notify_failed", note_id=str(note_id))
