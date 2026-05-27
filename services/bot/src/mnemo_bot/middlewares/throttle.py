"""Redis-backed token bucket throttle.

Default: `MNEMO_THROTTLE_PER_MIN` requests per minute per Telegram user.
When the bucket is empty we send a polite "🚧 slow down" reply and drop
the update.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from redis.asyncio import Redis

from mnemo_bot.config import get_settings


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user_id = data.get("tg_user_id")
        if tg_user_id is None:
            return await handler(event, data)

        rate = get_settings().throttle_per_min
        now_min = int(time.time() // 60)
        key = f"mnemo:rl:{tg_user_id}:{now_min}"

        # INCR + EXPIRE in a single round-trip pipeline.
        pipe = self._redis.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, 90)
        count, _ = await pipe.execute()

        if count > rate and isinstance(event, Message):
            await event.reply("🚧 Slow down a moment — too many requests this minute.")
            return None
        return await handler(event, data)
