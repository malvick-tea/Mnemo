"""Redis helpers for workers.

The pub/sub channel contract is defined once in ``mnemo_api.services.events``
and re-exported here so both the API and the workers stay in lock-step. This
module only adds the worker-side connection factory.
"""

from __future__ import annotations

from mnemo_api.config import get_settings
from mnemo_api.services.events import (
    digest_channel,
    note_ready_channel,
    publish_digest,
    publish_note_ready,
)
from redis.asyncio import Redis

__all__ = [
    "digest_channel",
    "get_redis",
    "note_ready_channel",
    "publish_digest",
    "publish_note_ready",
]


def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=False)
