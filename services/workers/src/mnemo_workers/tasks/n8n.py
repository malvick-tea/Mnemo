"""Actor that fires off the HTTP trigger to an n8n workflow.

Captures enqueue this so the API endpoint can return fast and not block on
n8n availability.

Signing contract (must match every workflow's "Verify HMAC" node):
    signature = HMAC_SHA256(secret, f"{ts}." + canonical_json(payload))
where ``canonical_json`` is JSON with sorted keys and no whitespace
(``separators=(",", ":")``). Both sides reconstruct the *same* canonical bytes
from the parsed payload, so re-serialization on the n8n side can no longer
diverge from what we signed.
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
from mnemo_api.config import get_settings
from mnemo_api.db import session_factory
from mnemo_api.logging import get_logger
from mnemo_api.models import Note, NoteStatus, User
from mnemo_api.services.events import publish_note_ready
from sqlalchemy import select
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mnemo_workers.redis_io import get_redis
from mnemo_workers.runner import is_last_attempt, run

log = get_logger(__name__)

_MAX_RETRIES = 5


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Deterministic JSON encoding shared with the n8n verify nodes."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode(
        "utf-8"
    )


@dramatiq.actor(queue_name="default", max_retries=_MAX_RETRIES, time_limit=30_000)
def trigger_n8n_workflow(workflow: str, **payload: Any) -> None:
    run(_trigger, workflow, payload)


async def _trigger(workflow: str, payload: dict[str, Any]) -> None:
    try:
        await _fire(workflow, payload)
    except Exception:
        # Re-raise while Dramatiq still has retries left. Only once delivery is
        # truly exhausted do we surface the failure: mark the note failed and
        # notify the bot so the user's placeholder doesn't sit in `pending`
        # forever.
        if not is_last_attempt(_MAX_RETRIES):
            raise
        note_id = payload.get("note_id")
        log.error("n8n.trigger.exhausted", workflow=workflow, note_id=note_id)
        if note_id is not None:
            await _fail_and_notify(UUID(str(note_id)), f"{workflow}: upstream trigger failed")
        raise


async def _fire(workflow: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    body = canonical_json(payload)
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


async def _fail_and_notify(note_id: UUID, message: str) -> None:
    """Terminal failure path: flip the note to `failed` and tell the bot."""
    redis = get_redis()
    try:
        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None:
                return
            note.status = NoteStatus.failed.value
            note.error_message = message[:2_000]
            user = await session.get(User, note.user_id)
            tg_user_id = user.tg_user_id if user is not None else None
            user_id = note.user_id
            await session.commit()
        if tg_user_id is not None:
            await publish_note_ready(redis, user_id=user_id, tg_user_id=tg_user_id, note_id=note_id)
    except Exception:
        log.exception("n8n.trigger.fail_notify_failed", note_id=str(note_id))
    finally:
        await redis.aclose()
