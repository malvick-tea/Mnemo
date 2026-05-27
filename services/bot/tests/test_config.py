"""Sanity check the bot Settings class."""

from __future__ import annotations

from mnemo_bot.config import get_settings


def test_allowed_ids_parses_csv() -> None:
    s = get_settings()
    assert 100 in s.allowed_tg_ids_set
    assert 200 in s.allowed_tg_ids_set
    assert 999 not in s.allowed_tg_ids_set


def test_secrets_loaded() -> None:
    s = get_settings()
    assert s.tg_token.get_secret_value() == "1:abcDEF"
    assert len(s.service_jwt_secret.get_secret_value()) >= 32
