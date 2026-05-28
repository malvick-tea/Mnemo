"""Healthcheck entrypoint: `python -m mnemo_bot.healthcheck`."""

from __future__ import annotations

import asyncio
import sys

from redis.asyncio import Redis

from mnemo_bot.config import get_settings


async def _main() -> int:
    try:
        r: Redis = Redis.from_url(get_settings().redis_url)
        pong = await r.ping()
        await r.aclose()
        return 0 if pong else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
