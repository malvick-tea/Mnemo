"""Worker tasks. Importing this package registers all actors with Dramatiq."""

# IMPORTANT: import the broker first so actors register against our broker.
from mnemo_workers import broker  # noqa: F401

from mnemo_workers.tasks import (  # noqa: F401  (side-effect imports)
    embed,
    n8n,
    process_text,
    summarize,
    tag,
)
