from __future__ import annotations

from fastapi.testclient import TestClient

from domain_atlas.core.settings import Settings
from domain_atlas.web.app import create_app


def test_health_route_returns_ok(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Domain Atlas"}


def test_home_route_renders_skeleton(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Domain Atlas" in response.text
    assert "SDD MVP Skeleton" in response.text
