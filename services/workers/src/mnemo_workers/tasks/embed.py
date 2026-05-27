"""Standalone embed actor.

`process_text_note` already embeds inline; this actor exists for re-embedding
after content is edited (PATCH /v1/notes/{id}) and for n8n callbacks where
the workflow only provides processed_content.
"""

from __future__ import annotations

from uuid import UUID

import dramatiq
from sqlalchemy import select

from mnemo_api.config import get_settings
from mnemo_api.db import session_factory
from mnemo_api.llm import make_embedder
from mnemo_api.logging import get_logger
from mnemo_api.models import Chunk, Note
from mnemo_api.services.chunking import split_into_chunks
from mnemo_workers.qdrant_io import get_qdrant_client, upsert_chunks
from mnemo_workers.runner import run

log = get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=3, time_limit=60_000)
def embed_note(note_id: str) -> None:
    run(_embed_note, UUID(note_id))


async def _embed_note(note_id: UUID) -> None:
    settings = get_settings()
    embedder = make_embedder(settings)
    qdrant = get_qdrant_client()

    try:
        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None or not note.processed_content:
                log.warning("embed.skip", note_id=str(note_id))
                return

            existing_rows = (
                await session.execute(
                    select(Chunk).where(Chunk.note_id == note.id).order_by(Chunk.chunk_index)
                )
            ).scalars().all()
            for c in existing_rows:
                await session.delete(c)
            await session.flush()

            chunks_in = split_into_chunks(note.processed_content)
            if not chunks_in:
                return

            vectors = await embedder.embed([c.content for c in chunks_in])
            new_rows: list[Chunk] = [
                Chunk(
                    note_id=note.id,
                    chunk_index=c.index,
                    content=c.content,
                    token_count=c.token_count,
                )
                for c in chunks_in
            ]
            session.add_all(new_rows)
            await session.flush()
            await upsert_chunks(
                qdrant,
                collection=settings.qdrant_collection,
                note=note,
                chunks=new_rows,
                vectors=vectors,
            )
            await session.commit()
            log.info("embed.ok", note_id=str(note_id), chunks=len(new_rows))
    finally:
        for c in (embedder, qdrant):
            close = getattr(c, "aclose", None)
            if callable(close):
                await close()
