"""Sanity check the bot Settings class."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from mnemo_bot.config import get_settings


@pytest.fixture(autouse=True)
def _settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_allowed_ids_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:abcDEF")
    monkeypatch.setenv("MNEMO_SERVICE_JWT_SECRET", "s" * 64)
    monkeypatch.setenv("MNEMO_ALLOWED_TG_IDS", "100,200")
    s = get_settings()
    assert 100 in s.allowed_tg_ids_set
    assert 200 in s.allowed_tg_ids_set
    assert 999 not in s.allowed_tg_ids_set


def test_secrets_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:abcDEF")
    monkeypatch.setenv("MNEMO_SERVICE_JWT_SECRET", "s" * 64)
    s = get_settings()
    assert s.tg_token.get_secret_value() == "1:abcDEF"
    assert len(s.service_jwt_secret.get_secret_value()) >= 32
