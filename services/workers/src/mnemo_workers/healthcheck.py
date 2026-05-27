"""Healthcheck entrypoint: `python -m mnemo_workers.healthcheck`.

Returns exit 0 if Redis is reachable (the broker we depend on). The
container's healthcheck in `docker-compose.yml` calls this.
"""

from __future__ import annotations

import asyncio
import sys

from redis.asyncio import Redis

from mnemo_api.config import get_settings


async def _main() -> int:
    try:
        r: Redis = Redis.from_url(get_settings().redis_url)
        pong = await r.ping()
        await r.aclose()
        return 0 if pong else 1
    except Exception:  # noqa: BLE001
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
