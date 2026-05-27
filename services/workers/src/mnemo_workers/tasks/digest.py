"""Cron-driven daily digest actor."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import dramatiq
from sqlalchemy import select

from mnemo_api.config import get_settings
from mnemo_api.db import session_factory
from mnemo_api.llm import make_llm
from mnemo_api.logging import get_logger
from mnemo_api.models import User
from mnemo_api.services.digest import daily_digest
from mnemo_workers.redis_io import get_redis
from mnemo_workers.runner import run

log = get_logger(__name__)


@dramatiq.actor(queue_name="periodic", max_retries=1, time_limit=300_000)
def run_daily_digest_for_all_users() -> None:
    run(_run_for_all)


async def _run_for_all() -> None:
    llm = make_llm(get_settings())
    redis = get_redis()
    try:
        async with session_factory()() as session:
            users = (
                await session.execute(
                    select(User).where(User.is_active.is_(True))
                )
            ).scalars().all()

        for user in users:
            try:
                async with session_factory()() as session:
                    text = await daily_digest(
                        session, llm, user_id=user.id, on_date=datetime.now(UTC)
                    )
                # Hand off to the bot via redis pubsub on a dedicated channel.
                await redis.publish(
                    f"digest.daily.{user.id}", text.encode("utf-8")
                )
                log.info("digest.daily.ok", user_id=str(user.id), len=len(text))
            except Exception:  # noqa: BLE001
                log.exception("digest.daily.failed", user_id=str(user.id))
            # Tiny sleep so we don't burst the LLM provider.
            await asyncio.sleep(0.1)
    finally:
        close = getattr(llm, "aclose", None)
        if callable(close):
            await close()
        await redis.aclose()
