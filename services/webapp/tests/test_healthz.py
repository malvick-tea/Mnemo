"""Smoke test: app boots and /healthz returns ok.

Doesn't touch the DB — the index/note routes do, and need integration
fixtures we leave out of unit tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz() -> None:
    from mnemo_webapp.main import app

    with TestClient(app) as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
