"""Cron-driven daily digest actor.

Publishes a `digest.daily.<user_id>` event with the rendered digest text
so the bot listener can deliver it via Telegram. We embed `tg_user_id`
in the payload so the bot doesn't need a separate lookup.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import dramatiq
from mnemo_api.config import get_settings
from mnemo_api.db import session_factory
from mnemo_api.exceptions import QuotaExceeded
from mnemo_api.llm import make_llm
from mnemo_api.logging import get_logger
from mnemo_api.models import User
from mnemo_api.services.digest import daily_digest
from mnemo_api.services.usage import assert_budget, current_user_id
from sqlalchemy import select

from mnemo_workers.redis_io import get_redis, publish_digest
from mnemo_workers.runner import run

log = get_logger(__name__)


@dramatiq.actor(queue_name="periodic", max_retries=1, time_limit=300_000)
def run_daily_digest_for_all_users() -> None:
    run(_run_for_all)


async def _run_for_all() -> None:
    settings = get_settings()
    redis = get_redis()
    llm = make_llm(settings, redis=redis)
    try:
        async with session_factory()() as session:
            users = (
                (await session.execute(select(User).where(User.is_active.is_(True))))
                .scalars()
                .all()
            )
            user_rows = [(u.id, u.tg_user_id) for u in users]

        for user_id, tg_user_id in user_rows:
            try:
                current_user_id.set(user_id)
                await assert_budget(redis, user_id, settings.user_daily_token_cap)
                async with session_factory()() as session:
                    text = await daily_digest(
                        session, llm, user_id=user_id, on_date=datetime.now(UTC)
                    )
                await publish_digest(redis, user_id=user_id, tg_user_id=tg_user_id, text=text)
                log.info("digest.daily.ok", user_id=str(user_id), len=len(text))
            except QuotaExceeded:
                log.info("digest.daily.skipped_over_budget", user_id=str(user_id))
            except Exception:
                log.exception("digest.daily.failed", user_id=str(user_id))
            await asyncio.sleep(0.1)
    finally:
        close = getattr(llm, "aclose", None)
        if callable(close):
            await close()
        await redis.aclose()
