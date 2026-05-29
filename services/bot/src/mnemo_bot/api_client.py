"""Thin HTTP client for the Core API.

Mints a fresh service JWT per call (cheap; HS256 sign of ~120 bytes) and
includes the correlation ID from contextvars so logs join on both sides.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import jwt
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mnemo_bot.config import get_settings
from mnemo_bot.logging import correlation_id_ctx, get_logger

log = get_logger(__name__)

_JWT_ALG = "HS256"
# Must match the API's verify_service_token (issuer + audience are enforced).
_JWT_ISSUER = "mnemo-bot"
_JWT_AUDIENCE = "mnemo-api"


def _service_token(tg_user_id: int) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(tg_user_id),
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    return jwt.encode(payload, s.service_jwt_secret.get_secret_value(), algorithm=_JWT_ALG)


class ApiClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=get_settings().api_base_url, timeout=60.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def capture_text(
        self, tg_user_id: int, content: str, source_metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._request(
            tg_user_id,
            "POST",
            "/v1/capture/text",
            json={"content": content, "source_metadata": source_metadata or {}},
        )

    async def capture_url(
        self, tg_user_id: int, url: str, source_metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._request(
            tg_user_id,
            "POST",
            "/v1/capture/url",
            json={"url": url, "source_metadata": source_metadata or {}},
        )

    async def capture_voice(
        self,
        tg_user_id: int,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        files = {"file": (filename, file_bytes, content_type)}
        return await self._request(tg_user_id, "POST", "/v1/capture/voice", files=files)

    async def capture_photo(
        self,
        tg_user_id: int,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        files = {"file": (filename, file_bytes, content_type)}
        data: dict[str, str] = {}
        if caption:
            data["caption"] = caption
        return await self._request(
            tg_user_id,
            "POST",
            "/v1/capture/photo",
            files=files,
            data=data,
        )

    async def capture_document(
        self,
        tg_user_id: int,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        files = {"file": (filename, file_bytes, content_type)}
        return await self._request(tg_user_id, "POST", "/v1/capture/document", files=files)

    async def capture_forward(
        self,
        tg_user_id: int,
        content: str,
        forward: dict[str, Any],
        source_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            tg_user_id,
            "POST",
            "/v1/capture/forward",
            json={
                "content": content,
                "forward": forward,
                "source_metadata": source_metadata or {},
            },
        )

    async def query(self, tg_user_id: int, q: str, top_k: int = 8) -> dict[str, Any]:
        return await self._request(
            tg_user_id, "POST", "/v1/query", json={"query": q, "top_k": top_k}
        )

    async def feedback(self, tg_user_id: int, query_id: UUID, rating: int) -> None:
        await self._request(
            tg_user_id,
            "POST",
            f"/v1/query/{query_id}/feedback",
            json={"rating": rating},
        )

    async def digest_today(self, tg_user_id: int) -> dict[str, Any]:
        return await self._request(tg_user_id, "POST", "/v1/digest/today", json={"mode": "preview"})

    async def get_settings(self, tg_user_id: int) -> dict[str, Any]:
        return await self._request(tg_user_id, "GET", "/v1/settings")

    async def patch_settings(self, tg_user_id: int, settings: dict[str, Any]) -> dict[str, Any]:
        return await self._request(tg_user_id, "PATCH", "/v1/settings", json={"settings": settings})

    async def get_note(self, tg_user_id: int, note_id: UUID) -> dict[str, Any]:
        return await self._request(tg_user_id, "GET", f"/v1/notes/{note_id}")

    async def update_note(self, tg_user_id: int, note_id: UUID, **fields: Any) -> dict[str, Any]:
        return await self._request(tg_user_id, "PATCH", f"/v1/notes/{note_id}", json=fields)

    async def delete_note(self, tg_user_id: int, note_id: UUID) -> None:
        await self._request(tg_user_id, "DELETE", f"/v1/notes/{note_id}")

    async def generate_anki(self, tg_user_id: int, note_id: UUID) -> dict[str, Any]:
        return await self._request(tg_user_id, "POST", f"/v1/notes/{note_id}/anki")

    async def _request(
        self, tg_user_id: int, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {_service_token(tg_user_id)}",
        }
        cid = correlation_id_ctx.get()
        if cid is not None:
            headers["X-Correlation-ID"] = cid

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, max=4),
            retry=retry_if_exception_type((httpx.NetworkError, httpx.RemoteProtocolError)),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.request(method, path, headers=headers, **kwargs)
                if 500 <= resp.status_code < 600:
                    raise httpx.RemoteProtocolError(f"api 5xx: {resp.status_code}")
                resp.raise_for_status()
                return resp.json() if resp.content else {}
        # unreachable
        raise RuntimeError("retry exhausted")
