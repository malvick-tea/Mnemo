"""Capture endpoints."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from minio import Minio
from redis.asyncio import Redis

from mnemo_api.config import get_settings
from mnemo_api.deps import CurrentUser, SessionDep, get_minio, get_redis
from mnemo_api.schemas import CaptureResponse, CaptureTextIn, CaptureURLIn
from mnemo_api.services import capture as capture_svc

router = APIRouter(prefix="/v1/capture", tags=["capture"])


@router.post("/text", response_model=CaptureResponse, status_code=201)
async def capture_text(
    payload: CaptureTextIn,
    user: CurrentUser,
    session: SessionDep,
    redis: Redis = get_redis,  # type: ignore[assignment]
) -> CaptureResponse:
    note = await capture_svc.create_text_note(
        session, redis,
        user=user,
        content=payload.content,
        captured_at=payload.captured_at,
        source_metadata=payload.source_metadata,
    )
    await session.commit()
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


@router.post("/url", response_model=CaptureResponse, status_code=201)
async def capture_url(
    payload: CaptureURLIn,
    user: CurrentUser,
    session: SessionDep,
    redis: Redis = get_redis,  # type: ignore[assignment]
) -> CaptureResponse:
    note = await capture_svc.create_url_note(
        session, redis,
        user=user,
        url=str(payload.url),
        captured_at=payload.captured_at,
        source_metadata=payload.source_metadata,
    )
    await session.commit()
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


@router.post("/voice", response_model=CaptureResponse, status_code=201)
async def capture_voice(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
    captured_at: datetime = Form(default_factory=lambda: datetime.now(UTC)),
    redis: Redis = get_redis,            # type: ignore[assignment]
    minio: Minio = get_minio,            # type: ignore[assignment]
) -> CaptureResponse:
    settings = get_settings()
    body = await _read_capped(file, settings.max_upload_mb)
    blob_key = (
        f"{user.id}/{datetime.now(UTC):%Y/%m}/{uuid4()}/"
        f"{file.filename or 'voice.ogg'}"
    )
    _put_object(minio, settings.minio_bucket, blob_key, body, file.content_type)
    note = await capture_svc.create_voice_note(
        session, redis,
        user=user,
        blob_key=blob_key,
        captured_at=captured_at,
        source_metadata={"size_bytes": len(body), "mime": file.content_type},
    )
    await session.commit()
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


@router.post("/photo", response_model=CaptureResponse, status_code=201)
async def capture_photo(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
) -> CaptureResponse:
    # TODO(milestone-2): wire photo OCR pipeline (n8n workflow 003-photo-ocr).
    raise HTTPException(501, detail="photo capture not yet implemented (milestone-2)")


@router.post("/document", response_model=CaptureResponse, status_code=201)
async def capture_document(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
) -> CaptureResponse:
    # TODO(milestone-2): wire document parsing (n8n workflow 004-document-parse).
    raise HTTPException(501, detail="document capture not yet implemented (milestone-2)")


@router.post("/forward", response_model=CaptureResponse, status_code=201)
async def capture_forward(
    user: CurrentUser,
    session: SessionDep,
) -> CaptureResponse:
    # TODO(milestone-2): wire forwarded message capture.
    raise HTTPException(501, detail="forward capture not yet implemented (milestone-2)")


# ─── helpers ────────────────────────────────────────────────────────────────


async def _read_capped(upload: UploadFile, max_mb: int) -> bytes:
    limit = max_mb * 1024 * 1024
    body = await upload.read(limit + 1)
    if len(body) > limit:
        raise HTTPException(413, f"Upload exceeds {max_mb} MB limit")
    return body


def _put_object(
    minio: Minio, bucket: str, key: str, body: bytes, content_type: str | None
) -> None:
    minio.put_object(
        bucket,
        key,
        data=io.BytesIO(body),
        length=len(body),
        content_type=content_type or "application/octet-stream",
    )
    _ = cast(object, minio)  # mypy: silence "unused minio after call" smell
