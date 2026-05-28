"""Catch-all error middleware.

Logs the traceback with the correlation ID and replies to the user with a
generic message that includes the correlation ID so they can quote it in a
bug report. We do NOT show the raw exception to the user.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from mnemo_bot.logging import correlation_id_ctx, get_logger

log = get_logger(__name__)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            cid = correlation_id_ctx.get() or "(no-id)"
            log.exception("handler.unhandled", event_type=type(event).__name__)
            msg = (
                "❌ Something went wrong. The Mnemo team has been logged.\n"
                f"Reference: `{cid[:12]}`"
            )
            if isinstance(event, Message):
                with _SafeSend():
                    await event.reply(msg)
            elif isinstance(event, CallbackQuery):
                with _SafeSend():
                    await event.answer(msg, show_alert=True)
            # Don't re-raise — we already logged.
            return None


class _SafeSend:
    """Suppress secondary errors while reporting the primary one."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *_exc: object) -> bool:
        return True
