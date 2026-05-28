"""Standalone tag actor."""

from __future__ import annotations

from uuid import UUID

import dramatiq
from mnemo_api.config import get_settings
from mnemo_api.db import session_factory
from mnemo_api.llm import make_llm
from mnemo_api.logging import get_logger
from mnemo_api.models import Note
from mnemo_api.services.tagging import suggest_and_apply_tags

from mnemo_workers.runner import run

log = get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=3, time_limit=60_000)
def tag_note(note_id: str) -> None:
    run(_tag_note, UUID(note_id))


async def _tag_note(note_id: UUID) -> None:
    llm = make_llm(get_settings())
    try:
        async with session_factory()() as session:
            note = await session.get(Note, note_id)
            if note is None or not note.processed_content:
                return
            applied = await suggest_and_apply_tags(
                session,
                llm,
                note_id=note.id,
                user_id=note.user_id,
                content=note.processed_content,
            )
            await session.commit()
            log.info("tag.ok", note_id=str(note_id), tags=applied)
    finally:
        close = getattr(llm, "aclose", None)
        if callable(close):
            await close()
