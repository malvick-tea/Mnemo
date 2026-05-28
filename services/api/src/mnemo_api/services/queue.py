"""Shared Redis enqueue helper.

The Core API drops lightweight task markers on a Redis list; the workers'
dispatcher pops them and dispatches to Dramatiq actors. Keeping enqueue in
one place (instead of inlined in capture.py and webhooks_n8n.py) means a
single point to evolve the wire format.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

TASK_QUEUE = "mnemo:tasks"


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


async def enqueue(redis: Redis, task: str, payload: dict[str, Any]) -> None:
    """Hand off to the workers' dispatcher."""
    await redis.lpush(
        TASK_QUEUE,
        json.dumps(
            {
                "task": task,
                "payload": _json_safe(payload),
                "enqueued_at": datetime.now(UTC).isoformat(),
            }
        ),
    )


async def trigger_n8n(redis: Redis, workflow: str, **payload: Any) -> None:
    """Convenience wrapper for the n8n trigger actor."""
    await enqueue(
        redis, "trigger_n8n_workflow", {"workflow": workflow, **payload}
    )
