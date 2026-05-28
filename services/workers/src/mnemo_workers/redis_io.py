"""Redis helpers: pub/sub channels for bot-facing events."""

from __future__ import annotations

import json
from uuid import UUID

from mnemo_api.config import get_settings
from redis.asyncio import Redis


def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=False)


def note_ready_channel(user_id: UUID) -> str:
    return f"note.ready.{user_id}"


async def publish_note_ready(
    redis: Redis, *, user_id: UUID, tg_user_id: int, note_id: UUID
) -> None:
    """Tell the bot a note is ready to surface.

    `tg_user_id` is included so the listener can mint a service JWT
    without a Redis hash-table lookup or an extra DB hit.
    """
    await redis.publish(
        note_ready_channel(user_id),
        json.dumps(
            {
                "note_id": str(note_id),
                "user_id": str(user_id),
                "tg_user_id": tg_user_id,
            }
        ),
    )


def digest_channel(user_id: UUID) -> str:
    return f"digest.daily.{user_id}"


async def publish_digest(redis: Redis, *, user_id: UUID, tg_user_id: int, text: str) -> None:
    await redis.publish(
        digest_channel(user_id),
        json.dumps({"user_id": str(user_id), "tg_user_id": tg_user_id, "text": text}),
    )
