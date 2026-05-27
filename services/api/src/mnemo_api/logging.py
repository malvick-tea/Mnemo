"""structlog setup.

One processor chain for the whole app. The correlation ID processor reads
from a contextvar that the request middleware sets per request.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog

correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


def _add_context(_logger: object, _method: str, event_dict: dict[str, object]) -> dict[str, object]:
    cid = correlation_id_ctx.get()
    if cid is not None:
        event_dict["correlation_id"] = cid
    uid = user_id_ctx.get()
    if uid is not None:
        event_dict["user_id"] = uid
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
