# Exercise 4 (generated): isolate API tests with a temporary SQLite database.
from __future__ import annotations

import pytest

from week2.app import config, db
from week2.app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """FastAPI test client backed by a fresh SQLite DB per test."""
    db_path = tmp_path / "test.db"
    test_settings = config.Settings(
        db_path=db_path,
        ollama_model=config.settings.ollama_model,
    )
    monkeypatch.setattr(config, "settings", test_settings)
    monkeypatch.setattr(db, "settings", test_settings)
    monkeypatch.setenv("DB_PATH", str(db_path))

    db.init_db()

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
