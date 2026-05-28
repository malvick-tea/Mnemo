"""Sanity checks for capture DTOs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mnemo_api.schemas import (
    CaptureForwardIn,
    CaptureTextIn,
    CaptureURLIn,
    ForwardMetadata,
)


def test_capture_text_requires_non_empty() -> None:
    with pytest.raises(ValidationError):
        CaptureTextIn(content="")
    ok = CaptureTextIn(content="hello")
    assert ok.content == "hello"


def test_capture_url_validates_http() -> None:
    with pytest.raises(ValidationError):
        CaptureURLIn(url="not a url")  # type: ignore[arg-type]
    ok = CaptureURLIn(url="https://example.com/post")  # type: ignore[arg-type]
    assert str(ok.url).startswith("https://example.com")


def test_capture_forward_round_trip() -> None:
    payload = CaptureForwardIn(
        content="forwarded body",
        forward=ForwardMetadata(
            origin_type="channel",
            from_chat_id=-100123,
            from_chat_title="Best Channel",
            message_id=42,
        ),
    )
    dumped = payload.model_dump()
    assert dumped["forward"]["origin_type"] == "channel"
    assert dumped["forward"]["from_chat_title"] == "Best Channel"
    # Round-trip
    again = CaptureForwardIn.model_validate(dumped)
    assert again.forward.message_id == 42


def test_forward_metadata_strips_unknown_origin_type() -> None:
    with pytest.raises(ValidationError):
        ForwardMetadata(origin_type="alien")  # type: ignore[arg-type]
