"""Bridge from the API's lightweight Redis enqueue to Dramatiq.

The Core API drops a JSON marker on `mnemo:tasks` so it doesn't need
Dramatiq linked in. A small dispatcher in the workers process pops markers
and `.send()`s the corresponding actor. This keeps the API's dependency
surface narrow and lets us test the API without a full broker.

The dispatcher also publishes the queue depth gauge so a scrape of
``/metrics`` shows how backed-up the API→workers handoff is.
"""

from __future__ import annotations

import asyncio
import json
import signal
import time
from typing import Any

from redis.asyncio import Redis

from mnemo_api.config import get_settings
from mnemo_api.logging import configure_logging, get_logger
from mnemo_api.metrics import queue_depth
from mnemo_workers.metrics_server import start_metrics_server
from mnemo_workers.tasks.embed import embed_note
from mnemo_workers.tasks.n8n import trigger_n8n_workflow
from mnemo_workers.tasks.process_document import process_document_note
from mnemo_workers.tasks.process_photo import process_photo_note
from mnemo_workers.tasks.process_text import process_text_note
from mnemo_workers.tasks.process_voice import process_voice_note
from mnemo_workers.tasks.summarize import summarize_note
from mnemo_workers.tasks.tag import tag_note

_TASK_QUEUE = "mnemo:tasks"
_DEPTH_REFRESH_SECONDS = 5.0

_ACTORS: dict[str, Any] = {
    "process_text_note": process_text_note,
    "process_voice_note": process_voice_note,
    "process_photo_note": process_photo_note,
    "process_document_note": process_document_note,
    "embed_note": embed_note,
    "summarize_note": summarize_note,
    "tag_note": tag_note,
    "trigger_n8n_workflow": trigger_n8n_workflow,
}


async def _loop() -> None:
    log = get_logger("dispatcher")
    start_metrics_server()
    redis: Redis = Redis.from_url(get_settings().redis_url, decode_responses=False)
    stop = asyncio.Event()

    def _stop_handler(*_: object) -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _stop_handler)
        except NotImplementedError:
            # Windows
            signal.signal(sig, lambda *_: stop.set())

    log.info("dispatcher.start", queue=_TASK_QUEUE)
    last_depth_refresh = 0.0
    try:
        while not stop.is_set():
            res = await redis.brpop([_TASK_QUEUE], timeout=2)
            now = time.monotonic()
            if now - last_depth_refresh >= _DEPTH_REFRESH_SECONDS:
                try:
                    depth = await redis.llen(_TASK_QUEUE)
                    queue_depth.set(float(depth))
                except Exception:  # noqa: BLE001
                    pass
                last_depth_refresh = now

            if res is None:
                continue
            _key, raw = res
            try:
                msg = json.loads(raw)
                actor = _ACTORS.get(msg["task"])
                if actor is None:
                    log.warning("dispatcher.unknown_task", task=msg["task"])
                    continue
                payload = msg.get("payload") or {}
                actor.send(**payload)
            except Exception:  # noqa: BLE001
                log.exception("dispatcher.dispatch_failed", raw=raw[:200])
    finally:
        await redis.aclose()
        log.info("dispatcher.stop")


def main() -> None:
    configure_logging(get_settings().log_level)
    asyncio.run(_loop())


if __name__ == "__main__":
    main()
