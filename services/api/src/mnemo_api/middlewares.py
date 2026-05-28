"""Cross-cutting middleware: correlation IDs, structured request logs,
Redis-backed per-IP/per-user rate limiting."""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mnemo_api.config import get_settings
from mnemo_api.logging import correlation_id_ctx, get_logger

_log = get_logger("http")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("X-Correlation-ID")
        cid = incoming or uuid.uuid4().hex
        token = correlation_id_ctx.set(cid)
        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx.reset(token)
        response.headers["X-Correlation-ID"] = cid
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency = int((time.perf_counter() - t0) * 1000)
            _log.exception(
                "http.request.error",
                method=request.method,
                path=request.url.path,
                latency_ms=latency,
            )
            raise
        latency = int((time.perf_counter() - t0) * 1000)
        _log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket per-identity at the API edge.

    The bot already throttles per-tg-user; this is the API-side
    belt-and-suspenders so a misbehaving caller can't flood the LLM.
    Keyed off the JWT token (hashed) when present, falls back to client IP.

    The cap multiplies the bot's per-minute throttle since one bot user can
    legitimately cause multiple API calls (capture + summarize + tag +
    embed are pipelined). 6x is generous; tune via env if needed.
    """

    _EXEMPT_PREFIXES = ("/v1/healthz", "/v1/readyz", "/metrics")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith(self._EXEMPT_PREFIXES):
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            # Lifespan hasn't started yet (e.g. healthz called early).
            return await call_next(request)

        settings = get_settings()
        per_minute = settings.throttle_per_min * 6  # see docstring
        key_id = _identity_key(request)
        now_min = int(time.time() // 60)
        bucket = f"mnemo:rl_api:{key_id}:{now_min}"

        pipe = redis.pipeline()
        pipe.incr(bucket, 1)
        pipe.expire(bucket, 90)
        count, _ = await pipe.execute()

        if count > per_minute:
            return JSONResponse(
                {
                    "error": "rate_limit_exceeded",
                    "detail": (
                        f"More than {per_minute} requests/min; "
                        "retry after the current minute closes."
                    ),
                },
                status_code=429,
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


def _identity_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1]
        return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    client = request.client
    return client.host if client else "anon"
