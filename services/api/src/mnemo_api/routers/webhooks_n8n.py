"""Webhooks called BY n8n into the Core API.

All endpoints verify the HMAC signature and use an idempotency key (passed
in the `Idempotency-Key` header) to make replays safe. The `note-ready`
callback updates content fields and re-enters the text pipeline so the
note ends up chunked, embedded, and surfaced to the user.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.auth import verify_webhook_signature
from mnemo_api.db import get_session
from mnemo_api.exceptions import AuthError
from mnemo_api.logging import get_logger
from mnemo_api.metrics import webhook_total
from mnemo_api.models import IdempotencyKey, Note, NoteStatus
from mnemo_api.schemas import N8NNoteFailedIn, N8NNoteReadyIn
from mnemo_api.services.queue import enqueue

router = APIRouter(prefix="/v1/webhooks/n8n", tags=["webhooks-n8n"])
log = get_logger(__name__)


async def _verify_and_dedupe(
    request: Request,
    signature: str | None,
    timestamp: str | None,
    idem_key: str | None,
) -> tuple[bytes, str]:
    body = await request.body()
    try:
        verify_webhook_signature(body, signature, timestamp)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    if not idem_key:
        raise HTTPException(400, "Missing Idempotency-Key header")
    return body, idem_key


@router.post("/{event}", status_code=202)
async def n8n_webhook(
    event: str,
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Mnemo-Signature"),
    x_timestamp: str | None = Header(default=None, alias="X-Mnemo-Timestamp"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        body, idem = await _verify_and_dedupe(request, x_signature, x_timestamp, idempotency_key)
    except HTTPException:
        webhook_total.labels(event=event, outcome="rejected").inc()
        raise

    async for session in get_session():
        existing = await session.get(IdempotencyKey, idem)
        if existing is not None:
            webhook_total.labels(event=event, outcome="duplicate").inc()
            return existing.response_body or {"status": "duplicate"}

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            webhook_total.labels(event=event, outcome="rejected").inc()
            raise HTTPException(400, "Invalid JSON") from exc

        redis = request.app.state.redis

        try:
            if event == "note-ready":
                ready = N8NNoteReadyIn.model_validate(payload)
                response = await _handle_note_ready(session, redis, ready)
            elif event == "note-failed":
                failed = N8NNoteFailedIn.model_validate(payload)
                response = await _handle_note_failed(session, failed)
            else:
                webhook_total.labels(event=event, outcome="rejected").inc()
                raise HTTPException(404, f"Unknown event '{event}'")
        except HTTPException:
            raise
        except Exception:
            webhook_total.labels(event=event, outcome="error").inc()
            raise

        session.add(IdempotencyKey(key=idem, response_body=response))
        await session.commit()
        webhook_total.labels(event=event, outcome="accepted").inc()
        return response

    raise HTTPException(500, "Session unavailable")  # unreachable


async def _handle_note_ready(
    session: AsyncSession, redis: Any, payload: N8NNoteReadyIn
) -> dict[str, Any]:
    note = await session.get(Note, payload.note_id)
    if note is None:
        log.warning("webhook.note_ready.missing", note_id=str(payload.note_id))
        return {"status": "not_found"}
    if payload.processed_content is not None:
        note.processed_content = payload.processed_content
    if payload.summary is not None:
        note.summary = payload.summary
    if payload.title is not None:
        note.title = payload.title
    if payload.extracted_metadata:
        merged = dict(note.source_metadata or {})
        merged.update(payload.extracted_metadata)
        note.source_metadata = merged

    # Leave status at `pending` so the worker can claim it; the worker
    # flips it to `processing` and then `ready` once chunked/embedded.
    note.status = NoteStatus.pending.value
    await session.flush()

    # Hand off to the text pipeline for summary (if missing), tags, chunks,
    # embeddings, and the note-ready pub/sub notification.
    await enqueue(redis, "process_text_note", {"note_id": str(payload.note_id)})

    return {"status": "accepted", "note_id": str(payload.note_id)}


_FAIL_MSG_CAP = 2_000


async def _handle_note_failed(session: AsyncSession, payload: N8NNoteFailedIn) -> dict[str, Any]:
    note = await session.get(Note, payload.note_id)
    if note is None:
        return {"status": "not_found"}
    note.status = NoteStatus.failed.value
    note.error_message = payload.error_message[:_FAIL_MSG_CAP]
    return {"status": "accepted"}
