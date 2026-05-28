"""Unit tests for Anki-card JSON parsing.

The LLM contract is "return valid JSON with a `cards` array". We test the
parser's robustness to invalid items and the 20-card cap.
"""

from __future__ import annotations

import json

from mnemo_api.services.anki import _parse_cards


def test_parses_well_formed_cards() -> None:
    raw = json.dumps(
        {
            "cards": [
                {"type": "basic", "front": "Q", "back": "A"},
                {"type": "cloze", "text": "The capital is {{c1::Paris}}."},
            ]
        }
    )
    out = _parse_cards(raw)
    assert len(out) == 2
    assert out[0].type == "basic"
    assert out[0].front == "Q"
    assert out[0].back == "A"
    assert out[1].type == "cloze"
    assert out[1].text and "{{c1::Paris}}" in out[1].text


def test_drops_invalid_items() -> None:
    raw = json.dumps(
        {
            "cards": [
                {"type": "basic", "front": "Q", "back": ""},  # empty back
                {"type": "cloze", "text": "no cloze marker here"},
                {"type": "weird", "front": "X", "back": "Y"},
                {"type": "basic", "front": "Real Q", "back": "Real A"},
            ]
        }
    )
    out = _parse_cards(raw)
    assert len(out) == 1
    assert out[0].front == "Real Q"


def test_invalid_json_returns_empty() -> None:
    assert _parse_cards("not json") == []
    assert _parse_cards("[]") == []


def test_caps_at_twenty_cards() -> None:
    raw = json.dumps(
        {"cards": [{"type": "basic", "front": f"Q{i}", "back": f"A{i}"} for i in range(50)]}
    )
    assert len(_parse_cards(raw)) == 20
