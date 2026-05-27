"""Service JWT + webhook HMAC tests."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from mnemo_api.auth import (
    make_service_token,
    verify_service_token,
    verify_webhook_signature,
)
from mnemo_api.config import get_settings
from mnemo_api.exceptions import AuthError, WebhookSignatureError


def test_service_token_roundtrip() -> None:
    token = make_service_token(123456)
    assert verify_service_token(token) == 123456


def test_expired_token_raises() -> None:
    token = make_service_token(123456, ttl_seconds=-1)
    with pytest.raises(AuthError):
        verify_service_token(token)


def test_webhook_signature_ok() -> None:
    body = b'{"note_id": "abc"}'
    ts = str(int(time.time()))
    secret = get_settings().webhook_hmac_secret.get_secret_value().encode("utf-8")
    sig = hmac.new(secret, f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    verify_webhook_signature(body, sig, ts)  # should not raise


def test_webhook_signature_replay_window() -> None:
    body = b"{}"
    old_ts = str(int(time.time()) - 10_000)
    with pytest.raises(WebhookSignatureError):
        verify_webhook_signature(body, "deadbeef", old_ts)


def test_webhook_signature_mismatch() -> None:
    body = b"{}"
    ts = str(int(time.time()))
    with pytest.raises(WebhookSignatureError):
        verify_webhook_signature(body, "0" * 64, ts)
