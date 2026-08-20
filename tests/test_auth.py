from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_db, reset_db_for_tests
from app.main import app


@pytest.fixture()
def auth_client(tmp_path: Path):
    settings = Settings(
        data_dir=str(tmp_path),
        auth_user="libraire",
        auth_password="secret",
        geocoder_url="http://127.0.0.1:9",
        router_url="http://127.0.0.1:9",
    )
    get_settings.cache_clear()
    db = reset_db_for_tests(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_login_page_and_session(auth_client: TestClient):
    denied = auth_client.get("/api/schools")
    assert denied.status_code == 401

    root = auth_client.get("/", follow_redirects=False)
    assert root.status_code == 303
    assert root.headers["location"] == "/login"

    login_page = auth_client.get("/login")
    assert login_page.status_code == 200
    assert "Connexion" in login_page.text

    bad = auth_client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert bad.status_code == 401

    ok = auth_client.post(
        "/api/auth/login",
        json={"username": "libraire", "password": "secret"},
    )
    assert ok.status_code == 200
    assert "matournee_session" in ok.cookies

    listed = auth_client.get("/api/schools")
    assert listed.status_code == 200

    logout = auth_client.post("/api/auth/logout")
    assert logout.status_code == 200
    denied_again = auth_client.get("/api/schools")
    assert denied_again.status_code == 401
