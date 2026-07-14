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
    assert "创建领域项目" in response.text


def test_create_domain_redirects_to_dashboard(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/domains",
        data={
            "name": "LLM Agents",
            "goal": "建立系统化知识地图",
            "level": "beginner",
            "language": "zh",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/domains/1"

    dashboard = client.get("/domains/1")
    assert dashboard.status_code == 200
    assert "LLM Agents" in dashboard.text
    assert "建立系统化知识地图" in dashboard.text
    assert "学习路线" in dashboard.text


def test_home_lists_existing_projects(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    client.post("/domains", data={"name": "合成生物学"})

    response = client.get("/")

    assert response.status_code == 200
    assert "合成生物学" in response.text
    assert "/domains/1" in response.text


def test_missing_domain_returns_404(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/domains/404")

    assert response.status_code == 404
