"""Whitelist check.

Telegram updates from a user not in `MNEMO_ALLOWED_TG_IDS` are silently
dropped — we don't even acknowledge them. This is the only authorization
boundary in v1.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from mnemo_bot.config import get_settings
from mnemo_bot.logging import get_logger

log = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        allowed = get_settings().allowed_tg_ids_set
        user = getattr(event, "from_user", None)
        tg_id = user.id if user is not None else None

        if tg_id is None:
            return  # ignore events without a user (channel posts, etc.)

        # Fail closed: an empty whitelist denies everyone rather than allowing
        # everyone. (Production startup also refuses an empty whitelist; this
        # is the runtime backstop.)
        if not allowed:
            log.warning("auth.no_whitelist.deny_all", tg_user_id=tg_id)
            return
        if tg_id not in allowed:
            log.warning("auth.rejected", tg_user_id=tg_id)
            return

        data["tg_user_id"] = tg_id
        data["tg_username"] = user.username if user else None
        return await handler(event, data)
