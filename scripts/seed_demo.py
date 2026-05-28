#!/usr/bin/env python3
"""Seed a demo dataset for README screenshots.

Intentionally fake content — uses obvious placeholder usernames so the
screenshots are clearly not real user data. Run inside the API container:
    make seed-demo
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mnemo_api.config import get_settings
from mnemo_api.models import Note, NoteStatus, NoteTag, SourceType, Tag, User

_FIXTURES = [
    (
        "pgvector HNSW paper",
        "Notes on the new HNSW index for pgvector — m=16 was a sweet spot for "
        "our 4M-row dataset, ef_construct ~200, recall@10 around 0.96.",
        "Bookmarking the HNSW paper Postgres uses — promising for ANN inside SQL.",
        ["postgres", "ml", "papers"],
    ),
    (
        "kitchen reno checklist",
        "Cabinets: Ikea Sektion. Counter: butcher block oak. Sink: Kraus 33in.",
        "Kitchen renovation shortlist before talking to the contractor.",
        ["home", "todo"],
    ),
    (
        "Why aiogram 3?",
        "aiogram 3.x has cleaner FSM, dependency injection via middlewares, "
        "and matches the FastAPI mental model. Migration from 2.x took ~half a day.",
        "Reasoning notes for picking aiogram 3 in Mnemo.",
        ["python", "bots", "mnemo"],
    ),
    (
        "RRF over weighted sum",
        "Reciprocal Rank Fusion needs no per-corpus tuning — handy when you "
        "blend Qdrant cosine with `ts_rank_cd`. k=60 is the typical default.",
        "Why ADR-002 picked RRF for Mnemo's hybrid search.",
        ["rag", "mnemo"],
    ),
]


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.postgres_dsn)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    tg_id = int(os.environ.get("DEMO_TG_USER_ID", "100000001"))
    async with session_maker() as session:
        user = User(tg_user_id=tg_id, tg_username="mnemo_demo")
        session.add(user)
        await session.flush()

        # Reuse-or-create tags per name so we link, not duplicate.
        tag_cache: dict[str, Tag] = {}

        cap = datetime.now(UTC) - timedelta(days=2)
        for title, content, summary, tag_names in _FIXTURES:
            note = Note(
                user_id=user.id,
                source_type=SourceType.text.value,
                raw_content=content,
                processed_content=content,
                summary=summary,
                title=title,
                captured_at=cap,
                status=NoteStatus.ready.value,
            )
            session.add(note)
            await session.flush()
            cap += timedelta(hours=4)
            for name in tag_names:
                tag = tag_cache.get(name)
                if tag is None:
                    tag = Tag(user_id=user.id, name=name)
                    session.add(tag)
                    await session.flush()
                    tag_cache[name] = tag
                session.add(
                    NoteTag(
                        note_id=note.id, tag_id=tag.id,
                        source="ai", confidence=1.0,
                    )
                )
        await session.commit()
    await engine.dispose()
    print(f"seeded {len(_FIXTURES)} notes for tg_user_id={tg_id}")


if __name__ == "__main__":
    asyncio.run(main())
