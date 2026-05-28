"""End-to-end integration: capture text → embed → query → citation.

This is the canonical test for the Phase-1 vertical slice. It requires:
- Postgres (alembic migrated)
- Qdrant
- Redis
- A real embedder; we monkeypatch a deterministic local embedder so the
  test doesn't depend on a network call.

Run via:
    make test-int
"""

from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


def _deterministic_vector(text: str, dim: int) -> list[float]:
    """Hash-based pseudo-embedding so identical text → identical vector."""
    h = hashlib.sha512(text.encode("utf-8")).digest()
    seed = int.from_bytes(h[:8], "big")
    rng_state = seed
    out: list[float] = []
    for _ in range(dim):
        rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((rng_state / 0x7FFFFFFF) * 2 - 1)
    # L2-normalize so cosine distances behave like a real embedder.
    norm = sum(x * x for x in out) ** 0.5
    return [x / norm for x in out]


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_HOST"),
    reason="Integration tests require a running Postgres (see services/api/conftest.py).",
)
@pytest.mark.asyncio
async def test_capture_query_roundtrip() -> None:
    from qdrant_client import AsyncQdrantClient

    from mnemo_api.config import get_settings
    from mnemo_api.db import session_factory
    from mnemo_api.models import Chunk, Note, NoteStatus, SourceType, User
    from mnemo_api.qdrant_setup import ensure_collection
    from mnemo_api.services.search import hybrid_search

    settings = get_settings()
    qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    await ensure_collection(qdrant, settings)

    class FakeEmbedder:
        dim = settings.embed_dim

        async def embed(self, texts: list[str]) -> list[list[float]]:
            return [_deterministic_vector(t, self.dim) for t in texts]

        async def embed_one(self, text: str) -> list[float]:
            return _deterministic_vector(text, self.dim)

    embedder = FakeEmbedder()

    # 1. Seed: user + note + chunk + qdrant point
    async with session_factory()() as session:
        user = User(tg_user_id=999_001)
        session.add(user)
        await session.flush()

        note = Note(
            user_id=user.id,
            source_type=SourceType.text.value,
            raw_content="Postgres has had logical replication since version 10.",
            processed_content="Postgres has had logical replication since version 10.",
            summary="Notes on Postgres logical replication.",
            title="Postgres logrep",
            captured_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            status=NoteStatus.ready.value,
        )
        session.add(note)
        await session.flush()

        point_id = uuid4()
        chunk = Chunk(
            note_id=note.id,
            chunk_index=0,
            content=note.processed_content,
            qdrant_point_id=point_id,
        )
        session.add(chunk)
        await session.commit()

        from qdrant_client.http.models import PointStruct

        await qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=str(point_id),
                    vector=_deterministic_vector(note.processed_content, settings.embed_dim),
                    payload={
                        "note_id": str(note.id),
                        "chunk_id": str(chunk.id),
                        "user_id": str(user.id),
                        "source_type": "text",
                        "tags": [],
                        "created_at": int(note.created_at.timestamp()),
                        "title": note.title,
                    },
                )
            ],
            wait=True,
        )

    # 2. Query: hybrid search must return our note among the hits.
    async with session_factory()() as session:
        hits = await hybrid_search(
            session=session,
            qdrant=qdrant,
            embedder=embedder,
            user_id=user.id,
            query="logical replication in postgres",
        )
    assert hits, "expected at least one hit"
    assert hits[0].note_id == note.id

    await qdrant.close()
