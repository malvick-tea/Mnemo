"""Custom exception hierarchy.

External-facing errors translate to deterministic HTTP responses in
`mnemo_api.main`. Internal-only errors stay as-is and bubble to the
ASGI middleware.
"""

from __future__ import annotations


class MnemoError(Exception):
    """Base class for every error Mnemo raises on purpose."""

    http_status: int = 500
    error_code: str = "internal_error"


class NotFoundError(MnemoError):
    http_status = 404
    error_code = "not_found"


class ValidationError(MnemoError):
    http_status = 422
    error_code = "validation_error"


class AuthError(MnemoError):
    http_status = 401
    error_code = "unauthorized"


class ForbiddenError(MnemoError):
    http_status = 403
    error_code = "forbidden"


class WebhookSignatureError(AuthError):
    error_code = "webhook_signature_invalid"


class IdempotencyConflict(MnemoError):
    http_status = 409
    error_code = "idempotency_conflict"


class ProviderError(MnemoError):
    """Upstream LLM / ASR / OCR provider failure."""

    http_status = 502
    error_code = "provider_error"


class QuotaExceeded(MnemoError):
    http_status = 429
    error_code = "quota_exceeded"
