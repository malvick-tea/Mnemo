"""AES-GCM encryption for integration credentials at rest.

Key material lives only in `MNEMO_ENCRYPTION_KEY` — 32 raw bytes,
base64-encoded. The nonce is generated fresh per encryption and prepended to
the ciphertext.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from mnemo_api.config import get_settings

_NONCE_LEN = 12


def _key_bytes() -> bytes:
    raw = base64.b64decode(get_settings().encryption_key.get_secret_value())
    if len(raw) != 32:
        raise RuntimeError(
            "MNEMO_ENCRYPTION_KEY must decode to exactly 32 bytes "
            f"(got {len(raw)}). Regenerate with `openssl rand -base64 32`."
        )
    return raw


def encrypt(plaintext: bytes, *, associated_data: bytes | None = None) -> bytes:
    nonce = os.urandom(_NONCE_LEN)
    aes = AESGCM(_key_bytes())
    ct = aes.encrypt(nonce, plaintext, associated_data)
    return nonce + ct


def decrypt(blob: bytes, *, associated_data: bytes | None = None) -> bytes:
    nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    aes = AESGCM(_key_bytes())
    return aes.decrypt(nonce, ct, associated_data)
