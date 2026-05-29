"""Size bounds for user-supplied JSON blobs.

``source_metadata``, ``settings``, and integration ``config`` are free-form
``dict[str, Any]`` columns. Left unbounded they invite JSONB bloat and
oversized writes. ``bounded_mapping`` caps key count, key length, and the
serialized byte size; it is wired into the relevant Pydantic models as a
field validator (raising ``ValueError`` → HTTP 422).
"""

from __future__ import annotations

import json
from typing import Any

MAX_METADATA_KEYS = 32
MAX_METADATA_BYTES = 8_192
MAX_CONFIG_KEYS = 64
MAX_CONFIG_BYTES = 16_384
MAX_KEY_LEN = 128


def bounded_mapping(
    value: dict[str, Any],
    *,
    what: str,
    max_keys: int = MAX_METADATA_KEYS,
    max_bytes: int = MAX_METADATA_BYTES,
) -> dict[str, Any]:
    if len(value) > max_keys:
        raise ValueError(f"{what}: too many keys ({len(value)} > {max_keys}).")
    for key in value:
        if not isinstance(key, str) or len(key) > MAX_KEY_LEN:
            raise ValueError(f"{what}: keys must be strings of at most {MAX_KEY_LEN} chars.")
    try:
        size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what}: must be JSON-serializable.") from exc
    if size > max_bytes:
        raise ValueError(f"{what}: payload too large ({size} > {max_bytes} bytes).")
    return value
