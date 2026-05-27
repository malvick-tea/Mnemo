"""Generate / propagate a correlation ID per Telegram update."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from mnemo_bot.logging import correlation_id_ctx


class CorrelationIdMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        cid = uuid.uuid4().hex
        token = correlation_id_ctx.set(cid)
        try:
            return await handler(event, data)
        finally:
            correlation_id_ctx.reset(token)
