"""Cross-cutting middleware: correlation IDs, structured request logs."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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
