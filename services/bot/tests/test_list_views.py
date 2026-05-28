"""Unit tests for the read-only command helpers."""

from __future__ import annotations

from mnemo_bot.handlers.list_views import _format_tags


def test_format_tags_sorts_by_count() -> None:
    out = _format_tags(
        [
            {"name": "rare", "count": 1},
            {"name": "popular", "count": 42},
            {"name": "mid", "count": 7},
        ]
    )
    assert out[0].startswith("`#popular`")
    assert out[1].startswith("`#mid`")
    assert out[2].startswith("`#rare`")


def test_format_tags_handles_missing_count() -> None:
    out = _format_tags([{"name": "x"}, {"name": "y", "count": None}])
    assert all(s.endswith("· 0") for s in out)


def test_format_tags_drops_garbage() -> None:
    out = _format_tags(["not-a-dict", None, {"name": "ok", "count": 1}])  # type: ignore[list-item]
    assert len(out) == 1
    assert "ok" in out[0]
