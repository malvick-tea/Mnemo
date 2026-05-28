"""Qdrant client helpers for worker tasks."""

from __future__ import annotations

from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PointStruct

from mnemo_api.config import get_settings
from mnemo_api.models import Chunk, Note


def get_qdrant_client() -> AsyncQdrantClient:
    s = get_settings()
    return AsyncQdrantClient(
        url=s.qdrant_url,
        api_key=s.qdrant_api_key.get_secret_value() if s.qdrant_api_key else None,
    )


async def upsert_chunks(
    qdrant: AsyncQdrantClient,
    *,
    collection: str,
    note: Note,
    chunks: Sequence[Chunk],
    vectors: Sequence[list[float]],
    tags: Sequence[str] = (),
) -> None:
    """Upsert chunks into Qdrant.

    `tags` are stored in the payload so `Filter` queries can narrow by
    tag without a Postgres join. Callers should load the current tag
    set with the chunk batch — Qdrant payloads aren't auto-updated when
    note tags change later, so re-running this fn is the canonical way
    to bring a note's vectors back in sync.
    """
    tag_list = [str(t) for t in tags]
    points = [
        PointStruct(
            id=str(c.qdrant_point_id),
            vector=v,
            payload={
                "note_id": str(note.id),
                "chunk_id": str(c.id),
                "user_id": str(note.user_id),
                "source_type": note.source_type,
                "tags": tag_list,
                "created_at": int(note.created_at.timestamp()),
                "title": note.title,
            },
        )
        for c, v in zip(chunks, vectors, strict=True)
    ]
    await qdrant.upsert(collection_name=collection, points=points, wait=True)
