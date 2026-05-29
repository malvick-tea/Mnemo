"""Per-user daily token ledger — the cost guardrail.

A Redis counter keyed by user + UTC day accumulates LLM token usage.
``MNEMO_USER_DAILY_TOKEN_CAP`` is enforced as a hard stop before LLM-heavy
work begins (capture, query, digest, Anki, vision).

Usage is attributed via the ``current_user_id`` context variable so the
metering LLM wrapper can record token spend without threading the user id
through every service signature. Recording is best-effort: a Redis hiccup
must never break a user's request, and providers that don't report token
counts (e.g. some Ollama models) simply contribute zero.
"""

from __future__ import annotations

import contextvars
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from redis.asyncio import Redis

from mnemo_api.exceptions import QuotaExceeded
from mnemo_api.llm.base import CompletionResult, LLMClient, Message
from mnemo_api.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

log = get_logger(__name__)

# Set at request/task entry so the metering wrapper knows whom to bill.
current_user_id: contextvars.ContextVar[UUID | None] = contextvars.ContextVar(
    "mnemo_current_user_id", default=None
)

# Keep the daily counter for two days so the key always outlives its UTC window.
_TTL_SECONDS = 60 * 60 * 48


def _key(user_id: UUID, *, now: datetime | None = None) -> str:
    day = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"mnemo:usage:tokens:{user_id}:{day}"


async def tokens_used_today(redis: Redis, user_id: UUID) -> int:
    raw = await redis.get(_key(user_id))
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def record_usage(redis: Redis, user_id: UUID, tokens: int) -> None:
    if tokens <= 0:
        return
    key = _key(user_id)
    async with redis.pipeline(transaction=False) as pipe:
        pipe.incrby(key, tokens)
        pipe.expire(key, _TTL_SECONDS)
        await pipe.execute()


async def assert_budget(redis: Redis, user_id: UUID, cap: int) -> None:
    """Raise ``QuotaExceeded`` (HTTP 429) if the user is at/over their cap.

    A non-positive cap disables the guardrail.
    """
    if cap <= 0:
        return
    used = await tokens_used_today(redis, user_id)
    if used >= cap:
        raise QuotaExceeded(
            f"Daily token budget exhausted ({used:,}/{cap:,}). Resets at 00:00 UTC."
        )


class MeteringLLM:
    """Transparent ``LLMClient`` proxy that records token usage.

    Wraps another client; after each completion it bills ``total_tokens`` to
    the user named by ``current_user_id``. Structurally satisfies the
    ``LLMClient`` protocol so it is a drop-in for the wrapped client.
    """

    def __init__(self, inner: LLMClient, redis: Redis) -> None:
        self._inner = inner
        self._redis = redis

    async def chat(
        self,
        messages: Sequence[Message] | list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        response_format: Literal["text", "json"] = "text",
        prompt_fingerprint: str | None = None,
    ) -> CompletionResult:
        result = await self._inner.chat(
            list(messages),
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
            prompt_fingerprint=prompt_fingerprint,
        )
        await self._record(result.total_tokens)
        return result

    async def _record(self, tokens: int) -> None:
        user_id = current_user_id.get()
        if user_id is None or tokens <= 0:
            return
        try:
            await record_usage(self._redis, user_id, tokens)
        except Exception:
            log.warning("usage.record_failed", exc_info=True)

    async def aclose(self) -> None:
        close = getattr(self._inner, "aclose", None)
        if callable(close):
            await close()
