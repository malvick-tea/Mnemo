"""Periodic cleanup chores.

`run_idempotency_cleanup` purges `idempotency_keys` rows older than 24h.
The webhook timestamp window is 5 minutes, so anything older than a day
will never match a legitimate replay — and the table grows monotonically
without this sweep.
"""

from __future__ import annotations

import dramatiq
from mnemo_api.db import session_factory
from mnemo_api.logging import get_logger
from sqlalchemy import text

from mnemo_workers.runner import run

log = get_logger(__name__)


@dramatiq.actor(queue_name="periodic", max_retries=1, time_limit=120_000)
def run_idempotency_cleanup() -> None:
    run(_purge_old_idempotency_keys)


async def _purge_old_idempotency_keys() -> None:
    async with session_factory()() as session:
        result = await session.execute(
            text("DELETE FROM idempotency_keys " "WHERE created_at < now() - interval '24 hours'")
        )
        await session.commit()
        log.info(
            "cleanup.idempotency.purged",
            rows=getattr(result, "rowcount", -1),
        )
