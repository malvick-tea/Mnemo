"""Redis helpers: pub/sub channel for note-ready events."""

from __future__ import annotations

import json
from uuid import UUID

from redis.asyncio import Redis

from mnemo_api.config import get_settings


def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=False)


def note_ready_channel(user_id: UUID) -> str:
    return f"note.ready.{user_id}"


async def publish_note_ready(redis: Redis, *, user_id: UUID, note_id: UUID) -> None:
    await redis.publish(
        note_ready_channel(user_id),
        json.dumps({"note_id": str(note_id), "user_id": str(user_id)}),
    )
