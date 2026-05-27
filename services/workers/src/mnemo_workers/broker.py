"""Dramatiq broker configured at module import time.

We set the broker before importing actor modules — Dramatiq registers actors
against whichever broker is current, so this file MUST be imported first.
"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, Callbacks, Pipelines, Retries, ShutdownNotifications, TimeLimit

from mnemo_api.config import get_settings

_settings = get_settings()
broker = RedisBroker(url=_settings.redis_url)

broker.add_middleware(AgeLimit())
broker.add_middleware(TimeLimit())
broker.add_middleware(ShutdownNotifications(notify_shutdown=True))
broker.add_middleware(Callbacks())
broker.add_middleware(Pipelines())
broker.add_middleware(Retries(max_retries=3, min_backoff=1_000, max_backoff=30_000))

dramatiq.set_broker(broker)
