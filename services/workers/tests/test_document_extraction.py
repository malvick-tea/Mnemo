"""Document extraction smoke tests.

We test the bits that don't require optional third-party binaries (PDF/
DOCX/EPUB are exercised in integration tests with real fixtures). Here we
verify the routing layer, the markdown extractor (pure-Python), and the
whitespace normalizer.
"""

from __future__ import annotations

import pytest

from mnemo_workers.tasks.process_document import (
    UnsupportedDocumentError,
    _extract,
    _extract_markdown,
    _normalize_whitespace,
)


def test_unsupported_extension_rejected() -> None:
    with pytest.raises(UnsupportedDocumentError):
        _extract(b"x", "song.mp3")


def test_text_passthrough() -> None:
    text, kind = _extract(b"hello world\n", "notes.txt")
    assert kind == "text"
    assert "hello world" in text


def test_markdown_strips_formatting() -> None:
    md = b"# Title\n\nSome **bold** and a [link](https://x).\n"
    out = _extract_markdown(md)
    assert "Title" in out
    assert "bold" in out
    assert "**" not in out
    assert "https://x" not in out  # link target dropped, label kept


def test_normalize_collapses_runs() -> None:
    assert _normalize_whitespace("a   b\n\n\n\nc") == "a b\n\nc"
    assert _normalize_whitespace("  hi  ") == "hi"
