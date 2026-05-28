"""Worker tasks. Importing this package registers all actors with Dramatiq."""

# IMPORTANT: import the broker first so actors register against our broker.
from mnemo_workers import broker  # noqa: F401
from mnemo_workers.metrics_server import start_metrics_server
from mnemo_workers.tasks import (  # noqa: F401  (side-effect imports)
    cleanup,
    digest,
    embed,
    n8n,
    notion_sync,
    obsidian_export,
    process_document,
    process_photo,
    process_text,
    process_voice,
    summarize,
    tag,
)

# Start the Prometheus exporter once when this package is imported.
# Dispatcher and scheduler also re-import it; the second binding attempt
# logs a warning and continues, so no conflict.
start_metrics_server()
