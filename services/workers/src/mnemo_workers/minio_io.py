"""MinIO client helpers for worker tasks.

Workers grab the singleton client and read blobs by key. We keep a single
client per process so we don't churn TLS handshakes per task.
"""

from __future__ import annotations

import io
from functools import lru_cache

from minio import Minio
from mnemo_api.config import get_settings


@lru_cache(maxsize=1)
def get_minio_client() -> Minio:
    s = get_settings()
    return Minio(
        endpoint=s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key.get_secret_value(),
        secure=s.minio_use_tls,
    )


def download_blob(blob_key: str) -> bytes:
    """Read the entire object into memory.

    For the uploads Mnemo accepts (≤MNEMO_MAX_UPLOAD_MB, typically 50 MB)
    in-memory is fine. Streaming is a milestone-3 concern for >100 MB blobs.
    """
    s = get_settings()
    client = get_minio_client()
    response = client.get_object(s.minio_bucket, blob_key)
    try:
        with io.BytesIO() as buf:
            for chunk in response.stream(64 * 1024):
                buf.write(chunk)
            return buf.getvalue()
    finally:
        response.close()
        response.release_conn()
