"""Async glue for Dramatiq actors.

Dramatiq actors are synchronous. Our task bodies are async (they hit the DB
via asyncpg and Qdrant via the async client), so we run them on a single
event loop per worker process via `asyncio.run`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run(coro_factory: Callable[..., Coroutine[Any, Any, T]], *args: object, **kwargs: object) -> T:
    """Run an async task body to completion in a fresh event loop."""
    return asyncio.run(coro_factory(*args, **kwargs))


def is_last_attempt(max_retries: int) -> bool:
    """True when Dramatiq is on the final delivery of the current message.

    Lets an actor distinguish a *retriable* failure (re-raise so Dramatiq
    retries) from a *terminal* one (mark the note failed and notify the user).
    Relies on the ``CurrentMessage`` broker middleware; if it is unavailable we
    conservatively treat the attempt as terminal so notes never get stuck
    silently in a non-terminal state.
    """
    from dramatiq.middleware import CurrentMessage

    message = CurrentMessage.get_current_message()
    if message is None:
        return True
    retries: int = message.options.get("retries", 0) or 0
    return retries >= max_retries
