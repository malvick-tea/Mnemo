"""JWT + HMAC verification.

- Service JWT: bot → API; HS256 signed with `MNEMO_SERVICE_JWT_SECRET`,
  exp ≤ 15 minutes. Payload includes the originating TG user ID.
- HMAC: n8n → API webhooks; SHA-256 over body keyed with
  `MNEMO_WEBHOOK_HMAC_SECRET`.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from mnemo_api.config import get_settings
from mnemo_api.exceptions import AuthError, WebhookSignatureError

_JWT_ALG = "HS256"
_REPLAY_WINDOW_SECONDS = 300


def make_service_token(tg_user_id: int, *, ttl_seconds: int = 900) -> str:
    """Bot calls this to mint a token before each API request."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(tg_user_id),
        "iss": "mnemo-bot",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.service_jwt_secret.get_secret_value(), algorithm=_JWT_ALG)


def verify_service_token(token: str) -> int:
    """Returns the `tg_user_id`. Raises AuthError on any failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.service_jwt_secret.get_secret_value(),
            algorithms=[_JWT_ALG],
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid service token: {exc}") from exc

    try:
        return int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthError("Service token missing tg_user_id") from exc


def verify_webhook_signature(
    body: bytes, signature_header: str | None, timestamp_header: str | None
) -> None:
    """Raises `WebhookSignatureError` on any mismatch / replay attempt."""
    if not signature_header or not timestamp_header:
        raise WebhookSignatureError("Missing signature or timestamp header")

    try:
        ts = int(timestamp_header)
    except ValueError as exc:
        raise WebhookSignatureError("Bad timestamp header") from exc

    if abs(int(time.time()) - ts) > _REPLAY_WINDOW_SECONDS:
        raise WebhookSignatureError("Timestamp outside replay window")

    secret = get_settings().webhook_hmac_secret.get_secret_value().encode("utf-8")
    expected = hmac.new(secret, f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise WebhookSignatureError("Signature mismatch")
