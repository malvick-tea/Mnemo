"""Start a Prometheus exporter in the workers process.

The API exposes its own ``/metrics`` via FastAPI's `make_asgi_app`. The
workers, dispatcher, and scheduler are long-running Python processes
without an HTTP framework, so we start a small `prometheus_client` HTTP
server in a daemon thread. Port defaults to 9101; override via
`MNEMO_METRICS_PORT`.
"""

from __future__ import annotations

import os

from mnemo_api.logging import get_logger
from prometheus_client import start_http_server

log = get_logger(__name__)


def start_metrics_server() -> None:
    if os.environ.get("MNEMO_METRICS_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        return
    port = int(os.environ.get("MNEMO_METRICS_PORT", "9101"))
    try:
        start_http_server(port)
        log.info("metrics.exporter.start", port=port)
    except OSError as exc:
        # Port already taken — likely a second worker process in the same
        # container. That's fine, the first one is exporting.
        log.warning("metrics.exporter.skip", port=port, error=str(exc))
