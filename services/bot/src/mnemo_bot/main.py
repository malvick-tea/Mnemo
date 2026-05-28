"""Bot entrypoint. Polling in dev, webhook in prod (configurable via env)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiohttp import web
from redis.asyncio import Redis

from mnemo_bot import handlers
from mnemo_bot.api_client import ApiClient
from mnemo_bot.config import get_settings
from mnemo_bot.logging import configure_logging, get_logger
from mnemo_bot.middlewares import (
    AuthMiddleware,
    CorrelationIdMiddleware,
    ErrorMiddleware,
    ThrottleMiddleware,
)
from mnemo_bot.note_ready_listener import listen_note_ready

log = get_logger(__name__)


@asynccontextmanager
async def _components() -> Any:
    s = get_settings()
    bot = Bot(
        token=s.tg_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    redis: Redis = Redis.from_url(s.redis_url, decode_responses=False)
    api = ApiClient()
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)

    # Middlewares (outer to inner)
    dp.update.middleware(CorrelationIdMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(ThrottleMiddleware(redis))
    dp.callback_query.middleware(ThrottleMiddleware(redis))
    dp.update.middleware(ErrorMiddleware())

    # Routers — registration order matters (URL-only must precede generic text).
    dp.include_router(handlers.start.router)
    dp.include_router(handlers.query.router)
    dp.include_router(handlers.digest.router)
    dp.include_router(handlers.anki.router)
    dp.include_router(handlers.list_views.router)
    dp.include_router(handlers.settings.router)
    dp.include_router(handlers.capture_url.router)
    dp.include_router(handlers.capture_voice.router)
    dp.include_router(handlers.capture_photo.router)
    dp.include_router(handlers.capture_document.router)
    dp.include_router(handlers.capture_forward.router)
    dp.include_router(handlers.capture_text.router)

    # Make shared instances available to handlers via context.
    dp["api"] = api
    dp["redis"] = redis

    try:
        yield bot, dp, redis, api
    finally:
        await api.aclose()
        await redis.aclose()
        await bot.session.close()


async def _run_polling() -> None:
    async with _components() as (bot, dp, redis, api):
        listener = asyncio.create_task(listen_note_ready(bot, redis, api))
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        finally:
            listener.cancel()
            try:
                await listener
            except asyncio.CancelledError:
                pass


async def _run_webhook() -> None:
    s = get_settings()
    async with _components() as (bot, dp, redis, api):
        listener = asyncio.create_task(listen_note_ready(bot, redis, api))

        app = web.Application()
        from aiogram.webhook.aiohttp_server import (
            SimpleRequestHandler,
            setup_application,
        )

        SimpleRequestHandler(dispatcher=dp, bot=bot).register(
            app, path=s.tg_webhook_path
        )
        setup_application(app, dp, bot=bot)

        public_url = f"https://{s.domain}{s.tg_webhook_path}"
        await bot.set_webhook(url=public_url, drop_pending_updates=True)
        log.info("bot.webhook.set", url=public_url)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=s.tg_webhook_port)  # noqa: S104
        await site.start()
        try:
            # Keep the process alive until cancelled.
            await asyncio.Event().wait()
        finally:
            listener.cancel()
            await runner.cleanup()


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level)
    log.info("bot.start", mode=s.tg_mode, env=s.env)
    if s.tg_mode == "webhook":
        asyncio.run(_run_webhook())
    else:
        asyncio.run(_run_polling())


if __name__ == "__main__":
    main()
