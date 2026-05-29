"""Bot-facing pub/sub events.

The channel names and payload shapes live here — in `mnemo_api` — so that
both the Core API (e.g. the n8n ``note-failed`` webhook) and the workers
publish on identical channels. ``mnemo_workers.redis_io`` re-exports these for
backwards compatibility with existing worker imports.
"""

from __future__ import annotations

import json
from uuid import UUID

from redis.asyncio import Redis


def note_ready_channel(user_id: UUID) -> str:
    return f"note.ready.{user_id}"


def digest_channel(user_id: UUID) -> str:
    return f"digest.daily.{user_id}"


async def publish_note_ready(
    redis: Redis, *, user_id: UUID, tg_user_id: int, note_id: UUID
) -> None:
    """Tell the bot a note reached a terminal state (ready *or* failed).

    The listener edits the user's placeholder message to the final note view.
    ``tg_user_id`` is included so the listener can mint a service JWT without a
    Redis hash-table lookup or an extra DB hit.
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


async def publish_digest(redis: Redis, *, user_id: UUID, tg_user_id: int, text: str) -> None:
    await redis.publish(
        digest_channel(user_id),
        json.dumps({"user_id": str(user_id), "tg_user_id": tg_user_id, "text": text}),
    )
