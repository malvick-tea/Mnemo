"""Actor that fires off the HTTP trigger to an n8n workflow.

Captures enqueue this so the API endpoint can return fast and not block on
n8n availability.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from uuid import UUID

import dramatiq
import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mnemo_api.config import get_settings
from mnemo_api.logging import get_logger
from mnemo_workers.runner import run

log = get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=5, time_limit=30_000)
def trigger_n8n_workflow(workflow: str, **payload: Any) -> None:
    run(_trigger, workflow, payload)


async def _trigger(workflow: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    body = json.dumps(payload).encode("utf-8")
    ts = str(int(time.time()))
    secret = settings.webhook_hmac_secret.get_secret_value().encode("utf-8")
    sig = hmac.new(secret, f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    idem = f"{workflow}:{payload.get('note_id', UUID(int=0))}:{ts[:8]}"

    url = f"{settings.n8n_base_url}/webhook/mnemo/{workflow}"
    headers = {
        "Content-Type": "application/json",
        "X-Mnemo-Signature": sig,
        "X-Mnemo-Timestamp": ts,
        "Idempotency-Key": idem,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, max=10),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        ):
            with attempt:
                resp = await client.post(url, content=body, headers=headers)
                resp.raise_for_status()
    log.info("n8n.trigger.ok", workflow=workflow, payload_keys=list(payload))
