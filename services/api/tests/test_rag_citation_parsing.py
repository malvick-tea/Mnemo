"""Citation parser unit test."""

from __future__ import annotations

import re

from mnemo_api.services.rag import _CITATION_RE


def test_picks_8hex_in_brackets() -> None:
    text = "First fact [a1b2c3d4]. Second fact [DEADBEEF] should NOT match (uppercase)."
    assert _CITATION_RE.findall(text) == ["a1b2c3d4"]


def test_multiple_citations() -> None:
    text = "Combined claim [abcdef01][12345678] is true."
    assert _CITATION_RE.findall(text) == ["abcdef01", "12345678"]


def test_not_confused_by_markdown_links() -> None:
    text = "See [docs](https://example.com)."
    assert _CITATION_RE.findall(text) == []
    # Sanity: the regex has correct hex requirement.
    assert re.fullmatch(r"[0-9a-f]{8}", "12345678") is not None
