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
