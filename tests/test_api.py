from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_db, reset_db_for_tests
from app.main import app
from app.services.geocode import GeocodeResult


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        data_dir=str(tmp_path),
        auth_user="",
        auth_password="",
        geocoder_url="http://127.0.0.1:9",
        router_url="http://127.0.0.1:9",
        depot_name="L'Evasion",
        depot_address="24 rue de la République, 57320 Bouzonville",
        map_center_lat=49.292,
        map_center_lon=6.534,
    )
    get_settings.cache_clear()

    async def fake_geocode(address: str, _settings=None) -> GeocodeResult:
        if "introuvable" in address.lower():
            return GeocodeResult(ok=False, error="Adresse introuvable", available=True)
        return GeocodeResult(ok=True, lat=49.3, lon=6.55, available=True)

    monkeypatch.setattr("app.routers.schools.geocode_address", fake_geocode)
    monkeypatch.setattr("app.main.geocode_address", fake_geocode)
    monkeypatch.setattr("app.services.geocode.ping_geocoder", lambda settings=None: _async_false())
    monkeypatch.setattr("app.services.routing.ping_router", lambda settings=None: _async_false())
    monkeypatch.setattr("app.main.ping_geocoder", _async_false)
    monkeypatch.setattr("app.main.ping_router", _async_false)

    db = reset_db_for_tests(settings)
    depot = db.get_setting("depot")
    assert depot is not None
    depot["lat"] = 49.292
    depot["lon"] = 6.534
    depot["geocode_status"] = "manual"
    db.set_setting("depot", depot)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


async def _async_false(*_args, **_kwargs) -> bool:
    return False


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] is True


def test_crud_school(client: TestClient):
    created = client.post(
        "/api/schools",
        json={
            "name": "École Test",
            "address": "1 rue de Test, 57320 Bouzonville",
            "phone": "0387000000",
        },
    )
    assert created.status_code == 201
    school = created.json()
    assert school["name"] == "École Test"
    assert school["lat"] == 49.3

    listed = client.get("/api/schools")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.put(
        f"/api/schools/{school['id']}",
        json={"name": "École Test 2", "lat": 49.31, "lon": 6.56},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "École Test 2"
    assert updated.json()["geocode_status"] == "manual"

    deleted = client.delete(f"/api/schools/{school['id']}")
    assert deleted.status_code == 204


def test_import_export_csv(client: TestClient):
    csv_content = (
        "nom;adresse;telephone;lat;lon\n"
        "École A;10 rue A, 57320 Bouzonville;0387111111;49.29;6.53\n"
        "École B;20 rue B, 57600 Forbach;;;\n"
    ).encode("utf-8-sig")
    files = {"file": ("ecoles.csv", io.BytesIO(csv_content), "text/csv")}
    imported = client.post("/api/schools/import", files=files)
    assert imported.status_code == 200
    body = imported.json()
    assert body["created"] == 2

    exported = client.get("/api/export/schools.csv")
    assert exported.status_code == 200
    assert "École A" in exported.text


def test_tour_optimize_haversine_fallback(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def no_matrix(points, settings=None):
        return None, None, False

    async def no_route(points, settings=None):
        return None, None, None, False

    monkeypatch.setattr("app.routers.tours.fetch_distance_matrix", no_matrix)
    monkeypatch.setattr("app.routers.tours.fetch_route_geometry", no_route)

    s1 = client.post(
        "/api/schools",
        json={"name": "A", "address": "addr A", "lat": 49.30, "lon": 6.55},
    ).json()
    s2 = client.post(
        "/api/schools",
        json={"name": "B", "address": "addr B", "lat": 49.25, "lon": 6.60},
    ).json()

    response = client.post(
        "/api/tours/optimize",
        json={"school_ids": [s1["id"], s2["id"]], "round_trip": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "haversine"
    assert data["distance_m"] > 0
    assert len(data["stops"]) >= 3
    assert data["geometry"]["type"] == "LineString"
