"""Dramatiq broker configured at module import time.

We set the broker before importing actor modules — Dramatiq registers actors
against whichever broker is current, so this file MUST be imported first.
"""

from __future__ import annotations

import time
from typing import Any

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import (
    AgeLimit,
    Callbacks,
    Middleware,
    Pipelines,
    Retries,
    ShutdownNotifications,
    TimeLimit,
)

from mnemo_api.config import get_settings
from mnemo_api.metrics import worker_task_seconds, worker_task_total

_settings = get_settings()
broker = RedisBroker(url=_settings.redis_url)


class MetricsMiddleware(Middleware):
    """Records `worker_task_total{actor,outcome}` + `worker_task_seconds{actor}`.

    Lives at the broker level so every actor is instrumented uniformly,
    including future ones — no per-actor boilerplate.
    """

    def before_process_message(self, broker: Any, message: Any) -> None:
        message.options["_mnemo_t0"] = time.perf_counter()

    def after_process_message(
        self,
        broker: Any,
        message: Any,
        *,
        result: Any = None,
        exception: BaseException | None = None,
    ) -> None:
        t0 = message.options.get("_mnemo_t0")
        if t0 is not None:
            worker_task_seconds.labels(actor=message.actor_name).observe(
                time.perf_counter() - t0
            )
        outcome = "error" if exception is not None else "ok"
        worker_task_total.labels(
            actor=message.actor_name, outcome=outcome,
        ).inc()


broker.add_middleware(AgeLimit())
broker.add_middleware(TimeLimit())
broker.add_middleware(ShutdownNotifications(notify_shutdown=True))
broker.add_middleware(Callbacks())
broker.add_middleware(Pipelines())
broker.add_middleware(Retries(max_retries=3, min_backoff=1_000, max_backoff=30_000))
broker.add_middleware(MetricsMiddleware())

dramatiq.set_broker(broker)
