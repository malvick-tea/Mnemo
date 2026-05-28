"""Test the lightweight Redis-based enqueue helper.

The helper is the thin contract between the API and the workers' dispatcher.
We verify the wire format the dispatcher will parse, not Redis itself.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest

from mnemo_api.services.queue import TASK_QUEUE, _json_safe, enqueue, trigger_n8n


class _FakeRedis:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def lpush(self, key: str, value: str) -> None:
        self.calls.append((key, value))


@pytest.mark.asyncio
async def test_enqueue_pushes_to_task_queue() -> None:
    r = _FakeRedis()
    await enqueue(r, "process_text_note", {"note_id": "abc"})  # type: ignore[arg-type]
    assert r.calls and r.calls[0][0] == TASK_QUEUE
    msg = json.loads(r.calls[0][1])
    assert msg["task"] == "process_text_note"
    assert msg["payload"] == {"note_id": "abc"}
    assert "enqueued_at" in msg


@pytest.mark.asyncio
async def test_enqueue_serializes_uuid() -> None:
    r = _FakeRedis()
    nid = uuid4()
    await enqueue(r, "process_voice_note", {"note_id": nid, "blob_key": "k"})  # type: ignore[arg-type]
    msg = json.loads(r.calls[0][1])
    assert msg["payload"]["note_id"] == str(nid)


@pytest.mark.asyncio
async def test_trigger_n8n_emits_correct_actor_name() -> None:
    r = _FakeRedis()
    nid = uuid4()
    await trigger_n8n(r, "001-url-ingest", note_id=nid, url="https://x")  # type: ignore[arg-type]
    msg = json.loads(r.calls[0][1])
    assert msg["task"] == "trigger_n8n_workflow"
    assert msg["payload"]["workflow"] == "001-url-ingest"
    assert msg["payload"]["note_id"] == str(nid)


def test_json_safe_handles_nested_uuid() -> None:
    nid = UUID("12345678-1234-5678-1234-567812345678")
    out: Any = _json_safe({"id": nid, "list": [nid, "x"], "deep": {"u": nid}})
    assert out["id"] == str(nid)
    assert out["list"][0] == str(nid)
    assert out["deep"]["u"] == str(nid)
