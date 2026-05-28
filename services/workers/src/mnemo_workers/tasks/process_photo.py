"""Photo capture pipeline.

Triggered by the API after a multipart photo upload lands in MinIO:
1. Download the image blob.
2. Ask the vision LLM to extract/describe (verbatim OCR if text-heavy,
   semantic description otherwise).
3. Persist the description as `processed_content`.
4. Hand off to `process_text_note` for summarize/tag/chunk/embed/publish.

Per ADR-003 we keep this in a local actor (low-latency path). n8n workflow
003-photo-ocr is preserved as an alternative for milestone-3.
"""

from __future__ import annotations

from uuid import UUID

import dramatiq
from sqlalchemy import select

from mnemo_api.config import get_settings
from mnemo_api.db import session_factory
from mnemo_api.llm import make_vision_llm, render_prompt
from mnemo_api.logging import get_logger
from mnemo_api.models import Note, NoteStatus
from mnemo_api.services.queue import enqueue
from mnemo_workers.minio_io import download_blob
from mnemo_workers.redis_io import get_redis
from mnemo_workers.runner import run

log = get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=3, time_limit=120_000)
def process_photo_note(note_id: str, blob_key: str) -> None:
    run(_process_photo_note, UUID(note_id), blob_key)


async def _process_photo_note(note_id: UUID, blob_key: str) -> None:
    settings = get_settings()
    redis = get_redis()
    vision = make_vision_llm(settings)
    try:
        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None:
                log.warning("photo.missing", note_id=str(note_id))
                return
            note.status = NoteStatus.processing.value
            caption = (note.source_metadata or {}).get("caption")
            mime = (note.source_metadata or {}).get("mime") or "image/jpeg"
            await session.commit()

        try:
            image_bytes = download_blob(blob_key)
        except Exception as exc:  # noqa: BLE001
            log.exception("photo.download.failed", note_id=str(note_id))
            await _fail(note_id, f"download: {exc}")
            return

        prompt, fp = render_prompt("photo_describe_v1", caption=caption)
        try:
            completion = await vision.chat_vision(
                prompt=prompt,
                image_bytes=image_bytes,
                mime=mime,
                model=settings.model_vision,
                max_tokens=1_200,
                temperature=0.2,
                prompt_fingerprint=fp,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("photo.vision.failed", note_id=str(note_id))
            await _fail(note_id, f"vision: {exc}")
            return

        description = completion.text.strip()
        if not description:
            await _fail(note_id, "Vision returned empty description")
            return

        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None:
                return
            note.processed_content = description
            meta = dict(note.source_metadata or {})
            meta["vision"] = {
                "model": completion.model,
                "prompt_fingerprint": fp,
            }
            note.source_metadata = meta
            await session.commit()

        await enqueue(redis, "process_text_note", {"note_id": str(note_id)})
        log.info(
            "photo.described",
            note_id=str(note_id),
            chars=len(description),
            model=completion.model,
        )
    finally:
        await redis.aclose()
        close = getattr(vision, "aclose", None)
        if callable(close):
            await close()


async def _fail(note_id: UUID, message: str) -> None:
    async with session_factory()() as session:
        note = (
            await session.execute(select(Note).where(Note.id == note_id))
        ).scalar_one_or_none()
        if note is None:
            return
        note.status = NoteStatus.failed.value
        note.error_message = message[:2_000]
        await session.commit()
