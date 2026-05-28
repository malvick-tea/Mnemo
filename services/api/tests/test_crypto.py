"""AES-GCM round-trip."""

from __future__ import annotations

from mnemo_api.crypto import decrypt, encrypt


def test_roundtrip_basic() -> None:
    plain = b"hello world"
    ct = encrypt(plain)
    assert ct != plain
    assert decrypt(ct) == plain


def test_associated_data_binds_ciphertext() -> None:
    plain = b'{"k":"v"}'
    ct = encrypt(plain, associated_data=b"user:42")
    # Wrong AAD → exception
    import pytest
    from cryptography.exceptions import InvalidTag

    with pytest.raises(InvalidTag):
        decrypt(ct, associated_data=b"user:43")


def test_nonce_freshness() -> None:
    plain = b"x"
    a = encrypt(plain)
    b = encrypt(plain)
    assert a != b  # nonce changes per call
