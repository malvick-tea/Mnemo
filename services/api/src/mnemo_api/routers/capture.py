"""Capture endpoints.

Heavy uploads (voice/photo/document) stream into MinIO; light captures
(text, url, forward) carry the content in the JSON body. All paths end in
a Note row + a worker enqueue so the API stays responsive.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from mnemo_api.config import get_settings
from mnemo_api.deps import CurrentUser, MinioDep, RedisDep, SessionDep
from mnemo_api.metrics import capture_bytes, capture_total
from mnemo_api.schemas import (
    CaptureForwardIn,
    CaptureResponse,
    CaptureTextIn,
    CaptureURLIn,
)
from mnemo_api.services import capture as capture_svc

router = APIRouter(prefix="/v1/capture", tags=["capture"])


@router.post("/text", response_model=CaptureResponse, status_code=201)
async def capture_text(
    payload: CaptureTextIn,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
) -> CaptureResponse:
    try:
        note = await capture_svc.create_text_note(
            session,
            redis,
            user=user,
            content=payload.content,
            captured_at=payload.captured_at,
            source_metadata=payload.source_metadata,
        )
        await session.commit()
    except Exception:
        capture_total.labels(source_type="text", outcome="error").inc()
        raise
    capture_total.labels(source_type="text", outcome="ok").inc()
    capture_bytes.labels(source_type="text").inc(len(payload.content))
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


@router.post("/url", response_model=CaptureResponse, status_code=201)
async def capture_url(
    payload: CaptureURLIn,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
) -> CaptureResponse:
    try:
        note = await capture_svc.create_url_note(
            session,
            redis,
            user=user,
            url=str(payload.url),
            captured_at=payload.captured_at,
            source_metadata=payload.source_metadata,
        )
        await session.commit()
    except Exception:
        capture_total.labels(source_type="url", outcome="error").inc()
        raise
    capture_total.labels(source_type="url", outcome="ok").inc()
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


@router.post("/voice", response_model=CaptureResponse, status_code=201)
async def capture_voice(
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    minio: MinioDep,
    file: UploadFile = File(...),
    captured_at: datetime = Form(default_factory=lambda: datetime.now(UTC)),
) -> CaptureResponse:
    settings = get_settings()
    try:
        body = await _read_capped(file, settings.max_upload_mb)
    except HTTPException:
        capture_total.labels(source_type="voice", outcome="rejected").inc()
        raise
    blob_key = _build_blob_key(user.id, file.filename or "voice.ogg")
    try:
        _put_object(minio, settings.minio_bucket, blob_key, body, file.content_type)
        note = await capture_svc.create_voice_note(
            session,
            redis,
            user=user,
            blob_key=blob_key,
            captured_at=captured_at,
            source_metadata={"size_bytes": len(body), "mime": file.content_type},
        )
        await session.commit()
    except Exception:
        capture_total.labels(source_type="voice", outcome="error").inc()
        raise
    capture_total.labels(source_type="voice", outcome="ok").inc()
    capture_bytes.labels(source_type="voice").inc(len(body))
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


@router.post("/photo", response_model=CaptureResponse, status_code=201)
async def capture_photo(
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    minio: MinioDep,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None),
    captured_at: datetime = Form(default_factory=lambda: datetime.now(UTC)),
) -> CaptureResponse:
    settings = get_settings()
    try:
        body = await _read_capped(file, settings.max_upload_mb)
    except HTTPException:
        capture_total.labels(source_type="photo", outcome="rejected").inc()
        raise
    mime = (file.content_type or "image/jpeg").lower()
    if not mime.startswith("image/"):
        capture_total.labels(source_type="photo", outcome="rejected").inc()
        raise HTTPException(415, f"Not an image MIME type: {mime}")
    blob_key = _build_blob_key(user.id, file.filename or "photo.jpg")
    try:
        _put_object(minio, settings.minio_bucket, blob_key, body, mime)
        note = await capture_svc.create_photo_note(
            session,
            redis,
            user=user,
            blob_key=blob_key,
            caption=caption,
            captured_at=captured_at,
            source_metadata={"size_bytes": len(body), "mime": mime},
        )
        await session.commit()
    except Exception:
        capture_total.labels(source_type="photo", outcome="error").inc()
        raise
    capture_total.labels(source_type="photo", outcome="ok").inc()
    capture_bytes.labels(source_type="photo").inc(len(body))
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


_ALLOWED_DOC_MIMES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/epub+zip",
        "text/plain",
        "text/markdown",
        "application/octet-stream",  # Telegram sometimes sends this for .md
    }
)


@router.post("/document", response_model=CaptureResponse, status_code=201)
async def capture_document(
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    minio: MinioDep,
    file: UploadFile = File(...),
    captured_at: datetime = Form(default_factory=lambda: datetime.now(UTC)),
) -> CaptureResponse:
    settings = get_settings()
    try:
        body = await _read_capped(file, settings.max_upload_mb)
    except HTTPException:
        capture_total.labels(source_type="document", outcome="rejected").inc()
        raise
    mime = (file.content_type or "application/octet-stream").lower()
    filename = file.filename or "document"
    if mime not in _ALLOWED_DOC_MIMES and not _has_known_ext(filename):
        capture_total.labels(source_type="document", outcome="rejected").inc()
        raise HTTPException(415, f"Unsupported document type: {mime} ({filename})")
    blob_key = _build_blob_key(user.id, filename)
    try:
        _put_object(minio, settings.minio_bucket, blob_key, body, mime)
        note = await capture_svc.create_document_note(
            session,
            redis,
            user=user,
            blob_key=blob_key,
            filename=filename,
            mime=mime,
            captured_at=captured_at,
            source_metadata={"size_bytes": len(body)},
        )
        await session.commit()
    except Exception:
        capture_total.labels(source_type="document", outcome="error").inc()
        raise
    capture_total.labels(source_type="document", outcome="ok").inc()
    capture_bytes.labels(source_type="document").inc(len(body))
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


@router.post("/forward", response_model=CaptureResponse, status_code=201)
async def capture_forward(
    payload: CaptureForwardIn,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
) -> CaptureResponse:
    forward_meta = payload.forward.model_dump(mode="json", exclude_none=True)
    try:
        note = await capture_svc.create_forward_note(
            session,
            redis,
            user=user,
            content=payload.content,
            forward_metadata=forward_meta,
            captured_at=payload.captured_at,
            source_metadata=payload.source_metadata,
        )
        await session.commit()
    except Exception:
        capture_total.labels(source_type="forward", outcome="error").inc()
        raise
    capture_total.labels(source_type="forward", outcome="ok").inc()
    capture_bytes.labels(source_type="forward").inc(len(payload.content))
    return CaptureResponse(note_id=note.id, status=note.status)  # type: ignore[arg-type]


# ─── helpers ────────────────────────────────────────────────────────────────


_KNOWN_DOC_EXTS = (".pdf", ".docx", ".epub", ".md", ".markdown", ".txt")


def _has_known_ext(filename: str) -> bool:
    return filename.lower().endswith(_KNOWN_DOC_EXTS)


def _build_blob_key(user_id: UUID, filename: str) -> str:
    return f"{user_id}/{datetime.now(UTC):%Y/%m}/{uuid4()}/{filename}"


async def _read_capped(upload: UploadFile, max_mb: int) -> bytes:
    limit = max_mb * 1024 * 1024
    body = await upload.read(limit + 1)
    if len(body) > limit:
        raise HTTPException(413, f"Upload exceeds {max_mb} MB limit")
    return body


def _put_object(
    minio: object,
    bucket: str,
    key: str,
    body: bytes,
    content_type: str | None,
) -> None:
    minio.put_object(  # type: ignore[attr-defined]
        bucket,
        key,
        data=io.BytesIO(body),
        length=len(body),
        content_type=content_type or "application/octet-stream",
    )
