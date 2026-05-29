"""End-to-end pipeline for a freshly-captured text note.

Triggered by the API via Redis enqueue. Pipeline:
    summarize → tag → chunk → embed → upsert Qdrant → publish note.ready

We keep everything in this single actor so a single retry policy applies
to the whole pipeline.

Completion notification is *terminal-only*: the bot's "📝 Saving…" placeholder
is edited exactly once, when the note reaches `ready` or `failed`. A retriable
failure re-raises (so Dramatiq retries) **without** publishing — otherwise the
bot would delete the placeholder mapping on the first failed attempt and a
later successful retry could never update the user.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import dramatiq
from mnemo_api.config import get_settings
from mnemo_api.db import session_factory
from mnemo_api.exceptions import QuotaExceeded
from mnemo_api.llm import make_embedder, make_llm
from mnemo_api.logging import get_logger
from mnemo_api.models import Chunk, Note, NoteStatus, User
from mnemo_api.services.chunking import split_into_chunks
from mnemo_api.services.summarize import summarize
from mnemo_api.services.tagging import suggest_and_apply_tags
from mnemo_api.services.usage import assert_budget, current_user_id
from sqlalchemy import select

from mnemo_workers.qdrant_io import get_qdrant_client, upsert_chunks
from mnemo_workers.redis_io import get_redis, publish_note_ready
from mnemo_workers.runner import is_last_attempt, run

log = get_logger(__name__)

_MAX_RETRIES = 3


@dramatiq.actor(queue_name="default", max_retries=_MAX_RETRIES, time_limit=120_000)
def process_text_note(note_id: str) -> None:
    run(_process_text_note, UUID(note_id))


async def _process_text_note(note_id: UUID) -> None:
    settings = get_settings()
    llm = None
    embedder = None
    qdrant = None
    redis = get_redis()

    chunk_count = 0
    tg_user_id: int | None = None
    user_id: UUID | None = None
    terminal = False  # only notify the bot on a terminal (ready/failed) outcome

    try:
        llm = make_llm(settings, redis=redis)
        embedder = make_embedder(settings)
        qdrant = get_qdrant_client()

        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None:
                log.warning("process_text.missing", note_id=str(note_id))
                return

            user_id = note.user_id
            user = await session.get(User, user_id)
            if user is not None:
                tg_user_id = user.tg_user_id
            current_user_id.set(user_id)

            note.status = NoteStatus.processing.value
            await session.commit()

            content = note.processed_content or note.raw_content or ""
            if not content.strip():
                note.status = NoteStatus.failed.value
                note.error_message = "Empty content; nothing to process."
                await session.commit()
                terminal = True
                return

            # Cost guardrail: stop before doing LLM-heavy work if the user is
            # already at their daily token cap.
            try:
                await assert_budget(redis, user_id, settings.user_daily_token_cap)
            except QuotaExceeded as exc:
                note.status = NoteStatus.failed.value
                note.error_message = str(exc)[:1_000]
                await session.commit()
                terminal = True
                log.warning("process_text.over_budget", note_id=str(note_id))
                return

            if note.summary is None:
                try:
                    note.summary = await summarize(
                        llm,
                        content=content,
                        source_type=note.source_type,
                        title_hint=note.title,
                    )
                except Exception as exc:
                    log.exception("process_text.summarize.failed", note_id=str(note_id))
                    note.error_message = f"summary: {exc}"[:1_000]

            applied_tags: list[str] = []
            try:
                applied_tags = await suggest_and_apply_tags(
                    session,
                    llm,
                    note_id=note.id,
                    user_id=note.user_id,
                    content=content,
                )
            except Exception:
                log.exception("process_text.tagging.failed", note_id=str(note_id))

            chunks_in = split_into_chunks(content)
            chunk_count = len(chunks_in)
            if chunks_in:
                vectors = await embedder.embed([c.content for c in chunks_in])
                chunk_rows: list[Chunk] = []
                for c, _vec in zip(chunks_in, vectors, strict=True):
                    chunk_rows.append(
                        Chunk(
                            note_id=note.id,
                            chunk_index=c.index,
                            content=c.content,
                            token_count=c.token_count,
                        )
                    )
                session.add_all(chunk_rows)
                await session.flush()

                await upsert_chunks(
                    qdrant,
                    collection=settings.qdrant_collection,
                    note=note,
                    chunks=chunk_rows,
                    vectors=vectors,
                    tags=applied_tags,
                )

            note.status = NoteStatus.ready.value
            note.processed_at = datetime.now(UTC)
            await session.commit()
            terminal = True
        log.info("process_text.ok", note_id=str(note_id), chunks=chunk_count)
    except Exception:
        # Retriable failure (embed/upsert/db). Re-raise so Dramatiq retries;
        # do NOT notify — the note stays `processing`. Only once retries are
        # exhausted do we fail terminally and tell the user.
        if not is_last_attempt(_MAX_RETRIES):
            raise
        log.exception("process_text.exhausted", note_id=str(note_id))
        await _mark_failed(note_id, "Processing failed after repeated attempts.")
        terminal = True
        raise
    finally:
        # Notify exactly once, on a terminal outcome, so the bot edits the
        # placeholder to the final note view (or a "failed" message).
        if terminal and user_id is not None and tg_user_id is not None:
            try:
                await publish_note_ready(
                    redis,
                    user_id=user_id,
                    tg_user_id=tg_user_id,
                    note_id=note_id,
                )
            except Exception:
                log.exception("process_text.publish_failed", note_id=str(note_id))
        for component in (llm, embedder, qdrant):
            close = getattr(component, "aclose", None)
            if callable(close):
                await close()
        await redis.aclose()


async def _mark_failed(note_id: UUID, message: str) -> None:
    async with session_factory()() as session:
        note = (await session.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
        if note is None:
            return
        note.status = NoteStatus.failed.value
        note.error_message = message[:2_000]
        await session.commit()
